from h3 import latlng_to_cell
from alive_progress import alive_bar

from backend.mcp_servers.adsb.helpers.adsb_locations import get_conn

RES = 7

def ensure_h3_column(conn):

    with conn.cursor() as cur:

        cur.execute("""
            ALTER TABLE airports
            ADD COLUMN IF NOT EXISTS h3_index BIGINT;
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_airports_h3
            ON airports(h3_index);
        """)

    conn.commit()


def update_airport_h3_indexes():

    with get_conn() as conn:

        print("Ensuring schema...")

        ensure_h3_column(conn)

        with conn.cursor() as cur:

            cur.execute("""
                SELECT
                    id,
                    latitude_deg,
                    longitude_deg
                FROM airports
                WHERE latitude_deg IS NOT NULL
                  AND longitude_deg IS NOT NULL;
            """)

            airports = cur.fetchall()

        print(f"Loaded {len(airports)} airports")

        updates = []

        with alive_bar(len(airports), title="Computing H3 Cells") as bar:

            for airport_id, lat, lon in airports:

                try:
                    h3_cell = latlng_to_cell(lat, lon, RES)

                    # convert H3 hex string -> BIGINT
                    h3_index = int(h3_cell, 16)

                    updates.append((
                        h3_index,
                        airport_id
                    ))

                except Exception as e:
                    print(f"Failed airport {airport_id}: {e}")

                bar()

        print("Updating database...")

        with conn.cursor() as cur:

            cur.executemany("""
                UPDATE airports
                SET h3_index = %s
                WHERE id = %s;
            """, updates)

        conn.commit()

        print(f"Updated {len(updates)} airports")


if __name__ == "__main__":
    update_airport_h3_indexes()