import folium
import h3
import math


from backend.mcp_servers.adsb.helpers.adsb_locations import get_conn

UTAH_BBOX = {
    "min_lat": 36.5,
    "max_lat": 42.5,
    "min_lon": -114.0,
    "max_lon": -109.0
}

USA_BBOX = {
    "min_lat": 24.5,
    "max_lat": 49,
    "min_lon": -127.4,
    "max_lon": -69.6
}

SCA_BBOX = {
    "min_lat": 31.05,
    "max_lat": 31.63,
    "min_lon": -116.7,
    "max_lon": -116.4
}


def stream_segments(conn):

    with conn.cursor(name="segment_stream") as cur:

        cur.execute("""
            SELECT start_bin, end_bin, transition_count
            FROM route_segments
        """)

        while True:

            rows = cur.fetchmany(10000)

            if not rows:
                break

            for row in rows:
                yield row

# ----------------------------
# H3 conversion safety layer
# ----------------------------
def to_latlon(cell):
    """
    Accepts:
    - int (DB format)
    - str (h3 hex)
    """
    if isinstance(cell, int):
        cell = format(cell, "x")
    return h3.cell_to_latlng(cell)


# ----------------------------
# Color mapping by intensity
# ----------------------------
def get_color(count):
    """
    Transition count → color scale
    """
    if count < 10:
        return "#2c7bb6"   # blue (noise / weak flow)
    elif count < 50:
        return "#abd9e9"   # light blue
    elif count < 200:
        return "#fdae61"   # orange (corridor level)
    elif count < 1000:
        return "#d7191c"   # red (major flow)
    else:
        return "#800026"   # dark red (highways)


# ----------------------------
# Main visualization function
# ----------------------------
def visualize_route_segments(
    stream_segments,
    output_file="h3_routes.html",
    noise_floor=5,
    sample_rate=5,
    max_edges=200_000,
    center_lat=40.0,
    center_lon=-95.0,
    zoom_start=5
):
    """
    Scalable H3 segment visualizer.

    Args:
        stream_segments: generator yielding (start_bin, end_bin, trans_count)
        noise_floor: minimum traffic threshold
        sample_rate: downsampling factor (1 = no sampling)
        max_edges: hard cap on rendered edges
    """

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start)

    edges_rendered = 0
    i = 0

    for start_bin, end_bin, trans_count in stream_segments:

        i += 1

        # ----------------------------
        # sampling (scale control)
        # ----------------------------
        if sample_rate > 1 and (i % sample_rate != 0):
            continue

        # ----------------------------
        # noise floor filter
        # ----------------------------
        if trans_count < noise_floor:
            continue

        # ----------------------------
        # convert H3 → lat/lon
        # ----------------------------
        start = to_latlon(start_bin)
        end = to_latlon(end_bin)

        box = SCA_BBOX

        slat,slon = start
        if(slat > box["max_lat"] or slat < box["min_lat"]):
            continue
        if(slon > box["max_lon"] or slon < box["min_lon"]):
            continue
        

        # ----------------------------
        # visual encoding
        # ----------------------------
        color = get_color(trans_count)
        width = 1 + math.log1p(trans_count)

        folium.PolyLine(
            locations=[start, end],
            color=color,
            weight=width,
            opacity=0.6,
        ).add_to(m)

        edges_rendered += 1

        # ----------------------------
        # hard cap
        # ----------------------------
        if edges_rendered >= max_edges:
            break

    m.save(output_file)

    print(f"[DONE] Saved: {output_file}")
    print(f"[INFO] Rendered edges: {edges_rendered}")


def run():
    with get_conn() as conn:
        visualize_route_segments(
            stream_segments=stream_segments(conn),
            noise_floor=2,
            sample_rate=1,
            max_edges=150000
        )


if __name__ == "__main__":
    run()