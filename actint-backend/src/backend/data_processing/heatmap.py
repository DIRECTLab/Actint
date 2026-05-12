
import psycopg
from backend.mcp_servers.adsb.helpers.basic_tools import get_conn

def fetch_heatmap():
    
    with get_conn() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("""
                SELECT lat, lon, intensity
                FROM heatmap_h3_res5_routes
            """)

            rows = cur.fetchall()

    points = [[r["lat"], r["lon"], r["intensity"]] for r in rows]
    max_val = max((r["intensity"] for r in rows), default=1)

    return points, max_val