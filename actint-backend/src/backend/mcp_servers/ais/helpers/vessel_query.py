from backend.data_processing.query_database import get_conn
from rapidfuzz import process, utils
import sys


# def get_vessel_information_helper(mmsi: int) -> dict:
#     """Get detailed information about a vessel given its MMSI."""
#     conn = get_conn()
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM ais_static_data WHERE mmsi = %s;", (mmsi,))
#     result = cursor.fetchone()
#     conn.close()
#     if result:
#         return {
#             "mmsi": result[0],
#             "vesselname": result[1],
#             "origincountry": result[3] if result[3] else "Unknown",
#             "homebase": result[11] if result[11] else "Unknown",
#             "parentcommand": result[12] if result[12] else "Unknown",
#             "fleet": result[13] if result[13] else "Unknown",
#         }
#     return "No Vessel with that MMSI."


def get_all_vessel_names() -> list[str]:
    conn = get_conn()
    cursor=conn.cursor()
    cursor.execute("SELECT vesselname FROM ais_static_data;")
    results = cursor.fetchall()
    conn.close()
    clean_names = [row[0] for row in results if row[0] is not None]
    return clean_names

def get_all_mmsis() -> list[int]:
    conn = get_conn()
    cursor=conn.cursor()
    cursor.execute("SELECT mmsi FROM ais_static_data;")
    results = cursor.fetchall()
    conn.close()
    clean_mmsis = [row[0] for row in results if row[0] is not None]
    return clean_mmsis


def get_vessel_name_helper(mmsi: int) -> str:
    """Get the name of a vessel given its MMSI."""
    name = get_static_data_helper(mmsi)['vesselname']
    if name:
        return name
    return "No Vessel with that MMSI."


def get_vessel_mmsi_helper(vessel_name: str) -> int:
    """Get the MMSI of a vessel given its name."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT mmsi FROM ais_static_data WHERE UPPER(vesselname) = UPPER(%s);", (vessel_name,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    raise ValueError("No Vessel with that name.")


def get_similar_vessel_names(query: str, number_results: int) -> list[str]:
    names = get_all_vessel_names()
    matches = process.extract(
        query,
        names, 
        limit=number_results,
        processor=utils.default_process # Handles case and whitespace automatically
    )
    names = [match[0] for match in matches]
    return names

def get_similar_mmsis(query: str, number_results: int) -> list[int]:
    mmsis = get_all_mmsis()
    matches = process.extract(
        query,
        mmsis, 
        limit=number_results,
        processor=utils.default_process # Handles case and whitespace automatically
    )
    mmsis = [match[0] for match in matches]
    return mmsis
    


def get_vessel_position_history_helper(mmsi: int) -> list[dict]:
    """Get the position history of a vessel given its MMSI."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ais_dynamic_data WHERE mmsi = %s ORDER BY basedatetime DESC;", (mmsi,))
    results = cursor.fetchall()
    conn.close()

    return [dict(zip([key[0] for key in cursor.description], row)) for row in results]


def get_vessel_latest_location_helper(mmsi: int) -> dict:
    return get_vessel_position_history_helper(mmsi)[0]

def get_all_fleets() -> list[str]:
    """Get a list of all fleets."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT fleet FROM ais_static_data WHERE fleet IS NOT NULL AND fleet != '';")
    results = cursor.fetchall()
    conn.close()
    fleets = []
    for result in results:
        fleet = result[13]
        if fleet not in fleets:
            fleets.append(fleet)
    return fleets

def get_static_data_helper():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ais_static_data;")
    results = cursor.fetchall()
    conn.close()
    return [dict(zip([key[0] for key in cursor.description], row)) for row in results]

def query_static_data_helper(searchQuery: dict):
    conn = get_conn()
    cursor = conn.cursor()

    prompt = "SELECT * FROM ais_static_data WHERE "
    for key, value in searchQuery.items():
        prompt += f"{key} = %s AND "
    prompt = prompt[:-5] + ";"  # Remove trailing ' AND ' and add semicolon
    cursor.execute(prompt, tuple(searchQuery.values()))
    results = cursor.fetchall()
    columns = [key[0] for key in cursor.description]
    conn.close()
    
    return [dict(zip(columns, row)) for row in results]

def query_dynamic_data_helper(searchQuery: dict, sort=False):
    conn = get_conn()
    cursor = conn.cursor()

    prompt = "SELECT * FROM ais_dynamic_data WHERE "
    for key, value in searchQuery.items():
        prompt += f"{key} = %s AND "
    prompt = prompt[:-5] + ";"  # Remove trailing ' AND ' and add semicolon 

    cursor.execute(prompt, tuple(searchQuery.values()))
    results = cursor.fetchall()
    conn.close()
    if(results and sort):
        sorted_vessels = sorted(
            results,
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_vessels

    return results

