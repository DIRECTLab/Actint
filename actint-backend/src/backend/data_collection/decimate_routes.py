"""
route graph clean up
keep transitions that have a circular variance close to 1 (consistent heading) or if it has a transition count > large number (airports and route intersections)
now we have good cells
remove redundant info
    if a cell has two neighbors only and the transitions are clean between them both ways list the middle cell for removal and update cell references
"""

from backend.mcp_servers.adsb.helpers.adsb_locations import get_conn
from backend.mcp_servers.utils.distance_calculation import rdp
import h3
import math

def calc_R(start, end, conn):

    R = 0

    with conn.cursor() as cur:
        cur.execute("""
                SELECT heading_sin_sum, heading_cos_sum, heading_count
                FROM route_segment_stats
                WHERE start_bin = %s
                AND end_bin = %s
            """, (start, end))
        
        rows = cur.fetchall()

    sin_sum = cos_sum = count = 0

    for row in rows:
        sin_sum += row[0]
        cos_sum += row[1]
        count += row[2]

    if count == 0:
        #print(f"stats heading count was 0")
        return 0

    R = (math.sqrt(sin_sum*sin_sum + cos_sum*cos_sum))/count
    print(f"R: {R}")

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



def get_connected_neighbors(conn, cell: str, outbound: bool): 
    """
    returns a list of neighbors connected to this cell and the number of connections
    """

    pot_neighbors = h3.grid_ring(cell, 1)
    #print(f"potential neighbors: {pot_neighbors}")
    neighbors = []
    neigh_count = 0

    for pot_neighbor in pot_neighbors:

        int_pot_neigh =  int(pot_neighbor, 16)

        vars = (int(cell,16), int_pot_neigh) if outbound else (int_pot_neigh, int(cell,16))

        with conn.cursor() as cur:
            cur.execute("""
                SELECT *
                FROM route_segments
                WHERE start_bin = %s
                AND end_bin = %s
            """, vars)

            row = cur.fetchone()

        if(row):
            neighbors.append(pot_neighbor)
            neigh_count += 1

    return neighbors, neigh_count



def get_neighbor_chain(start_cell, conn):

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

        coord = h3.cell_to_latlng(item)
        result.append(coord)
        #print(f"{coord[0]:.6f}, {coord[1]:.6f}")

    return result


def get_complex_chain(cell):
    """
    find a complex chain of cells that make up a route (multiple connections to multiple lanes not strictly 2 conns)
    """

    #


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
            start_cell = h3.int_to_str(0x87485da99ffffff)
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


if __name__ == "__main__":
    testing_chains()


