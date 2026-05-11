"""ADS-B position history and movement analysis tools.

This module is the ADS-B analogue of `actint.tools.previous_locations` for AIS.
It focuses on retrieving position time-series from Postgres and providing
small, composable analysis helpers (e.g., following detection).

All public helpers open/close their own DB connections by default (like AIS).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from backend.mcp_servers.adsb.helpers.basic_tools import get_conn, normalize_icao, bbox_from_radius_nm, icao_to_reg
from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm, calculate_bearing


@dataclass
class AircraftPosition:
    id: int
    icao: str
    timestamp: datetime
    lat: float
    lon: float
    altitude: Optional[int] = None
    ground_speed: Optional[float] = None
    track: Optional[float] = None
    vertical_rate: Optional[int] = None
    flight_number: Optional[str] = None
    emergency: Optional[str] = None
    category: Optional[str] = None


_POSITION_COLUMNS = [
    "id",
    "icao",
    "timestamp",
    "lat",
    "lon",
    "altitude",
    "ground_speed",
    "track",
    "vertical_rate",
    "flight_number",
    "emergency",
    "category",
]


def _row_to_position(row: dict) -> AircraftPosition:
    return AircraftPosition(
        id=int(row["id"]),
        icao=str(row["icao"]),
        timestamp=row["timestamp"],
        lat=float(row["lat"]),
        lon=float(row["lon"]),
        altitude=row.get("altitude"),
        ground_speed=row.get("ground_speed"),
        track=row.get("track"),
        vertical_rate=row.get("vertical_rate"),
        flight_number=row.get("flight_number"),
        emergency=row.get("emergency"),
        category=row.get("category"),
    )


def get_vehicle_locations(
    icao: str,
    limit: int = 200,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[AircraftPosition]:
    """Get recent ADS-B positions for an aircraft.

    Returns a list sorted newest-first.
    """

    icao_n = normalize_icao(icao)
    if not icao_n:
        raise ValueError("icao is required")

    if limit <= 0:
        limit = 200
    if limit > 5000:
        limit = 5000

    where_parts: list[str] = ["icao = %s"]
    params: list[object] = [icao_n]

    if start_time is not None:
        where_parts.append("timestamp >= %s")
        params.append(start_time)

    if end_time is not None:
        where_parts.append("timestamp <= %s")
        params.append(end_time)

    sql = (
        "SELECT "
        + ", ".join(_POSITION_COLUMNS)
        + " FROM adsb_positions "
        + "WHERE "
        + " AND ".join(where_parts)
        + " ORDER BY timestamp DESC "
        + "LIMIT %s;"
    )
    params.append(limit)


    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            colnames = [d.name for d in cur.description]
            rows = [dict(zip(colnames, r)) for r in cur.fetchall()]

    return [_row_to_position(r) for r in rows]


def get_vehicle_current_position(icao: str) -> AircraftPosition | None:
    """Return the most recent ADS-B position for an aircraft."""

    positions = get_vehicle_locations(icao, limit=1)
    return positions[0] if positions else None


def get_track_summary(icao: str, lookback_hours: float = 6.0) -> dict:
    """Return simple aggregate stats for an aircraft track."""

    icao_n = normalize_icao(icao)
    if not icao_n:
        raise ValueError("icao is required")

    if lookback_hours <= 0:
        lookback_hours = 6.0

    sql = """
        SELECT
            MIN(timestamp) AS start_time,
            MAX(timestamp) AS end_time,
            COUNT(*) AS points,
            MIN(altitude) AS min_altitude,
            MAX(altitude) AS max_altitude,
            MIN(lat) AS min_lat,
            MAX(lat) AS max_lat,
            MIN(lon) AS min_lon,
            MAX(lon) AS max_lon,
            AVG(ground_speed) AS avg_ground_speed
        FROM adsb_positions
        WHERE icao = %s
          AND timestamp >= NOW() - (%s || ' hours')::interval;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (icao_n, lookback_hours))
            row = cur.fetchone()
            colnames = [d.name for d in cur.description]

    result = dict(zip(colnames, row)) if row else {}
    result["icao"] = icao_n
    return result


def _compute_direction_vector(positions_newest_first: list[AircraftPosition]) -> tuple[float, float]:
    """Compute a simple direction vector (dlat_sum, dlon_sum) from recent positions."""

    if len(positions_newest_first) < 2:
        return 0.0, 0.0

    positions = list(reversed(positions_newest_first))
    dlat_sum = 0.0
    dlon_sum = 0.0

    prev = positions[0]
    for cur in positions[1:]:
        dlat_sum += float(cur.lat) - float(prev.lat)
        dlon_sum += float(cur.lon) - float(prev.lon)
        prev = cur

    return dlat_sum, dlon_sum


def get_direction_vector_for_aircraft(icao: str, n_points: int = 50) -> tuple[float, float]:
    """Compute a direction vector for an aircraft from its last N positions."""

    if n_points < 2:
        n_points = 2
    if n_points > 2000:
        n_points = 2000

    positions = get_vehicle_locations(icao, limit=n_points)
    return _compute_direction_vector(positions)


def aircraft_following(
    leader_icao: str,
    follower_icao: str,
    threshold_time_minutes: int = 60,
    threshold_distance_nm: float = 5.0,
    lookback_hours: float = 6.0,
    max_points: int = 300,
) -> str:
    """Determine whether follower aircraft has been near leader's path.

    This mirrors the AIS `ship_following` style: count how often the follower
    was within a distance threshold of leader positions within a time window.

    Returns a human-readable analysis string.
    """

    leader = normalize_icao(leader_icao)
    follower = normalize_icao(follower_icao)
    if not leader or not follower:
        raise ValueError("leader_icao and follower_icao are required")

    if threshold_time_minutes <= 0:
        threshold_time_minutes = 60
    if threshold_distance_nm <= 0:
        threshold_distance_nm = 5.0

    if lookback_hours <= 0:
        lookback_hours = 6.0

    start_time = datetime.now().astimezone() - timedelta(hours=lookback_hours)

    leader_positions = get_vehicle_locations(leader, limit=max_points, start_time=start_time)
    follower_positions = get_vehicle_locations(follower, limit=max_points, start_time=start_time)

    window = timedelta(minutes=threshold_time_minutes)

    hits = 0
    for lp in leader_positions:
        lp_time = lp.timestamp
        close = False
        for fp in follower_positions:
            # If follower position is too old vs leader position, it won't match
            if lp_time - fp.timestamp > window:
                continue
            if fp.timestamp - lp_time > window:
                continue

            dist = haversine_distance_nm(lp.lat, lp.lon, fp.lat, fp.lon)
            if dist <= threshold_distance_nm:
                close = True
                break

        if close:
            hits += 1

    total = len(leader_positions)
    return (
        f"Aircraft {follower} was within {threshold_distance_nm:.1f} nm of {leader} "
        f"within ±{threshold_time_minutes} minutes for {hits}/{total} leader positions "
        f"over the last {lookback_hours:g} hours."
    )

def find_nearest_aircraft(
    lat: float,
    lon: float,
    *,
    lookback_hours: float = 6.0,
    radius_nm: float = 50.0,
    limit: int = 5,
) -> list[dict]:
    """Find nearest aircraft to a location using each aircraft's latest position.

    This is designed for interactive queries like "closest aircraft to airport".
    We first compute each aircraft's latest position within a time window, then
    filter down to a bbox/radius and score by haversine distance.
    """

    if limit <= 0:
        limit = 5
    if limit > 50:
        limit = 50

    if lookback_hours <= 0:
        lookback_hours = 6.0

    if radius_nm <= 0:
        radius_nm = 50.0

    lat_min, lat_max, lon_min, lon_max, wrapped = bbox_from_radius_nm(lat, lon, float(radius_nm))

    base_sql = """
        WITH ref AS (
            SELECT COALESCE(MAX(timestamp), NOW()) AS t_ref
            FROM adsb_positions
        ),
        latest AS (
            SELECT DISTINCT ON (icao)
                id, icao, timestamp, lat, lon,
                altitude, ground_speed, track, vertical_rate,
                flight_number, emergency, category
            FROM adsb_positions, ref
            WHERE timestamp >= (ref.t_ref - (%s || ' hours')::interval)
            ORDER BY icao, timestamp DESC
        )
        SELECT *
        FROM latest
        WHERE lat BETWEEN %s AND %s
    """

    if lon_min <= lon_max:
        sql = base_sql + """
          AND lon BETWEEN %s AND %s
        LIMIT 20000;
        """
        params = (float(lookback_hours), lat_min, lat_max, lon_min, lon_max)
    else:
        sql = base_sql + """
          AND (lon >= %s OR lon <= %s)
        LIMIT 20000;
        """
        params = (float(lookback_hours), lat_min, lat_max, lon_min, lon_max)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            colnames = [d.name for d in cur.description]
            rows = [dict(zip(colnames, r)) for r in cur.fetchall()]

        # Fetch identity fields cheaply for the final shortlist
        scored: list[dict] = []
        for r in rows:
            r_lat = r.get("lat")
            r_lon = r.get("lon")
            if r_lat is None or r_lon is None:
                continue

            d_nm = haversine_distance_nm(lat, lon, float(r_lat), float(r_lon))
            if d_nm > float(radius_nm):
                continue

            bearing = calculate_bearing(lat, lon, float(r_lat), float(r_lon))

            out = dict(r)
            out["distance_nm"] = d_nm
            out["bearing_deg"] = bearing
            out["reg_num"] = icao_to_reg(conn, str(r.get("icao", "")))
            scored.append(out)

    scored.sort(key=lambda x: x["distance_nm"])
    return scored[:limit]