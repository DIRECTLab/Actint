import json

from backend.mcp_servers.ais.helpers.vessel_query import get_vessel_position_history_helper, query_static_data_helper, get_all_latest_detections_helper
from backend.config import config
import psycopg
from backend.dark_vessels.data.gfw.regions.region_coordinates import region_evaluator
from backend.dark_vessels.data.gfw.ship_types import AIS_COUNTRY_CODES, AIS_VESSEL_TYPE_CODES


def _connect_to_suspicious_db():
    try:
        # Read environment variables
        db_config = {
            "host": config.DB_HOST,
            "dbname": config.SUS_VESSELS_DB_NAME,
            "user": config.DB_USER,
            "password": config.DB_PASS,
            "port": config.DB_PORT,
        }
        # Validate required vars
        for key, value in db_config.items():
            if value is None:
                raise ValueError(f"Missing environment variable: {key}")
            
        # Connect
        conn = psycopg.connect(**db_config)
        return conn
        
    except Exception as e:
        print("Error:")
        print(e)


def _get_suspicious_tables():
    conn = _connect_to_suspicious_db()
    cursor = conn.cursor()
    # Get all region tables

    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
    """)
    tables = cursor.fetchall()
    conn.close()
    return [table[0] for table in tables]
\

def get_ais_in_region(region: str):
    
    latest_locations = get_all_latest_detections_helper()
    vessels_in_region_data = []
    for vessel in latest_locations:
        lat = vessel['lat']
        lon = vessel['lon']
        vessel_region = region_evaluator.evaluate_region(lat, lon)
        if vessel_region == region:
            static_data = query_static_data_helper({'mmsi': vessel['mmsi']})
            position_history = get_vessel_position_history_helper(vessel['mmsi'])
            vessels_in_region_data.append({
                "static_data": static_data,
                "dynamic_data": position_history
            })
    return vessels_in_region_data




def prepare_data_for_ML(data):
    """This will be the function that converts the AIS data from the database into AIS data that we can feed into the ML machine. We will needd to somehow define a true_activity"""
    # print(data)
    prepared_ship_data = []
    for ship in data:
        static_data = ship["static_data"][0]
        dynamic_data = ship["dynamic_data"]
        print("static data:",static_data)

        ship_detection_objects = []
        for detection in dynamic_data:
            ship_detection_objects.append({
                "mmsi": static_data['mmsi'],
                "vessel_type_code": static_data["vesseltype"],
                "vessel_type_key": AIS_VESSEL_TYPE_CODES.get(static_data["vesseltype"], "Unknown"),
                "timestamp": detection["basedatetime"],
                "lat": detection["lat"],
                "lon": detection["lon"],
                "sog": detection["sog"],
                "cog": detection["cog"],
                "heading": detection["heading"],
                "nav_status": detection["status"],
                "length": static_data["length"],
                "width": static_data["width"],
                "draught": static_data["draft"],
                "name": static_data["vesselname"],
                "flag": AIS_COUNTRY_CODES.get(static_data["origincountry"], "Unknown"),
                "ais_on": True,
                "true_activity": None,
                "had_dark_period": None,
                # We will need to assign true_activity and had_dark_period based on the data we have
            })
        prepared_ship_data.extend(ship_detection_objects)

        return prepared_ship_data


def edit_create_sus_vessels(static_data, latest_detection, reasons_sus):
    region = region_evaluator.evaluate_region(latest_detection['lat'], latest_detection['lon'])
    conn = _connect_to_suspicious_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {region} (
            mmsi INTEGER PRIMARY KEY,
            reasons_sus JSONB,
            latest_sus_time TIMESTAMP,
            latest_sus_lat FLOAT,
            latest_sus_lon FLOAT,
            latest_sus_sog FLOAT,
            latest_sus_cog FLOAT,
            latest_sus_heading FLOAT,
            latest_sus_status TEXT,
            latest_sus_cargo TEXT,
            vesselname TEXT,
            imo TEXT,
            vesseltype TEXT,
            length FLOAT,
            width FLOAT,
            draft FLOAT,
            cargo TEXT,
            first_seen TIMESTAMP
        )
    """)
    cursor.execute(f"SELECT * FROM {region} WHERE mmsi = %s", (static_data['mmsi'],))
    results = cursor.fetchone()
    if results:
        # Edit the existing entry
        cursor.execute(f"""
            UPDATE {region} SET
                reasons_sus = %s,
                latest_sus_time = %s,
                latest_sus_lat = %s,
                latest_sus_lon = %s,
                latest_sus_sog = %s,
                latest_sus_cog = %s,
                latest_sus_heading = %s,
                latest_sus_status = %s,
                latest_sus_cargo = %s
            WHERE mmsi = %s
        """, (
            json.dumps(reasons_sus),
            latest_detection['basedatetime'],
            latest_detection['lat'],
            latest_detection['lon'],
            latest_detection['sog'],
            latest_detection['cog'],
            latest_detection['heading'],
            latest_detection['status'],
            latest_detection['cargo'],
            static_data['mmsi'],
        ))
    else:
        # Create a new entry
        cursor.execute(f"""
            INSERT INTO {region} (
                mmsi,
                reasons_sus,
                latest_sus_time,
                latest_sus_lat,
                latest_sus_lon,
                latest_sus_sog,
                latest_sus_cog,
                latest_sus_heading,
                latest_sus_status,
                latest_sus_cargo,
                vesselname,
                imo,
                vesseltype,
                length,
                width,
                draft,
                cargo,
                first_seen
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            latest_detection['mmsi'],
            json.dumps(reasons_sus),
            latest_detection['basedatetime'],
            latest_detection['lat'],
            latest_detection['lon'],
            latest_detection['sog'],
            latest_detection['cog'],
            latest_detection['heading'],
            latest_detection['status'],
            latest_detection['cargo'],
            static_data['vesselname'],
            static_data['imo'],
            static_data['vesseltype'],
            static_data['length'],
            static_data['width'],
            static_data['draft'],
            static_data['cargo'],
            static_data['first_seen'],
        ))

    conn.commit()
    conn.close()


def remove_suspicious_vessel(mmsi: int):
    conn = _connect_to_suspicious_db()
    cursor = conn.cursor()

    tables = _get_suspicious_tables()
    for (table,) in tables:
        cursor.execute(f"DELETE FROM {table} WHERE mmsi = %s", (mmsi,))

    conn.commit()
    conn.close()
    return 



if __name__ == "__main__":
    from backend.mcp_servers.ais.helpers.vessel_query import query_static_data_helper, get_vessel_latest_location_helper
    
    static_data = query_static_data_helper({'mmsi': 209641000})[0]
    # print(static_data)
    latest_detection = get_vessel_latest_location_helper(209641000)

    # edit_create_sus_vessels(static_data, latest_detection, "Pacific_Ocean", "illegal fishing")
    



# reference_data_structure_for_ML = {
#             "mmsi": mmsi,
#             "vessel_type_key": vessel_key,                                  This can derived from vessel_type_code
#             "vessel_type_code": tmpl["type_code"],
#             "timestamp": t,
#             "lat": round(lat + RNG.normal(0, 0.0002), 5),
#             "lon": round(lon + RNG.normal(0, 0.0002), 5),
#             "sog": round(reported_sog, 1),
#             "cog": round(reported_cog, 1),
#             "heading": round(reported_cog + RNG.normal(0, 2), 1) % 360,
#             "nav_status": nav_status,                                       just status in dynamic data
#             "length": int(length),
#             "width": int(width),
#             "draught": draught,                                             Equal to the draft
#             "name": name,
#             "flag": flag,                                                   can be derived from the origin country
#             "ais_on": True,
#             "true_activity": phase,                                         This must be assigned
#             "had_dark_period": len(dark_segments) > 0,                      This must be derived from the AIS data
#         }