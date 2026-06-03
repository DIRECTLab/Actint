from backend.data_processing.query_database import get_conn, DatabaseConnectionTypes
from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm
#from colorama import Fore, Style #for debugging prints


def query_region(region):
    #TODO: Add a check to make sure the region is a region we have data for
    """Return the list of fishy vessels in a region"""
    conn = get_conn(DatabaseConnectionTypes.FISHY_VESSELS)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sampletable;")
    results = cursor.fetchall()
    conn.close()
    return results


def query_vessel(name):
    """See if a specific vessel is in the list of fishy vessels"""
    conn = get_conn(DatabaseConnectionTypes.FISHY_VESSELS)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sampletable WHERE name = %s;", (name,))
    results = cursor.fetchall()
    conn.close()
    if len(results) == 0:
        return (f"No vessel with name {name} found in fishy vessels database.")
    else: 
        return results


def get_fishy_vessel_locations(region):
    """Get the most recent locations of vessels in a region marked as suspicious based on dark vessel analysis."""
    conn = get_conn(DatabaseConnectionTypes.FISHY_VESSELS)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sampletable WHERE region = %s;", (region,))
    results = cursor.fetchall()
    conn.close()

    columns = [col[0] for col in cursor.description]
    detections = [
        dict(zip(columns, row))
        for row in results
    ]

    return detections


def find_fishy_clusters(mmsi: str, number_ships: str, region: str) -> str:
    mmsi = int(mmsi)
    number_ships = int(number_ships)
    detections = get_fishy_vessel_locations(region)
    mmsis = get_fishy_mmsis(region)
    if mmsi not in mmsis:
        raise ValueError("MMSI not in vessels")
    primary_ship_location = get_vessel_latest_location_helper(mmsi)
    primary_lat = primary_ship_location[2]  #TODO: Make it so these don't need to be hardcoded
    primary_lon = primary_ship_location[3]
    distances = []

    for detection in detections:
        if detection['mmsi'] == mmsi:
            continue
        lat = detection['lat']
        lon = detection['lon']
        if lat is None or lon is None:
            continue
        distance = haversine_distance_nm(primary_lat, primary_lon, lat, lon)
        distances.append({
            "distance": distance,
            "data": detection
        })

    distances.sort(key=lambda x: x['distance'])
    nearest_ships = distances[:number_ships]
    output = (
        f"The {number_ships} closest ships to {mmsi} are:\n\n"
        "MMSI       | Distance (nm) | Latitude   | Longitude   | SOG   | COG   | Time\n"
        "-----------+---------------+------------+-------------+-------+-------+----------\n"
    )

    for ship in nearest_ships:
        # determine if the vessel is a fishy vessel
        data = ship["data"]

        time_str = data["basedatetime"].strftime("%H:%M:%S") \
            if hasattr(data["basedatetime"], "strftime") \
            else str(data["basedatetime"])
        output += (
            f"{data['mmsi']:<10} | "
            f"{ship['distance']:<13.3f} | "
            f"{data['lat']:<10.5f} | "
            f"{data['lon']:<11.5f} | "
            f"{data['sog']:<5.1f} | "
            f"{data['cog']:<5.1f} | "
            f"{time_str}\n"
        )
    return output


def get_fishy_mmsis(region):
    """Get the MMSIs of vessels in a region marked as suspicious based on dark vessel analysis."""
    conn = get_conn(DatabaseConnectionTypes.FISHY_VESSELS)
    cursor = conn.cursor()
    cursor.execute("SELECT mmsi FROM sampletable WHERE region = %s;", (region,))
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results if row[0] is not None]


def get_vessel_latest_location_helper(mmsi: int) -> dict | None:
    """Get the latest known location of a vessel given its MMSI."""
    conn = get_conn(DatabaseConnectionTypes.FISHY_VESSELS)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sampletable WHERE mmsi = %s ORDER BY basedatetime DESC LIMIT 1;", (mmsi,))
    result = cursor.fetchone()
    conn.close()
    
    return result


def get_fishy_vessel_trajectories(region):
    """Use the ship_going tools to figure out where each fishy vessel in a region is likely headed"""

    vessels = get_fishy_vessel_locations(region)

    # for each vessel
        # get trajectory using ship_going tools

    pass


def run_tests():
    """Run tests for the functions in this file."""
    failed = False

    print("\nRunning tests for dark_vessel_helper.py...\n")

    if len(query_region("brazil_eez")) == 0:
        #print(Fore.LIGHTRED_EX) # uncomment for colour coded terminal output
        print("query_region test failed: No vessels found in region.")
        #print (Fore.RESET) # uncomment for colour coded terminal output
        failed = True
    else:
        #print(Fore.LIGHTGREEN_EX)
        print("query_region test passed.")
        #print(Fore.RESET)

    if len(query_vessel("steve")) == 0:
        #print(Fore.LIGHTRED_EX)
        print("query_vessel test failed: No vessel with name steve found.")
        #print(Fore.RESET)
        failed = True
    else:
        #print(Fore.LIGHTGREEN_EX)
        print("query_vessel test passed.")
        #print(Fore.RESET)

    # get fishy vessel locations
    if len(get_fishy_vessel_locations("brazil_eez")) == 0:
        #print(Fore.LIGHTRED_EX)
        print("get_fishy_vessel_locations test failed: No vessels found in region.")
        #print(Fore.RESET)
        failed = True
    else: 
        #print(Fore.LIGHTGREEN_EX)
        print("get_fishy_vessel_locations test passed.")
        #print(Fore.RESET)

    # find fishy clusters
    if len(find_fishy_clusters("9", "5", "brazil_eez")) == 0:
        #print(Fore.LIGHTRED_EX)
        print("find_fishy_clusters test failed: No clusters found.")
        #print(Fore.RESET)
        failed = True
    else:
        #print(Fore.LIGHTGREEN_EX)
        print("find_fishy_clusters test passed.")
        #print(Fore.RESET)

    #TODO: write test for get fishy vessel trajectories

    if not failed:
        print("\nAll tests passed.\n")


if __name__ == "__main__":
    run_tests()
