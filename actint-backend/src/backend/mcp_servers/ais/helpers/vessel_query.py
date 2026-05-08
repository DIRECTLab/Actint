from backend.data_processing.query_database import get_conn


def get_vessel_name(mmsi: int) -> str:
    """Get the name of a vessel given its MMSI."""
    name = get_vessel_information(mmsi)['vessel_name']
    if name:
        return name
    return "No Vessel with that MMSI."



def get_vessel_mmsi(vessel_name: str) -> int:
    """Get the MMSI of a vessel given its name."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT mmsi FROM ais_dynamic_data WHERE UPPER(vessel_name) = UPPER(%s);", (vessel_name,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return "No Vessel with that name."


def get_vessel_information(mmsi: int) -> dict:
    """Get detailed information about a vessel given its MMSI."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ais_static_data WHERE mmsi = %s;", (mmsi,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            "mmsi": result[0],
            "vessel_name": result[1],
            "origin_country": result[3] if result[3] else "Unknown",
            "home_base": result[11] if result[11] else "Unknown",
            "parent_command": result[12] if result[12] else "Unknown",
            "fleet": result[13] if result[13] else "Unknown",
        }
    return "No Vessel with that MMSI."

    


def get_vessel_position_history(mmsi: int) -> list[dict]:
    """Get the position history of a vessel given its MMSI."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ais_dynamic_data WHERE mmsi = %s ORDER BY basedatetime DESC;", (mmsi,))
    results = cursor.fetchall()
    conn.close()

    return [dict(zip([key[0] for key in cursor.description], row)) for row in results]


def get_latest_vessel_position(mmsi: int) -> dict:
    return get_vessel_position_history(mmsi)[0]

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

def get_static_data():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ais_static_data;")
    results = cursor.fetchall()
    conn.close()
    return [dict(zip([key[0] for key in cursor.description], row)) for row in results]

def query_static_data(searchQuery: dict):
    conn = get_conn()
    cursor = conn.cursor()

    prompt = "SELECT * FROM ais_static_data WHERE "
    for key, value in searchQuery.items():
        prompt += f"{key} = %s AND "
    prompt = prompt[:-5] + ";"  # Remove trailing ' AND ' and add semicolon
    
    cursor.execute(prompt, tuple(searchQuery.values()))
    
    results = cursor.fetchall()
    conn.close()
    

    return results

def query_dynamic_data(searchQuery: dict, sort=False):
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

