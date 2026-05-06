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
    bearing_diff_deg,
    get_conn,
)
from backend.mcp_servers.adsb.helpers.adsb_locations import (
    get_direction_vector_for_aircraft,
    get_vehicle_current_position,
)
from backend.mcp_servers.utils.distance_calculation import calculate_bearing, haversine_distance_nm


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

    with get_conn() as conn:
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
    iso_country_q = (iso_country or "").strip().upper()
    iso_region_q = (iso_region or "").strip().upper()

    # Be forgiving: callers often confuse iso_region with iso_country (e.g., pass "US").
    # Airports use ISO 3166-2 style region codes like "US-UT".
    if iso_country_q and len(iso_country_q) != 2:
        iso_country_q = ""
    if iso_region_q and "-" not in iso_region_q:
        iso_region_q = ""

    sql = """
        SELECT
            id, ident, type, name,
            latitude_deg, longitude_deg,
            iso_country, iso_region,
            municipality,
            iata_code, icao_code,
            score
        FROM airports
        WHERE (%s = '' OR name ILIKE '%%' || %s || '%%')
          AND (%s = '' OR municipality ILIKE '%%' || %s || '%%')
                    AND (%s = '' OR iso_country = %s)
                    AND (%s = '' OR iso_region = %s)
        ORDER BY score DESC NULLS LAST, name ASC
        LIMIT %s;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    name_q,
                    name_q,
                    muni_q,
                    muni_q,
                    iso_country_q,
                    iso_country_q,
                    iso_region_q,
                    iso_region_q,
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

    ident_q = (airport_ident or "").strip().upper()

    sql = """
        SELECT
            id, airport_ref, airport_ident,
            length_ft, width_ft, surface,
            lighted, closed,
            le_ident, le_latitude_deg, le_longitude_deg, le_elevation_ft, le_heading_degt,
            he_ident, he_latitude_deg, he_longitude_deg, he_elevation_ft, he_heading_degt
        FROM runways
                WHERE (%s = '' OR airport_ident = %s)
                    AND (%s::int IS NULL OR airport_ref = %s)
        ORDER BY length_ft DESC NULLS LAST
        LIMIT %s;
    """

    with get_conn() as conn:
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

    ident_q = (airport_ident or "").strip().upper()
    type_q = (freq_type or "").strip()

    sql = """
        SELECT id, airport_ref, airport_ident, type, description, frequency_mhz
        FROM airport_frequencies
                WHERE (%s = '' OR airport_ident = %s)
                    AND (%s::int IS NULL OR airport_ref = %s)
                    AND (%s = '' OR type = %s)
        ORDER BY type ASC, frequency_mhz ASC
        LIMIT %s;
    """

    with get_conn() as conn:
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

    Uses DB-side distance ordering (efficient) and supports dateline wraparound.
    If `max_distance_nm` is not provided, it expands the search radius until at least
    one airport is found.
    """

    if limit <= 0:
        limit = 5
    if limit > 50:
        limit = 50


    # Earth mean radius in nautical miles
    earth_radius_nm = 3440.065

    with get_conn() as conn:
        def _query(radius_nm: float) -> list[dict[str, Any]]:
            lat_min, lat_max, lon_min, lon_max = bbox_from_radius_nm(lat, lon, radius_nm)

            base_query = """
                SELECT
                    id,
                    ident,
                    type,
                    name,
                    latitude_deg,
                    longitude_deg,
                    iso_country,
                    iso_region,
                    municipality,
                    iata_code,
                    icao_code,
                    (%s * acos(
                        LEAST(1, GREATEST(-1,
                            cos(radians(%s)) *
                            cos(radians(latitude_deg)) *
                            cos(radians(longitude_deg) - radians(%s)) +
                            sin(radians(%s)) *
                            sin(radians(latitude_deg))
                        ))
                    )) AS distance_nm
                FROM airports
                WHERE latitude_deg IS NOT NULL
                  AND longitude_deg IS NOT NULL
                  AND type != 'closed'
                  AND latitude_deg BETWEEN %s AND %s
            """

            params: list[Any] = [earth_radius_nm, lat, lon, lat, lat_min, lat_max]

            if lon_min <= lon_max:
                query = base_query + """
                  AND longitude_deg BETWEEN %s AND %s
                ORDER BY distance_nm ASC
                LIMIT %s;
                """
                params.extend([lon_min, lon_max, limit])
            else:
                query = base_query + """
                  AND (longitude_deg >= %s OR longitude_deg <= %s)
                ORDER BY distance_nm ASC
                LIMIT %s;
                """
                params.extend([lon_min, lon_max, limit])

            with conn.cursor() as cur:
                cur.execute(query, params)
                cols = [d.name for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]

            for r in rows:
                try:
                    r["bearing_deg"] = calculate_bearing(
                        lat, lon, float(r["latitude_deg"]), float(r["longitude_deg"])
                    )
                except Exception:
                    r["bearing_deg"] = None
            return rows

        if max_distance_nm is not None and max_distance_nm > 0:
            return _query(float(max_distance_nm))

        radius_nm = 15.0
        max_radius_nm = 3000.0
        while radius_nm <= max_radius_nm:
            rows = _query(radius_nm)
            if rows:
                return rows
            radius_nm *= 2.0

    return []


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

    base_sql = """
        SELECT id, ident, name, type, latitude_deg, longitude_deg, iso_country, iso_region, municipality
        FROM airports
        WHERE latitude_deg BETWEEN %s AND %s
    """

    if lon_min <= lon_max:
        sql = base_sql + """
          AND longitude_deg BETWEEN %s AND %s
        LIMIT 10000;
        """
        params: tuple[Any, ...] = (lat_min, lat_max, lon_min, lon_max)
    else:
        sql = base_sql + """
          AND (longitude_deg >= %s OR longitude_deg <= %s)
        LIMIT 10000;
        """
        params = (lat_min, lat_max, lon_min, lon_max)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
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
