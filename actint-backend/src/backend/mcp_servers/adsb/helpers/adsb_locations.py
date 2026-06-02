"""ADS-B position history and movement analysis tools.

This module is the ADS-B analogue of `actint.tools.previous_locations` for AIS.
It focuses on retrieving position time-series from Postgres and providing
small, composable analysis helpers (e.g., following detection).

All public helpers open/close their own DB connections by default (like AIS).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.mcp_servers.adsb.helpers.basic_tools import normalize_icao
from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm

from backend.data_processing.query_database import DatabaseConnectionTypes, get_conn

_DEFAULT_LOOKBACK_MONTHS = 6  # change to 1 when live data is flowing


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

    Always applies a time lower-bound so Postgres can prune partitions
    on the partitioned adsb_positions table.
    """

    icao_n = normalize_icao(icao)
    if not icao_n:
        raise ValueError("icao is required")

    if limit <= 0:
        limit = 200
    if limit > 5000:
        limit = 5000

    from datetime import timezone

    effective_start = start_time or (
        datetime.now(tz=timezone.utc) - timedelta(days=30 * lookback_months)
    )

    params: list[Any] = [icao_n, effective_start]

    end_clause = ""
    if end_time:
        end_clause = " AND timestamp <= %s"
        params.append(end_time)

    params.append(limit)

    query = (
        "SELECT " + ", ".join(_POSITION_COLUMNS) +
        " FROM adsb_positions"
        " WHERE icao = %s"
        " AND timestamp >= %s"
        + end_clause +
        " ORDER BY timestamp DESC"
        " LIMIT %s;"
    )

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
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

    query = """
        SELECT
            MIN(timestamp)    AS start_time,
            MAX(timestamp)    AS end_time,
            COUNT(*)          AS points,
            MIN(altitude)     AS min_altitude,
            MAX(altitude)     AS max_altitude,
            MIN(lat)          AS min_lat,
            MAX(lat)          AS max_lat,
            MIN(lon)          AS min_lon,
            MAX(lon)          AS max_lon,
            AVG(ground_speed) AS avg_ground_speed
        FROM adsb_positions
        WHERE icao = %s
          AND timestamp >= NOW() - make_interval(hours => %s);
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (icao_n, lookback_hours))
            colnames = [d.name for d in cur.description]
            row = cur.fetchone()

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
