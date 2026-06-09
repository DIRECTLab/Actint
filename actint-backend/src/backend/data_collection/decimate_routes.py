
from backend.mcp_servers.adsb.helpers.adsb_locations import get_conn
from backend.mcp_servers.utils.distance_calculation import rdp
import h3
import math

from dataclasses import dataclass
from typing import Optional
from psycopg.rows import dict_row

#WE PASS AND RETURN ALL CELL NAMES AS HEXADECIMAL INT, FUNCTIONS SHOULD HANDLE STRING CONVERSION AS NECESSARY
#naive chain calculations assume cells are actually neighbors with a shared hex edge (ignores multi-hop transitions)

#mvp goal: simplified routes as a list of corridors and intersections and a tool to see what corridor a plane is in and predict next segment based on stats
#stretch goal: ML model to predict destinations over the graph given adsb points
#OBJECTID	GLOBAL_ID	IDENT	TYPE_CODE	LEVEL_	WKHR_CODE	WKHR_RMK	MAA_VAL	MAA_UOM	MEA_E_VAL	MEA_E_UOM	MEA_W_VAL	MEA_W_UOM	GMEA_E_VAL	GMEA_E_UOM	GMEA_W_VAL	GMEA_W_UOM	DMEA_VAL	DMEA_UOM	MOCA_VAL	MOCA_UOM	MEAGAP	TRUETRK	MAGTRK	REVTRUETRK	REVMAGTRK	NMAGTRK	NREVMAGTRK	LENGTH_VAL	COPDIST	COPNAV_ID	REPATCSTAR	REPATCEND	DIRECTION	FREQ_CLASS	STATUS	STARTPT_ID	ENDPT_ID	RTPORT_ID	ENRINFO_ID	WIDTHRIGHT	WIDTHLEFT	WIDTH_UOM	MCA1_VAL	MCA1_UOM	MCA1_DIR	MCA2_VAL	MCA2_UOM	MCA2_DIR	MCAPT_ID	MCAPT_TYPE	TFLAG_CODE	REMARKS	AK_LOW	AK_HIGH	US_LOW	US_HIGH	US_AREA	PACIFIC	Shape__Length


def calc_R(stats):
    """
    calculates the R value of a given cell transition. R value is the mean resultant length aka the heading consistency 1 = very consistent 0 = going all over
    """
    sin_sum, cos_sum, count = stats

    if count == 0:
        #print(f"stats heading count was 0")
        return 0

    R = (math.sqrt(sin_sum*sin_sum + cos_sum*cos_sum))/count
    print(f"R: {R}")

    return R


def get_transition_stats(start, end, conn):

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
                SELECT heading_sin_sum, heading_cos_sum, heading_count
                FROM route_segment_stats
                WHERE start_bin = %s
                AND end_bin = %s
            """, (start, end))
        
        rows = cur.fetchall()
    
    return rows #returns list of dicts with each row as a dict


def aggregate_stats(stats):
    """sum up the stats in a list of stat dicts from the db.

    Args:
        stats (list of dicts) stats object list of stat dicts.

    Returns: 
        alist (list): sin_sum, cos_sum, count.
    """
    sin_sum = cos_sum = count = 0

    for stat in stats:
        sin_sum += stat["heading_sin_sum"]
        cos_sum += stat["heading_cos_sum"]
        count += stat["heading_count"]

    return sin_sum, cos_sum, count



def calc_transitions_R(start, end, conn):

    rows = get_transition_stats(start, end, conn)
    stats = aggregate_stats(rows)
    R = calc_R(stats)
    return R



def stream_segments(conn):

    with conn.cursor(name="segment_stream") as cur:

        cur.execute("""
            SELECT start_bin, end_bin, transition_count
            FROM route_segments
        """)

        while True:

            rows = cur.fetchmany(10000)

            if not rows:
                break

            for row in rows:
                yield row



def get_connected_neighbors(conn, cell: int, outbound: bool): 
    """
    returns a list of neighbors connected to this cell and the number of connections
    """

    cell_str = str(hex(cell))

    pot_neighbors = h3.grid_ring(cell_str, 1)
    #print(f"potential neighbors: {pot_neighbors}")
    neighbors: int = []
    neigh_count = 0

    for pot_neighbor in pot_neighbors:

        int_pot_neigh =  int(pot_neighbor, 16)

        vars = (cell, int_pot_neigh) if outbound else (int_pot_neigh, cell)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT *
                FROM route_segments
                WHERE start_bin = %s
                AND end_bin = %s
            """, vars)

            row = cur.fetchone()

        if(row):
            neighbors.append(int_pot_neigh)
            neigh_count += 1

    return neighbors, neigh_count



def get_neighbor_chain(start_cell: int, conn):

    def walk(current, previous, forward):
        """
        direction=True  -> outbound walk
        direction=False -> inbound walk
        """

        result = []
        visited = set()

        while True:

            if current in visited:
                break

            visited.add(current)

            out_neighbors, out_count = get_connected_neighbors(conn, current, outbound=True)
            print(f"chain start cell: {current}")
            print(f"out_neighs: {out_neighbors}, {out_count}")
            in_neighbors, in_count = get_connected_neighbors(conn, current, outbound=False)
            print(f"in_neighs: {in_neighbors}, {in_count}")

            unique_neighbors = set(out_neighbors + in_neighbors)

            # endpoint
            if out_count != 1 or in_count != 1 or len(unique_neighbors) != 2:
                break

            if forward:
                if previous not in in_neighbors:
                    break
                next_cell = out_neighbors[0]

            else:
                if previous not in out_neighbors:
                    break
                next_cell = in_neighbors[0]

            result.append(current)

            previous = current
            current = next_cell

        return result

    # start node classification
    out_neighbors, out_count = get_connected_neighbors(conn, start_cell, outbound=True)
    in_neighbors, in_count = get_connected_neighbors(conn, start_cell, outbound=False)

    # isolated
    if out_count + in_count == 0:
        return [start_cell]

    # invalid branching start
    if (out_count != 1 or in_count != 1 or len(set(out_neighbors + in_neighbors)) != 2):
        return None

    print(f"execute backward pass")
    backward = walk(
        current=in_neighbors[0],
        previous=start_cell,
        forward=False
    )

    print(f"execute forward pass")
    forward = walk(
        current=out_neighbors[0],
        previous=start_cell,
        forward=True
    )

    return (
        list(reversed(backward))
        + [start_cell]
        + forward
    )



def chain_to_latlon(chain):

    result = []

    for item in chain:

        str_item = str(hex(item))

        coord = h3.cell_to_latlng(str_item)
        result.append(coord)
        #print(f"{coord[0]:.6f}, {coord[1]:.6f}")

    return result



def calc_directed_average_R(conn, cell, outbound):
    """
    find the average R value for transitions into or out of a cell
    outbound (bool): True = get outbound connections R False then do inbound
    adds all neighbor cell's sin and cos values together to find group R value
    """

    neighbors, count = get_connected_neighbors(conn, cell, outbound)
    print(f"chain start cell: {cell}")
    print(f"out_neighs: {neighbors}, {count}")

    R_sum = 0

    all_stats = [0,0,0]

    for neighbor in neighbors:

        if(outbound):
            stats = get_transition_stats(cell, neighbor, conn)
        else:
            stats = get_transition_stats(neighbor, cell, conn)

        agg_stats = aggregate_stats(stats)
        all_stats[0] += agg_stats[0]
        all_stats[1] += agg_stats[1]
        all_stats[2] += agg_stats[2]

    R_ave = calc_R(all_stats)

    print(f"average R: {R_ave}")
    return R_ave


def compute_orientation(headings_deg):
    rx = 0.0
    ry = 0.0
    n = len(headings_deg)

    for h in headings_deg:
        theta = math.radians(h)

        rx += math.cos(2 * theta)
        ry += math.sin(2 * theta)

    # orientation strength
    R = math.sqrt(rx*rx + ry*ry) / n

    # mean axis
    mean_angle = 0.5 * math.atan2(ry, rx)

    orientation_deg = math.degrees(mean_angle) % 180

    return orientation_deg, R



def calc_cell_orientation(conn, cell):
    """
    given a cell calculate the orientation using the transition stats of all its neighbors
    """
    out_neighbors, out_count = get_connected_neighbors(conn, cell, outbound=True)
    in_neighbors, in_count = get_connected_neighbors(conn, cell, outbound=False)

    print(f"chain start cell: {cell}")
    print(f"out_neighs: {out_neighbors}, {out_count}")
    print(f"in_neighs: {in_neighbors}, {in_count}")

    headings = []

    for neighbor in out_neighbors:

        stats = get_transition_stats(cell, neighbor, conn)
        agg_stats = aggregate_stats(stats)

        sin, cos, count = agg_stats

        heading = math.degrees(math.atan2(sin, cos)) % 360
        headings.append(heading)

    for neighbor in in_neighbors:

        stats = get_transition_stats(neighbor, cell, conn)
        agg_stats = aggregate_stats(stats)

        sin, cos, count = agg_stats

        heading = math.degrees(math.atan2(sin, cos)) % 360
        headings.append(heading)

    orientation = compute_orientation(headings)
    print(f"orientation: {orientation}")
    return orientation



@dataclass
class Corridor:
    corridor_id: int

    # geometry
    start_cell_id: int
    end_cell_id: int

    #defines the centerline that width and length are based off of
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float

    width_km: float
    length_km: float

    # orientation
    orientation_deg: float          # 0-180 axis
    orientation_std_deg: float      #standard deviation (how straight is the corridor?)

    # flow characteristics
    is_bidirectional: bool

    forward_count: int
    reverse_count: int

    # consistency metrics
    orientation_strength: float     # 0-1 R on the orientation data

    # altitude
    min_altitude_ft: Optional[int]
    max_altitude_ft: Optional[int]
    mean_altitude_ft: Optional[int]
    dominant_alt_band: Optional[str]

    # topology
    start_intersection_id: Optional[int]
    end_intersection_id: Optional[int]

    # metadata
    cell_count: int #number of h3 res 7 cells contained in the route





def get_corridor(cell):
    """
    find a complex corridor of cells that make up a consistent route using heading vectors and clustering
    """

    # bi-directional corridor if a -> b and b -> a have consistent and inverse average headings (180 off)
    # uni-directional corridor if a -> b has consistent heading and b -> a is inconsistent or non existent 
    # how to find the intersections? 
    # intersection is the meeting of two corridors, this won't typically be a clean single cell or definite point
        # intersections will have certain characteristics including inconsistent headings, heavily favored altitude band, 

    # general idea for bi-directional corridor - bin all the cells around based on their average heading bins could be of 15 degrees of more, then check how far apart those bins are, if 180 degrees or close then its a good corridor


    #is the cell likely to be in a corridor? yes if high orientation score otherwise ignore it



CIRC_VAR = 0.8 # value 0-1: 1 means all headings are perfectly aligned 0 means completely inconsistent
NOISE_FLOOR = 5

def main():

    with get_conn() as conn:

        #get stream of transitions
        for start_bin, end_bin, trans_count in stream_segments(conn):

            #start by simplifying the routes as much as possible (rdp and surrounded to one)

            #print(f"start_bin: {start_bin}")
            start_cell = str(hex(start_bin))
            #print(f"start cell: {start_cell}")
            neighbors, count = get_connected_neighbors(start_cell, conn)

            if count > 2:
                None
                #this is an intersection
            elif count == 2:
                #this is prime for RDP simplification
                chain = get_neighbor_chain(start_cell, conn)
                coords = chain_to_latlon(chain)
                simplified_coords = rdp(coords, 0.001)

            else: #(1 or 0 connected)
                None
                #end of the line or an island 
            
            #if connected_neighbors == 6:
                #surrounded - consider merging neighbors into one node (simplify heavy traffic areas)


            #next delete any nodes that are still useless

            R = calc_R(start_bin, end_bin, conn)

            if(R >= CIRC_VAR or trans_count >= NOISE_FLOOR):
                #KEEP
                print(f"Keeping: {start_bin},{end_bin} with R = {R} and count = {trans_count}")
                
            else:
                #DELETE
                #print(f"Removing: {start_bin},{end_bin} with R = {R} and count = {trans_count}")
                None
            

def testing_chains():

    with get_conn() as conn:

        #get stream of transitions
        #for start_bin, end_bin, trans_count in stream_segments(conn):

            #print(f"start_bin: {start_bin}")
            start_cell = 0x87485da99ffffff
            print(f"start cell: {start_cell}")
            out_neighbors, out_count = get_connected_neighbors(conn, start_cell, outbound=True)
            print(f"out_neighs: {out_neighbors}, {out_count}")
            in_neighbors, in_count = get_connected_neighbors(conn, start_cell, outbound=False)
            print(f"in_neighs: {in_neighbors}, {in_count}")

            if out_count == 1 and in_count == 1:
                chain = get_neighbor_chain(start_cell, conn)
                coords = chain_to_latlon(chain)

                #if(len(coords) > 15):
                print(f"chain: {chain}")
                print(f"final coords:")
                for coord in coords:
                    print(f"{coord[0]:.6f}, {coord[1]:.6f}")


def testing_rdp():
    # input points given as (lon, lat) -> convert to (lat, lon)
    raw_points = [
        (-71.01931, 42.37111),
        (-71.01932, 42.371113),
        (-71.01923, 42.37123),
        (-71.01918, 42.371292),
        (-71.01917, 42.371334),
        (-71.019135, 42.371372),
        (-71.01912, 42.371407),
        (-71.01909, 42.37144),
        (-71.01906, 42.371487),
        (-71.01903, 42.37152),
        (-71.01901, 42.371555),
        (-71.019, 42.37159),
        (-71.01894, 42.371628),
        (-71.01885, 42.371674),
        (-71.01865, 42.371754),
        (-71.01859, 42.37176),
        (-71.01856, 42.371765),
        (-71.01847, 42.37172),
        (-71.01843, 42.371704),
        (-71.01843, 42.371704),
    ]

    # -71.01931	42.37111
    # -71.01932	42.371113
    # -71.01923	42.37123
    # -71.01918	42.371292
    # -71.01917	42.371334
    # -71.019135	42.371372
    # -71.01912	42.371407
    # -71.01909	42.37144
    # -71.01906	42.371487
    # -71.01903	42.37152
    # -71.01901	42.371555
    # -71.019	42.37159
    # -71.01894	42.371628
    # -71.01885	42.371674
    # -71.01865	42.371754
    # -71.01859	42.37176
    # -71.01856	42.371765
    # -71.01847	42.37172
    # -71.01843	42.371704
    # -71.01843	42.371704

    # convert to (lat, lon)
    points = [(lat, lon) for lon, lat in raw_points]

    epsilon = 0.001  # nautical miles (adjust as needed)

    print("Original points:", len(points))

    simplified = rdp(points, epsilon)

    print("Simplified points:", len(simplified))
    print("\nResult:")

    for lat, lon in simplified:
        print(f"{lon:.6f}, {lat:.6f}")


def testing_R_calc():

    with get_conn() as conn:
        print("")
        calc_directed_average_R(conn, 0x87195D699FFFFFF, outbound=True)
        print("")
        calc_directed_average_R(conn, 0x87195D699FFFFFF, outbound=False)
        print("")
        calc_cell_orientation(conn, 0x87195D699FFFFFF)
    

if __name__ == "__main__":
    testing_R_calc()


