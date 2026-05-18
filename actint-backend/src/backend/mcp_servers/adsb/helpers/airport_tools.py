"""Airport / runway / frequency tools for ADS-B.

This module is the aviation analogue of AIS geographic context tools:
- nearest airport lookup (nearest port analogue)
- runway and frequency lookups
- candidate destination airports based on direction of travel

All public helpers open/close their own DB connections by default.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Optional

from backend.mcp_servers.adsb.helpers.basic_tools import (
    bbox_from_radius_nm,
    bearing_diff_deg
)
from backend.mcp_servers.adsb.helpers.adsb_locations import (
    get_direction_vector_for_aircraft,
    get_vehicle_current_position,
)
from backend.mcp_servers.utils.distance_calculation import calculate_bearing, haversine_distance_nm

from backend.data_processing.query_database import DatabaseConnectionTypes, get_conn


def get_airport_by_ident(ident: str) -> Optional[dict[str, Any]]:
    ident_n = (ident or "").strip().upper()
    if not ident_n:
        raise ValueError("ident is required")

    sql = """
        SELECT
            id, ident, type, name,
            latitude_deg, longitude_deg, elevation_ft,
            continent, country_name, iso_country,
            region_name, iso_region, local_region,
            municipality, scheduled_service,
            gps_code, icao_code, iata_code, local_code,
            home_link, wikipedia_link, keywords, score, last_updated
        FROM airports
        WHERE ident = %s
        LIMIT 1;
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (ident_n,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d.name for d in cur.description]
            return dict(zip(cols, row))


def search_airports(
    name_contains: str | None = None,
    iso_country: str | None = None,
    iso_region: str | None = None,
    municipality_contains: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if limit <= 0:
        limit = 50
    if limit > 1000:
        limit = 1000

    name_q = (name_contains or "").strip()
    muni_q = (municipality_contains or "").strip()

    sql = """
        SELECT
            id, ident, type, name,
            latitude_deg, longitude_deg,
            iso_country, iso_region,
            municipality,
            iata_code, icao_code,
            score
        FROM airports
        WHERE (%s = '' OR name ILIKE '%' || %s || '%')
          AND (%s = '' OR municipality ILIKE '%' || %s || '%')
          AND (%s IS NULL OR iso_country = %s)
          AND (%s IS NULL OR iso_region = %s)
        ORDER BY score DESC NULLS LAST, name ASC
        LIMIT %s;
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    name_q,
                    name_q,
                    muni_q,
                    muni_q,
                    iso_country,
                    iso_country,
                    iso_region,
                    iso_region,
                    limit,
                ),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_airport_runways(
    *,
    airport_ident: str | None = None,
    airport_ref: int | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    if limit <= 0:
        limit = 200
    if limit > 2000:
        limit = 2000

    ident_q = (airport_ident or "").strip().upper() if airport_ident else None

    sql = """
        SELECT
            id, airport_ref, airport_ident,
            length_ft, width_ft, surface,
            lighted, closed,
            le_ident, le_latitude_deg, le_longitude_deg, le_elevation_ft, le_heading_degt,
            he_ident, he_latitude_deg, he_longitude_deg, he_elevation_ft, he_heading_degt
        FROM runways
        WHERE (%s IS NULL OR airport_ident = %s)
          AND (%s IS NULL OR airport_ref = %s)
        ORDER BY length_ft DESC NULLS LAST
        LIMIT %s;
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (ident_q, ident_q, airport_ref, airport_ref, limit))
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_airport_frequencies(
    *,
    airport_ident: str | None = None,
    airport_ref: int | None = None,
    freq_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    if limit <= 0:
        limit = 200
    if limit > 2000:
        limit = 2000

    ident_q = (airport_ident or "").strip().upper() if airport_ident else None
    type_q = (freq_type or "").strip() if freq_type else None

    sql = """
        SELECT id, airport_ref, airport_ident, type, description, frequency_mhz
        FROM airport_frequencies
        WHERE (%s IS NULL OR airport_ident = %s)
          AND (%s IS NULL OR airport_ref = %s)
          AND (%s IS NULL OR type = %s)
        ORDER BY type ASC, frequency_mhz ASC
        LIMIT %s;
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (ident_q, ident_q, airport_ref, airport_ref, type_q, type_q, limit))
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def find_nearest_airport(
    lat: float,
    lon: float,
    *,
    limit: int = 5,
    max_distance_nm: float | None = None,
) -> list[dict[str, Any]]:
    """Find nearest airports to a location.

    Uses a bbox prefilter in SQL and refines distance with haversine.
    """

    if limit <= 0:
        limit = 5
    if limit > 50:
        limit = 50

    prefilter_nm = max_distance_nm if (max_distance_nm and max_distance_nm > 0) else 500.0
    lat_min, lat_max, lon_min, lon_max = bbox_from_radius_nm(lat, lon, prefilter_nm)

    sql = """
        SELECT
            id, ident, type, name,
            latitude_deg, longitude_deg,
            iso_country, iso_region,
            municipality, iata_code, icao_code
        FROM airports
        WHERE latitude_deg BETWEEN %s AND %s
          AND longitude_deg BETWEEN %s AND %s
        LIMIT 5000;
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (lat_min, lat_max, lon_min, lon_max))
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    scored: list[dict[str, Any]] = []
    for ap in rows:
        d_nm = haversine_distance_nm(lat, lon, float(ap["latitude_deg"]), float(ap["longitude_deg"]))
        if max_distance_nm is not None and max_distance_nm > 0 and d_nm > max_distance_nm:
            continue
        ap2 = dict(ap)
        ap2["distance_nm"] = d_nm
        ap2["bearing_deg"] = calculate_bearing(lat, lon, float(ap["latitude_deg"]), float(ap["longitude_deg"]))
        scored.append(ap2)

    scored.sort(key=lambda x: x["distance_nm"])
    return scored[:limit]


def _bearing_from_vector(direction_vector: tuple[float, float]) -> float:
    """Compute bearing (deg) from a (dlat, dlon) direction vector."""

    dlat, dlon = direction_vector
    if dlat == 0 and dlon == 0:
        return 0.0

    # Bearing from North: atan2(east, north)
    deg = math.degrees(math.atan2(dlon, dlat))
    return (deg + 360.0) % 360.0


def get_possible_airport_destinations(
    lat: float,
    lon: float,
    direction_vector: tuple[float, float],
    *,
    radius_nm: float = 300.0,
    tolerance_deg: float = 15.0,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return candidate airports in the direction of travel.

    This is analogous to AIS `get_possible_destinations`, but over `airports`.
    """

    if radius_nm <= 0:
        radius_nm = 300.0
    if tolerance_deg <= 0:
        tolerance_deg = 15.0
    if limit <= 0:
        limit = 10
    if limit > 50:
        limit = 50

    heading = _bearing_from_vector(direction_vector)

    lat_min, lat_max, lon_min, lon_max = bbox_from_radius_nm(lat, lon, radius_nm)

    sql = """
        SELECT id, ident, name, type, latitude_deg, longitude_deg, iso_country, iso_region, municipality
        FROM airports
        WHERE latitude_deg BETWEEN %s AND %s
          AND longitude_deg BETWEEN %s AND %s
        LIMIT 10000;
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (lat_min, lat_max, lon_min, lon_max))
            cols = [d.name for d in cur.description]
            airports = [dict(zip(cols, r)) for r in cur.fetchall()]

    candidates: list[dict[str, Any]] = []
    for ap in airports:
        ap_lat = float(ap["latitude_deg"])
        ap_lon = float(ap["longitude_deg"])
        dist_nm = haversine_distance_nm(lat, lon, ap_lat, ap_lon)
        if dist_nm > radius_nm:
            continue

        brg = calculate_bearing(lat, lon, ap_lat, ap_lon)
        if bearing_diff_deg(brg, heading) > tolerance_deg:
            continue

        out = dict(ap)
        out["distance_nm"] = dist_nm
        out["bearing_deg"] = brg
        out["heading_deg"] = heading
        candidates.append(out)

    candidates.sort(key=lambda x: x["distance_nm"])
    return candidates[:limit]


def get_possible_airport_destinations_for_aircraft(
    icao: str,
    *,
    n_points: int = 50,
    radius_nm: float = 300.0,
    tolerance_deg: float = 15.0,
    limit: int = 10,
) -> dict[str, Any]:
    """Convenience wrapper: compute direction vector from ADS-B track, then suggest airports."""

    current = get_vehicle_current_position(icao)
    if current is None:
        return {"error": f"No positions found for icao={icao}"}

    direction = get_direction_vector_for_aircraft(icao, n_points=n_points)
    candidates = get_possible_airport_destinations(
        current.lat,
        current.lon,
        direction,
        radius_nm=radius_nm,
        tolerance_deg=tolerance_deg,
        limit=limit,
    )

    return {
        "icao": current.icao,
        "current_position": asdict(current),
        "direction_vector": {"dlat": direction[0], "dlon": direction[1]},
        "candidates": candidates,
    }
