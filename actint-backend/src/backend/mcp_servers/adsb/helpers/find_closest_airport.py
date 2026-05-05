"""
given a lat long find the closest airport
"""

from actint.tools.ADSB.basic_tools import get_conn

import math

# --- Helpers ---

def normalize_lon(lon):
    """Normalize longitude to [-180, 180]"""
    return ((lon + 180) % 360) - 180


def km_to_bounding_box(lat, lon, radius_km):
    """
    Convert radius (km) to a bounding box in degrees.
    Handles pole behavior and longitude scaling.
    """

    # Latitude: ~111 km per degree
    lat_delta = radius_km / 111.0

    # Longitude shrinks with latitude
    cos_lat = math.cos(math.radians(lat))
    cos_lat = max(cos_lat, 0.01)  # prevent blow-up near poles

    lon_delta = radius_km / (111.0 * cos_lat)

    lat_min = max(-90, lat - lat_delta)
    lat_max = min(90, lat + lat_delta)

    lon_min = normalize_lon(lon - lon_delta)
    lon_max = normalize_lon(lon + lon_delta)

    
    #print(f"https://bboxfinder.com/#{lat_min},{lon_min},{lat_max},{lon_max}") #testing bounding box website

    return lat_min, lat_max, lon_min, lon_max


# --- Core Query ---

def find_nearest_airport(conn, lat, lon, radius_km=10):
    """
    Find nearest airport within a bounding box.
    Returns None if nothing found in radius.
    """

    if not conn:
        conn = get_conn()

    lat_min, lat_max, lon_min, lon_max = km_to_bounding_box(lat, lon, radius_km)

    base_query = """
    SELECT
        id,
        ident,
        type,
        name,
        latitude_deg,
        longitude_deg,
        6371000 * acos(
            LEAST(1, GREATEST(-1,
                cos(radians(%s)) *
                cos(radians(latitude_deg)) *
                cos(radians(longitude_deg) - radians(%s)) +
                sin(radians(%s)) *
                sin(radians(latitude_deg))
            ))
        ) AS distance_m
    FROM airports
    WHERE latitude_deg IS NOT NULL
      AND longitude_deg IS NOT NULL
      AND type != 'closed'
      AND latitude_deg BETWEEN %s AND %s
    """

    params = [lat, lon, lat, lat_min, lat_max]

    # --- Longitude filtering with wraparound handling ---

    if lon_min <= lon_max:
        # Normal case (no wrap)
        query = base_query + """
        AND longitude_deg BETWEEN %s AND %s
        ORDER BY distance_m
        LIMIT 1;
        """
        params.extend([lon_min, lon_max])

    else:
        # Wraparound case (crosses ±180)
        query = base_query + """
        AND (
            longitude_deg >= %s
            OR longitude_deg <= %s
        )
        ORDER BY distance_m
        LIMIT 1;
        """
        params.extend([lon_min, lon_max])

    with conn.cursor() as cur:
        cur.execute(query, params)
        row = cur.fetchone()

        if not row:
            return None

        columns = [desc[0] for desc in cur.description]
        return dict(zip(columns, row))


# --- wrapper function ---

def find_nearest_airport_with_expansion(conn, lat, lon):
    """
    nearest airport search using adaptive radius.
    """

    radius_km = 25  

    while radius_km <= 5000:
        result = find_nearest_airport(conn, lat, lon, radius_km)
        if result:
            return result
        radius_km *= 2

    return None


if __name__ == "__main__":
    print("testing")

    with get_conn() as conn:

        #result0 = find_nearest_airport_with_expansion(conn, 0, 0)
        result1 = find_nearest_airport_with_expansion(conn, 40.7883933,-111.9777733) #SLC airport
        #result2 = find_nearest_airport_with_expansion(conn, 27.684200463265817, -137.1297917253547) #point in the pacific
        #result3 = find_nearest_airport_with_expansion(conn, 19.608802917606038, -153.28811363727246) #east coast of hawaii
        #result4 = find_nearest_airport_with_expansion(conn, 47.685470076427286, 0.003324845968570514) #La fleche franch
        #result5 = find_nearest_airport_with_expansion(conn, -18.55674848151163, -179.9304579598385) #east of fiji over long change
        #result6 = find_nearest_airport_with_expansion(conn, -84.79658541635872, -31.973987400773126) #antarctica 

        #print(f"result1: {result0}")
        print(f"result1: {result1}")
        #print(f"result2: {result2}")
        #print(f"result3: {result3}")
        #print(f"result4: {result4}")
        #print(f"result5: {result5}")
        #print(f"result6: {result6}")