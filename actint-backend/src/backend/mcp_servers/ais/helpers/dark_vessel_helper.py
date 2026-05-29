from backend.data_processing.query_database import get_conn, DatabaseConnectionTypes
from colorama import Fore, Style


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
    cursor.execute("SELECT name, lat, lon FROM sampletable WHERE region = %s;", (region,))
    results = cursor.fetchall()
    conn.close()
    return results


def find_fishy_clusters(mmsi: str, number_ships: str, region: str) -> str:
    mmsi = int(mmsi)
    number_ships = int(number_ships)
    detections = get_fishy_vessel_locations(region)
    mmsis = get_all_mmsis()
    if mmsi not in mmsis:
        raise ValueError("MMSI not in vessels")
    primary_ship_location = get_vessel_latest_location_helper(mmsi)
    primary_lat = primary_ship_location['lat']
    primary_lon = primary_ship_location['lon']
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


def get_fishy_vessel_trajectories(region):
    """Use the ship_going tools to figure out where each fishy vessel in a region is likely headed"""

    vessels = get_fishy_vessel_locations(region)

    # for each vessel
        # get trajectory using ship_going tools

    pass


def run_tests():
    """Run tests for the functions in this file."""
    failed = False

    if len(query_region("brazil_eez")) == 0:
        print(Fore.LIGHTRED_EX + "query_region test failed: No vessels found in region." + Fore.RESET)
        failed = True
    else:
        print(Fore.LIGHTGREEN_EX + "query_region test passed." + Fore.RESET)

    if len(query_vessel("steve")) == 0:
        print(Fore.LIGHTRED_EX + "query_vessel test failed: No vessel with name steve found." + Fore.RESET)
        failed = True
    else:
        print(Fore.LIGHTGREEN_EX + "query_vessel test passed." + Fore.RESET)

    # get fishy vessel locations
    if len(get_fishy_vessel_locations("brazil_eez")) == 0:
        print(Fore.LIGHTRED_EX + "get_fishy_vessel_locations test failed: No vessels found in region." + Fore.RESET)
        failed = True
    else: 
        print(Fore.LIGHTGREEN_EX + "get_fishy_vessel_locations test passed." + Fore.RESET)

    # find fishy clusters
    if len(find_fishy_clusters("123456789", "5", "brazil_eez")) == 0:
        print(Fore.LIGHTRED_EX + "find_fishy_clusters test failed: No clusters found." + Fore.RESET)
        failed = True
    else:
        print(Fore.LIGHTGREEN_EX + "find_fishy_clusters test passed." + Fore.RESET)

    #TODO: write test for get fishy vessel trajectories

    if not failed:
        print("All tests passed.")

run_tests()