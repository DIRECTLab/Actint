"""Aviation reference tools (countries, regions, navaids).

Backed by:
- avi_countries
- avi_regions
- avi_navaids

These helpers provide the same kind of "context lookup" capabilities that
AIS tools provide for maritime regions and ports.

All public helpers open/close their own DB connections by default.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.mcp_servers.adsb.helpers.basic_tools import bbox_from_radius_nm
from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm
from backend.data_processing.query_database import DatabaseConnectionTypes, get_conn

from backend.config import config

PH = "?" if config.DB_USING_SQLITE else "%s"

def get_country_info(code: str) -> Optional[dict[str, Any]]:
    code_n = (code or "").strip().upper()
    if not code_n:
        raise ValueError("code is required")

    sql = """
        SELECT id, code, name, continent, wikipedia_link, keywords
        FROM avi_countries
        WHERE code = {PH}
        LIMIT 1;
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (code_n,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d.name for d in cur.description]
            return dict(zip(cols, row))


def search_countries(name_contains: str, limit: int = 20) -> list[dict[str, Any]]:
    q = (name_contains or "").strip()
    if not q:
        raise ValueError("name_contains is required")

    if limit <= 0:
        limit = 20
    if limit > 200:
        limit = 200

    sql = """
        SELECT id, code, name, continent
        FROM avi_countries
        WHERE name ILIKE '%' || {PH} || '%'
        ORDER BY name ASC
        LIMIT {PH};
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (q, limit))
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_region_info(code: str) -> Optional[dict[str, Any]]:
    code_n = (code or "").strip().upper()
    if not code_n:
        raise ValueError("code is required")

    sql = """
        SELECT id, code, local_code, name, continent, iso_country, wikipedia_link, keywords
        FROM avi_regions
        WHERE code = {PH}
        LIMIT 1;
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (code_n,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d.name for d in cur.description]
            return dict(zip(cols, row))


def search_regions(name_contains: str, iso_country: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    q = (name_contains or "").strip()
    if not q:
        raise ValueError("name_contains is required")

    if limit <= 0:
        limit = 20
    if limit > 200:
        limit = 200

    sql = """
        SELECT id, code, name, continent, iso_country
        FROM avi_regions
        WHERE name ILIKE '%' || {PH} || '%'
          AND ({PH} IS NULL OR iso_country = {PH})
        ORDER BY name ASC
        LIMIT {PH};
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (q, iso_country, iso_country, limit))
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_navaid_by_ident(ident: str, limit: int = 50) -> list[dict[str, Any]]:
    """Navaid ident is not guaranteed unique; returns a list."""

    ident_n = (ident or "").strip().upper()
    if not ident_n:
        raise ValueError("ident is required")

    if limit <= 0:
        limit = 50
    if limit > 500:
        limit = 500

    sql = """
        SELECT
            id, ident, name, type, frequency_khz,
            latitude_deg, longitude_deg, elevation_ft,
            iso_country, dme_frequency_khz, dme_channel,
            associated_airport
        FROM avi_navaids
        WHERE ident = {PH}
        LIMIT {PH};
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (ident_n, limit))
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_navaids_for_airport(airport_ident: str, limit: int = 50) -> list[dict[str, Any]]:
    airport_n = (airport_ident or "").strip().upper()
    if not airport_n:
        raise ValueError("airport_ident is required")

    if limit <= 0:
        limit = 50
    if limit > 500:
        limit = 500

    sql = """
        SELECT id, ident, name, type, frequency_khz, latitude_deg, longitude_deg, iso_country
        FROM avi_navaids
        WHERE associated_airport = {PH}
        LIMIT {PH};
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (airport_n, limit))
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def find_nearest_navaids(
    lat: float,
    lon: float,
    *,
    radius_nm: float | None = 200.0,
    navaid_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if limit <= 0:
        limit = 10
    if limit > 50:
        limit = 50

    if radius_nm is None or radius_nm <= 0:
        radius_nm = 200.0

    lat_min, lat_max, lon_min, lon_max = bbox_from_radius_nm(lat, lon, float(radius_nm))
    type_q = (navaid_type or "").strip() or None

    conditions = [
        "latitude_deg BETWEEN {PH} AND {PH}",
        "longitude_deg BETWEEN {PH} AND {PH}",
    ]
    params: list[Any] = [lat_min, lat_max, lon_min, lon_max]

    if type_q:
        conditions.append("type = {PH}")
        params.append(type_q)

    params.append(20000)

    sql = f"""
        SELECT id, ident, name, type, frequency_khz,
               latitude_deg, longitude_deg, iso_country, associated_airport
        FROM avi_navaids
        WHERE {" AND ".join(conditions)}
        LIMIT {PH};
    """

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    scored: list[dict[str, Any]] = []
    for nv in rows:
        nv_lat = nv.get("latitude_deg")
        nv_lon = nv.get("longitude_deg")
        if nv_lat is None or nv_lon is None:
            continue
        d_nm = haversine_distance_nm(lat, lon, float(nv_lat), float(nv_lon))
        if d_nm > float(radius_nm):
            continue
        out = dict(nv)
        out["distance_nm"] = d_nm
        scored.append(out)

    scored.sort(key=lambda x: x["distance_nm"])
    return scored[:limit]
