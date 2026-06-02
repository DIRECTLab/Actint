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



def get_connected_neighbors(cell, conn): 
    """
    returns a list of neighbors connected to this cell and the number of connections
    """

    pot_neighbors = h3.grid_ring(cell, 1)
    #print(f"potential neighbors: {pot_neighbors}")
    neighbors = []
    neigh_count = 0

    for pot_neighbor in pot_neighbors:

        int_pot_neigh =  int(pot_neighbor, 16)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT *
                FROM route_segments
                WHERE start_bin = %s
                AND end_bin = %s
            """, (int(cell,16), int_pot_neigh))

            row = cur.fetchone()

        if(row):
            neighbors.append(pot_neighbor)
            neigh_count += 1

    return neighbors, neigh_count



def get_neighbor_chain(start_cell, conn):
    """
    Returns an ordered chain of connected cells.

    Assumes:
    - interior chain nodes have exactly 2 neighbors
    - endpoints have exactly 1 neighbor
    - branching nodes (>2 neighbors) are invalid
    """

    def walk_direction(current, previous):
        """
        Walk in one direction along the chain.

        Args:
            current: current cell
            previous: cell we came from
        Returns:
            Ordered list of cells in this direction.
        """

        result = []

        while True:

            neighbors, count = get_connected_neighbors(current, conn)

            # Invalid topology
            if count == 0 or count > 2:
                break

            # Add current cell
            result.append(current)

            # Endpoint reached
            if count == 1:
                break

            # Continue forward
            next_cells = [
                n for n in neighbors
                if n != previous
            ]

            # Chain broken or loop detected
            if len(next_cells) != 1:
                break

            next_cell = next_cells[0]

            previous = current
            current = next_cell

        return result

    # Get start node neighbors
    neighbors, count = get_connected_neighbors(start_cell, conn)

    # Isolated node
    if count == 0:
        return [start_cell]

    # Invalid branching start
    if count > 2:
        return None

    # Start is endpoint
    if count == 1:
        forward = walk_direction(neighbors[0], start_cell)
        return [start_cell] + forward

    # Start is middle node (count == 2)
    left = walk_direction(neighbors[0], start_cell)
    right = walk_direction(neighbors[1], start_cell)

    return (
        list(reversed(left))
        + [start_cell]
        + right
    )


def chain_to_latlon(chain):

    result = []

    for item in chain:

        coord = h3.cell_to_latlng(item)
        result.append(coord)
        #print(f"{coord[0]:.6f}, {coord[1]:.6f}")

    return result



CIRC_VAR = 0.8 # value 0-1: 1 means all headings are perfectly aligned 0 means completely inconsistent
NOISE_FLOOR = 5

def main():

    with get_conn() as conn:

        #get stream of transitions
        for start_bin, end_bin, trans_count in stream_segments(conn):

            #start by simplifying the routes as much as possible (rdp and surrounded to one)

            #if connected_neighbors > 2:
                #this is an intersection
            #elif connected_neighbors == 2:
                #this is prime for RDP simplification
            #else: (1 or 0 connected)
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
        for start_bin, end_bin, trans_count in stream_segments(conn):

            #print(f"start_bin: {start_bin}")
            start_cell = str(hex(start_bin))
            #print(f"start cell: {start_cell}")
            neighbors, count = get_connected_neighbors(start_cell, conn)

            if count == 2:
                chain = get_neighbor_chain(start_cell, conn)
                coords = chain_to_latlon(chain)

                if(len(coords) > 3):
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


