from backend.data_processing.query_database import get_conn
from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm

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

def get_all_fleet_names() -> list[str]:
    conn = get_conn()
    cursor=conn.cursor()
    cursor.execute("SELECT fleet FROM ais_static_data;")
    results = cursor.fetchall()
    conn.close()
    clean_names = [row[0] for row in results if row[0] is not None]
    return clean_names

def get_vessel_name(mmsi: int) -> str:
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

def get_vessel_position_history_helper(mmsi: int, limit = None) -> list[dict]:
    """Get the position history of a vessel given its MMSI."""
    conn = get_conn()
    cursor = conn.cursor()
    if limit:
        limit = int(limit)
        cursor.execute("SELECT * FROM ais_dynamic_data WHERE mmsi = %s ORDER BY basedatetime DESC LIMIT %s;" , (mmsi, limit),)
    else:
        cursor.execute("SELECT * FROM ais_dynamic_data WHERE mmsi = %s ORDER BY basedatetime DESC;", (mmsi,))
    results = cursor.fetchall()
    conn.close()

    return [dict(zip([key[0] for key in cursor.description], row)) for row in results]


def get_vessel_latest_location_helper(mmsi: int) -> dict | None:
    """Get the latest known location of a vessel given its MMSI."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ais_dynamic_data WHERE mmsi = %s ORDER BY basedatetime DESC LIMIT 1;", (mmsi,))
    result = cursor.fetchone()
    conn.close()
    
    return dict(zip([key[0] for key in cursor.description], result))


def get_all_latest_detections_helper() -> list[dict]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY mmsi ORDER BY basedatetime DESC) AS rn FROM ais_dynamic_data) sub WHERE rn = 1;")
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    conn.close()

    return [dict(zip(columns, row)) for row in rows]

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
