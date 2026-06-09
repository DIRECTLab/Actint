from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm, calculate_bearing, bearing_to_cardinal, get_cross_track_distance, rdp 

"""
tools to make:
    find_closest_segment(lat, lon)
    find_best_fit_segment(list of lat, lon points or adsb messages)
    predict next segment(previous_segment, list of adsb messages)
    
"""

def stream_ats_segments(conn):
    """
    Streams ATS route segments by joining route start/end points.
    """

    with conn.cursor(name="route_stream") as cur:

        cur.execute("""
            SELECT
                r.ident,
                sp.latitude  AS start_lat,
                sp.longitude AS start_lon,
                ep.latitude  AS end_lat,
                ep.longitude AS end_lon
            FROM ats_routes r
            JOIN ats_designated_points sp
                ON sp.global_id = r.startpt_id
            JOIN ats_designated_points ep
                ON ep.global_id = r.endpt_id
            WHERE
                sp.latitude IS NOT NULL
                AND sp.longitude IS NOT NULL
                AND ep.latitude IS NOT NULL
                AND ep.longitude IS NOT NULL
        """)

        while True:
            rows = cur.fetchmany(10000)
            if not rows:
                break
            for row in rows:
                yield row

