import folium

from backend.mcp_servers.adsb.helpers.basic_tools import get_conn


UTAH_BBOX = {
    "min_lat": 36.5,
    "max_lat": 42.5,
    "min_lon": -114.0,
    "max_lon": -109.0
}

USA_BBOX = {
    "min_lat": 24.5,
    "max_lat": 49.0,
    "min_lon": -127.4,
    "max_lon": -69.6
}

SCA_BBOX = {
    "min_lat": 31.05,
    "max_lat": 31.63,
    "min_lon": -116.7,
    "max_lon": -116.4
}


# -----------------------------
# DB STREAM
# -----------------------------
def stream_segments(conn):
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


# -----------------------------
# GEOMETRY HELPERS
# -----------------------------
def in_bbox(lat, lon, bbox):
    return (
        bbox["min_lat"] <= lat <= bbox["max_lat"]
        and bbox["min_lon"] <= lon <= bbox["max_lon"]
    )


def normalize_lon(lon):
    """
    Normalize longitude into [-180, 180].
    """
    return ((lon + 180) % 360) - 180


def split_dateline_segment(start_lat, start_lon, end_lat, end_lon):
    """
    Splits segments that cross the ±180° meridian.
    Returns list of (start, end) coordinate pairs.
    """

    start_lon = normalize_lon(start_lon)
    end_lon = normalize_lon(end_lon)

    diff = abs(start_lon - end_lon)

    # No dateline crossing
    if diff <= 180:
        return [((start_lat, start_lon), (end_lat, end_lon))]

    # Crossing detected → split
    if start_lon > end_lon:
        return [
            ((start_lat, start_lon), (start_lat, 180.0)),
            ((end_lat, -180.0), (end_lat, end_lon))
        ]
    else:
        return [
            ((start_lat, start_lon), (start_lat, -180.0)),
            ((end_lat, 180.0), (end_lat, end_lon))
        ]


# -----------------------------
# VISUALIZATION
# -----------------------------
def visualize_route_segments(
    stream_segments,
    output_file="ats_routes.html",
    max_edges=500_000,
    center_lat=39.5,
    center_lon=-98.35,
    zoom_start=5,
    bbox_filter=None
):
    """
    Visualize ATS route segments with dateline-safe rendering.
    """

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles="CartoDB positron"
    )

    edges_rendered = 0

    for (
        route_ident,
        start_lat,
        start_lon,
        end_lat,
        end_lon
    ) in stream_segments:

        try:
            start_lat = float(start_lat)
            start_lon = float(start_lon)
            end_lat = float(end_lat)
            end_lon = float(end_lon)
        except (TypeError, ValueError):
            continue

        # -----------------------------
        # Optional bounding box filter
        # -----------------------------
        if bbox_filter is not None:
            if not (
                in_bbox(start_lat, start_lon, bbox_filter)
                or in_bbox(end_lat, end_lon, bbox_filter)
            ):
                continue

        # -----------------------------
        # Dateline-safe segmentation
        # -----------------------------
        segments = split_dateline_segment(
            start_lat, start_lon,
            end_lat, end_lon
        )

        for seg in segments:

            folium.PolyLine(
                locations=[seg[0], seg[1]],
                color="#ff5500",
                weight=2,
                opacity=0.7,
                tooltip=route_ident
            ).add_to(m)

        edges_rendered += 1

        if edges_rendered >= max_edges:
            break

    m.save(output_file)

    print(f"[DONE] Saved: {output_file}")
    print(f"[INFO] Rendered edges: {edges_rendered}")


# -----------------------------
# ENTRY POINT
# -----------------------------
def run():

    with get_conn() as conn:

        visualize_route_segments(
            stream_segments=stream_segments(conn),
            output_file="ats_routes.html",
            max_edges=500_000,
            center_lat=39.5,
            center_lon=-98.35,
            zoom_start=5,
            bbox_filter=None
        )


if __name__ == "__main__":
    run()