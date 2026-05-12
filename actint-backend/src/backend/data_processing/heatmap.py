
import psycopg
from backend.mcp_servers.adsb.helpers.basic_tools import get_conn

def fetch_heatmap():
    with get_conn() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("""
                SELECT lat_center, lon_center, traversal_count
                FROM heatmap_h3_res6_routes
            """)
            rows = cur.fetchall()

    if not rows:
        return []

    # compute max once
    max_val = max(r["traversal_count"] for r in rows)

    if max_val <= 0:
        return []

    NOISE_FLOOR = 200/max_val #if a bin has less than n planes ignore it
    NOISE_CEILING = 0.75 #trying to get rid of hot spots for visualization

    points = []

    for r in rows:
        intensity = r["traversal_count"] / max_val

        # apply noise floor AFTER normalization
        if intensity < NOISE_FLOOR or intensity > NOISE_CEILING:
            continue

        points.append([
            r["lat_center"],
            r["lon_center"],
            intensity
        ])

    return points

if __name__ == "__main__":
    result = fetch_heatmap()
    points = result
    print(result)