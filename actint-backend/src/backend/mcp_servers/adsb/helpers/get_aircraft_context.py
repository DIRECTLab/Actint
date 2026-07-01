#return the aircraft table line for a given ICAO

from backend.mcp_servers.adsb.helpers.basic_tools import get_conn, normalize_icao
import json


def get_aircraft_context(icao: str) -> str:
    """Get context information about an aircraft including registration number, aircraft description, and more
    
    Args:
        icao (str): icao of the aircraft
    
    Returns:
        str: JSON with context result including icao, registration, type, description, several T/F flags, first seen and last seen timestamps 
    """
    try:
        icao_n = normalize_icao(icao)
        if not icao_n:
            return json.dumps({"error": "icao is required"})

        query = """
            SELECT icao, reg_num, type, description, db_flags, military, first_seen, last_seen
            FROM aircraft
            WHERE icao = %s
            LIMIT 1;
        """

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (icao_n,))
                row = cur.fetchone()

        if not row:
            return json.dumps({"error": f"icao {icao} not found in database"})

        result = {
            "icao": row[0],
            "reg_num": row[1],
            "type": row[2],
            "description": row[3],
            "military": row[5],
            "interesting": True if (row[4] & 2) else False,
            "pia": True if (row[4] & 4) else False,
            "ladd": True if (row[4] & 8) else False,
            "first_seen": row[6].isoformat() if row[6] else None,
            "last_seen": row[7].isoformat() if row[7] else None,
        }

        return json.dumps(result, indent=2)
    
    except Exception as e:
        return json.dumps({"error": str(e)})




if __name__ == "__main__":
    print("testing")
    test1 = get_aircraft_context('ac1988') #test case
    test2 = get_aircraft_context('06a088') #test case
    test3 = get_aircraft_context('7cad400') #test case

    print(f"test1: {test1}")
    print(f"test2: {test2}")
    print(f"test3: {test3}")