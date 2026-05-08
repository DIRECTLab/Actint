"""
ADS-B Route Heatmap (H3) Aggregator
-----------------------------------

Goal:
Convert ADS-B flight data into a route-density heatmap.

Method:
- Use H3 (res 9) to spatially bin positions
- Sort data by ICAO + timestamp
- For each aircraft, collapse consecutive identical H3 cells
- Count ONLY cell entries (not raw messages)

Result:
Each H3 cell = number of aircraft that passed through it.

Meaning:
"traffic flow density" (routes), not message volume.

Why:
Removes ADS-B spam, holding patterns, and transmit-rate bias.

Output:
(h3_cell → traversal_count)

Pseudo code:

FOR each aircraft (icao) ordered by time:

    prev_cell = NONE
    prev_time = NONE

    FOR each ADS-B point:

        cell = H3(lat, lon, res=9)
        time = timestamp

        IF prev_time is not NONE:
            dt = time - prev_time

            IF dt < MIN_TIME_DELTA:
                CONTINUE   // optional time decimation

        IF cell == prev_cell:
            CONTINUE   // collapse spatial duplicates

        heatmap[cell] += 1   // count entry event

        prev_cell = cell
        prev_time = time

"""

from h3 import latlng_to_cell, cell_to_parent, cell_to_latlng
from collections import defaultdict
import time 
from backend.mcp_servers.adsb.helpers.basic_tools import get_conn

RES = 9
MIN_DT = 15
BATCH = 10_000
FLUSH = 20_000



def flush(table, cur, agg):
    """
    agg: dict {h3_cell(str) -> count}
    """

    rows = []

    for h3_cell, count in agg.items():

        lat_c, lon_c = cell_to_latlng(h3_cell)

        rows.append((
            int(h3_cell, 16),
            lat_c,
            lon_c,
            count
        ))

    cur.executemany(f"""
        INSERT INTO {table} (
            h3_index,
            lat_center,
            lon_center,
            traversal_count
        )
        VALUES (%s, %s, %s, %s)

        ON CONFLICT (h3_index)
        DO UPDATE SET
            traversal_count =
                {table}.traversal_count +
                EXCLUDED.traversal_count
    """, rows)



def build_heat_map():

    TABLE = "heatmap_h3_res9_routes"

    CREATE_TABLE = f"""
    CREATE TABLE IF NOT EXISTS {TABLE} (
        h3_index BIGINT PRIMARY KEY,
        lat_center DOUBLE PRECISION,
        lon_center DOUBLE PRECISION,
        traversal_count BIGINT NOT NULL
    );
    """

    CREATE_INDEX = f"""
    CREATE INDEX IF NOT EXISTS idx_{TABLE}_count
    ON {TABLE}(traversal_count DESC);
    """

    heat_map = defaultdict(int)

    last_icao = None
    last_cell = None
    last_ts = None

    rows = traversals = 0

    start = time.time()


    with get_conn() as write_conn:
        #conn.autocommit = False
        with write_conn.cursor() as cur:
            cur.execute(CREATE_TABLE)
            cur.execute(CREATE_INDEX)
        write_conn.commit()

        with get_conn() as read_conn:

            #read_conn.read_only = True

            with read_conn.cursor(name="stream") as read_cur:
                read_cur.itersize = BATCH
                read_cur.execute("""
                    SELECT icao, timestamp, lat, lon
                    FROM adsb_positions
                    WHERE lat IS NOT NULL AND lon IS NOT NULL
                    AND timestamp >= '2025-01-1'
                    AND timestamp <  '2025-12-31'
                    ORDER BY icao, timestamp
                """)


                with write_conn.cursor() as write_cur:

                    while True:
                        batch = read_cur.fetchmany(BATCH)
                        #print("batch found!")

                        if not batch:
                            break
                        
                            

                        for icao, ts, lat, lon in batch:
                            rows += 1

                            if icao != last_icao:
                                last_icao = icao
                                last_cell = None
                                last_ts = None

                            if last_ts:
                                dt = (ts - last_ts).total_seconds()

                                if dt < MIN_DT:
                                    continue

                            last_ts = ts

                            cell = latlng_to_cell(lat, lon, RES)

                            if cell == last_cell:
                                continue

                            last_cell = cell

                            heat_map[cell] += 1
                            traversals += 1

                        if len(heat_map) >= FLUSH:
                            flush(TABLE, write_cur, heat_map)
                            write_conn.commit()
                            heat_map.clear()

                            print(
                                f"{rows:,} rows | "
                                f"{traversals:,} traversals"
                            )
                    if heat_map:
                        flush(TABLE, write_cur, heat_map)
                        write_conn.commit()


    elapsed = time.time() - start

    print(
        f"DONE | "
        f"{rows:,} rows | "
        f"{traversals:,} traversals | "
        f"{elapsed:.1f}s"
    )





def build_resn_heatmap(src_res, dst_res):

    SRC_TABLE = f"heatmap_h3_res{src_res}_routes"
    DST_TABLE = f"heatmap_h3_res{dst_res}_routes"

    CREATE_TABLE = f"""
    CREATE TABLE IF NOT EXISTS {DST_TABLE} (
        h3_index BIGINT PRIMARY KEY,
        lat_center DOUBLE PRECISION,
        lon_center DOUBLE PRECISION,
        traversal_count BIGINT NOT NULL
    );
    """

    CREATE_INDEX = f"""
    CREATE INDEX IF NOT EXISTS idx_{DST_TABLE}_count
    ON {DST_TABLE}(traversal_count DESC);
    """

    start = time.time()

    rows = 0
    agg = defaultdict(int)

    # --------------------------------------------------------
    # WRITE CONNECTION
    # --------------------------------------------------------

    with get_conn() as write_conn:

        with write_conn.cursor() as cur:
            cur.execute(CREATE_TABLE)
            cur.execute(CREATE_INDEX)

        write_conn.commit()

        # ----------------------------------------------------
        # READ CONNECTION
        # ----------------------------------------------------

        with get_conn() as read_conn:

            with read_conn.cursor(name="stream") as read_cur:

                read_cur.itersize = BATCH

                read_cur.execute(f"""
                    SELECT
                        h3_index,
                        traversal_count
                    FROM {SRC_TABLE}
                """)

                with write_conn.cursor() as write_cur:

                    while True:

                        batch = read_cur.fetchmany(BATCH)

                        if not batch:
                            break

                        for h3_index, count in batch:

                            rows += 1

                            # bigint -> hex string
                            res_src_cell = hex(h3_index)[2:]

                            # parent conversion
                            res_dst_cell = cell_to_parent(
                                res_src_cell,
                                dst_res
                            )

                            agg[res_dst_cell] += count

                        # periodic flush
                        if len(agg) >= BATCH:

                            flush(DST_TABLE, write_cur, agg)
                            write_conn.commit()
                            agg.clear()

                            print(f"{rows:,} rows processed")

                    # final flush
                    if agg:

                        flush(DST_TABLE, write_cur, agg)
                        write_conn.commit()

    elapsed = time.time() - start

    print(
        f"DONE | "
        f"{rows:,} rows | "
        f"{elapsed:.1f}s"
    )


if __name__ == "__main__":
    
    build_heat_map()
    build_resn_heatmap(9,7)
    build_resn_heatmap(7,6)
    build_resn_heatmap(6,5)

# cell = latlng_to_cell(41.7355, -111.834, 9)
# print(f"cell: {cell}")