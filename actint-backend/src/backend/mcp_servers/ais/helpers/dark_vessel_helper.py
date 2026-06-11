from backend.data_processing.query_database import get_conn, DatabaseConnectionTypes
from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm
from backend.dark_vessels.dark_vessel_analysis import run_analysis


'''
Future development should involve a function for finding suspected dark activity hotspots and getting fishy trajectories
Pseudocode: 

    def get_fishy_hotspots_helper(region):
        """Identify areas within a region that have a high density of fishy vessels."""
        # detections = get_fishy_vessel_locations_helper(region)
        # hotspots = []
        # for detection in detections:
            # figure out their trajectory
            # figure out if that trajectory intercepts any previously detected trajectories
                # if so, save that point
            # for each interception point
                # count how many interception points are surrounding the point within a certain radius
                # if that number exceeds n
                    # add that point to the list of hotspots
        # return list of areas that have a high density of fishy vessels
        # return hotspots


    def get_fishy_vessel_trajectories(region):
        """Use the ship_going tools to figure out where each fishy vessel in a region is likely headed"""
        # vessels = get_fishy_vessel_locations_helper(region)
        # trajectories = []
        # for each vessel
            # get trajectory using ship_going tools
        # return trajectories

'''


def query_vessel(mmsi):
    """See if a specific vessel is in the list of suspicious vessels"""
    conn = get_conn(DatabaseConnectionTypes.FISHY_VESSELS)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dark_detections WHERE mmsi = %s;", (mmsi,))
    results = cursor.fetchall()
    conn.close()
    if len(results) == 0:
        return (f"No vessel with mmsi {mmsi} found in fishy vessels database.")
    else: 
        return results


def find_fishy_clusters(mmsi: str, number_ships: str) -> str:
    """Detect clusters of suspicious vessels"""
    mmsi = int(mmsi)
    number_ships = int(number_ships)
    detections = get_fishy_vessel_locations_helper()
    mmsis = get_fishy_mmsis()
    if mmsi not in mmsis:
        raise ValueError("MMSI not in vessels")
    primary_ship_location = get_vessel_latest_location_helper(mmsi)
    primary_lat = primary_ship_location[2]  # Assuming lat is the 3rd column in the result
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
            f"{time_str}\n"
        )
    return output


def get_fishy_mmsis():
    """Get the MMSIs of vessels in a region marked as suspicious based on dark vessel analysis."""
    conn = get_conn(DatabaseConnectionTypes.FISHY_VESSELS)
    cursor = conn.cursor()
    cursor.execute("SELECT mmsi FROM dark_detections")
    results = cursor.fetchall()
    conn.close()
    return [row[0] for row in results if row[0] is not None]


def get_vessel_latest_location_helper(mmsi: int) -> dict | None:
    """Get the latest known location of a vessel given its MMSI."""
    conn = get_conn(DatabaseConnectionTypes.FISHY_VESSELS)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dark_detections WHERE mmsi = %s ORDER BY basedatetime DESC LIMIT 1;", (mmsi,))
    result = cursor.fetchone()
    conn.close()
    
    return result

