"""Condensed MCP Server for ADS-B Aircraft Intelligence Tools.

Goal: reduce tool count + response bloat while keeping the core workflows usable
in 1 call (or at most 2) for the LLM.

This server is intended for testing alongside the existing ADS-B server.
It reuses existing helper functions but projects results into compact schemas.

Core tools exposed:
- say_hello
- get_aircraft_context
- get_aircraft_track
- analyze_aircraft_following
- find_nearby
- get_airport_context
- search_airports
- query_adsb (preset-first)

Environment variables required for DB access (via helpers):
- DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Iterable

from fastmcp import FastMCP

from backend.mcp_servers.adsb.helpers.adsb_locations import (
    aircraft_following,
    find_nearest_aircraft,
    get_track_summary,
    get_vehicle_current_position,
    get_vehicle_locations,
)
from backend.mcp_servers.adsb.helpers.airport_tools import (
    find_nearest_airport,
    get_airport_by_ident,
    get_airport_frequencies,
    get_airport_runways,
    search_airports,
)
from backend.mcp_servers.adsb.helpers.avi import find_nearest_navaids
from backend.mcp_servers.adsb.helpers.basic_tools import execute_readonly_query, get_conn
from backend.mcp_servers.adsb.helpers.get_aircraft_context import get_aircraft_context as _get_aircraft_context_json
from backend.mcp_servers.adsb.helpers.icao_to_reg_country import icao_to_country


mcp = FastMCP("ADSB Aircraft Intelligence (Condensed)", "0.2.0")


# ---------------------------------------------------------------------------
# JSON utilities
# ---------------------------------------------------------------------------


def _json_default(obj: Any):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=_json_default)


def _ok(data: Any, *, warnings: list[str] | None = None, truncated: bool | None = None) -> str:
    meta: dict[str, Any] = {"warnings": warnings or []}
    if truncated is not None:
        meta["truncated"] = truncated
    return _dumps({"data": data, "meta": meta})


def _err(message: str, *, warnings: list[str] | None = None) -> str:
    return _dumps({"error": message, "meta": {"warnings": warnings or []}})


# ---------------------------------------------------------------------------
# Param parsing / projection helpers (kept local for now)
# ---------------------------------------------------------------------------


def _clamp_int(val: int, *, default: int, min_v: int, max_v: int) -> int:
    if val < min_v:
        return default
    if val > max_v:
        return max_v
    return val


def _parse_int(val: int | str | None, *, default: int, min_v: int, max_v: int) -> int:
    try:
        if val is None or (isinstance(val, str) and val.strip() == ""):
            return default
        return _clamp_int(int(val), default=default, min_v=min_v, max_v=max_v)
    except Exception:
        return default


def _parse_float(val: float | str | None, *, default: float, min_v: float | None = None, max_v: float | None = None) -> float:
    try:
        if val is None or (isinstance(val, str) and val.strip() == ""):
            out = float(default)
        else:
            out = float(val)
    except Exception:
        out = float(default)

    if min_v is not None and out < float(min_v):
        out = float(default)
    if max_v is not None and out > float(max_v):
        out = float(max_v)
    return out


def _parse_datetime_optional(val: str | None) -> datetime | None:
    if val is None:
        return None
    s = (val or "").strip()
    if not s:
        return None
    # Accept ISO8601; allow trailing Z.
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _parse_list_str(val: str | list[str] | None) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    s = str(val).strip()
    if not s:
        return []
    # Accept comma-separated
    return [p.strip() for p in s.split(",") if p.strip()]


def _project(d: dict[str, Any] | None, keys: Iterable[str]) -> dict[str, Any] | None:
    if d is None:
        return None
    return {k: d.get(k) for k in keys if k in d}


def _position_to_dict(p: Any, *, fields: list[str] | None = None) -> dict[str, Any]:
    # Supports AircraftPosition (attrs) and dicts.
    base = {
        "id": getattr(p, "id", None),
        "icao": getattr(p, "icao", None),
        "timestamp": getattr(p, "timestamp", None),
        "lat": getattr(p, "lat", None),
        "lon": getattr(p, "lon", None),
        "altitude": getattr(p, "altitude", None),
        "ground_speed": getattr(p, "ground_speed", None),
        "track": getattr(p, "track", None),
        "vertical_rate": getattr(p, "vertical_rate", None),
        "flight_number": getattr(p, "flight_number", None),
    }
    # If it's already a dict from helper, merge what we can.
    if isinstance(p, dict):
        base.update(p)

    if fields:
        return {k: base.get(k) for k in fields if k in base}

    # Default: compact but useful.
    return {
        "icao": base.get("icao"),
        "timestamp": base.get("timestamp"),
        "lat": base.get("lat"),
        "lon": base.get("lon"),
        "altitude": base.get("altitude"),
        "ground_speed": base.get("ground_speed"),
        "track": base.get("track"),
        "flight_number": base.get("flight_number"),
    }


def _airport_basic(a: dict[str, Any]) -> dict[str, Any]:
    return {
        "ident": a.get("ident"),
        "name": a.get("name"),
        "type": a.get("type"),
        "latitude_deg": a.get("latitude_deg"),
        "longitude_deg": a.get("longitude_deg"),
        "iso_country": a.get("iso_country"),
        "iso_region": a.get("iso_region"),
        "municipality": a.get("municipality"),
        "iata_code": a.get("iata_code"),
        "icao_code": a.get("icao_code"),
    }


def _runway_compact(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "airport_ident": r.get("airport_ident"),
        "length_ft": r.get("length_ft"),
        "width_ft": r.get("width_ft"),
        "surface": r.get("surface"),
        "lighted": r.get("lighted"),
        "closed": r.get("closed"),
        "le_ident": r.get("le_ident"),
        "he_ident": r.get("he_ident"),
    }


def _freq_compact(f: dict[str, Any]) -> dict[str, Any]:
    return {
        "airport_ident": f.get("airport_ident"),
        "type": f.get("type"),
        "description": f.get("description"),
        "frequency_mhz": f.get("frequency_mhz"),
    }


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool()
def say_hello() -> str:
    return "Hello! The ADS-B Aircraft Intelligence (Condensed) MCP server is running."


@mcp.tool()
def get_aircraft_context(
    icao: str,
    include: list[str] | str | None = None,
    lookback_hours: float | str = 6.0,
) -> str:
    """One-call context bundle for an aircraft.

    Default includes are chosen to avoid follow-up calls:
    - identity/flags (from aircraft table)
    - registration + country
    - current position (compact)
    - track summary (compact)

    Args:
        icao: ICAO hex.
        include: Optional list (or comma-separated string) of extras.
            Supported: ["identity", "country", "current_position", "track_summary"].
            If omitted, defaults to all four.
        lookback_hours: Track summary lookback window.

    Returns:
        JSON envelope with aircraft context.
    """

    try:
        includes = set(_parse_list_str(include))
        if not includes:
            includes = {"identity", "country", "current_position", "track_summary"}

        data: dict[str, Any] = {"icao": (icao or "").strip().lower()}
        warnings: list[str] = []

        if "identity" in includes:
            identity_raw = _get_aircraft_context_json(icao)
            try:
                identity = json.loads(identity_raw)
            except Exception:
                identity = {"error": "failed to parse identity helper output"}

            if isinstance(identity, dict) and "error" in identity:
                warnings.append(f"identity: {identity.get('error')}")
            else:
                # Keep only the useful fields for context.
                data["identity"] = _project(
                    identity,
                    [
                        "icao",
                        "reg_num",
                        "type",
                        "description",
                        "military",
                        "interesting",
                        "pia",
                        "ladd",
                        "first_seen",
                        "last_seen",
                    ],
                )

        if "country" in includes:
            # Uses ICAO->reg->country mapping.
            data["country"] = icao_to_country(icao)

        if "current_position" in includes:
            p = get_vehicle_current_position(icao)
            data["current_position"] = None if p is None else _position_to_dict(p)

        if "track_summary" in includes:
            lh = _parse_float(lookback_hours, default=6.0, min_v=0.01, max_v=24.0 * 30)
            summary = get_track_summary(icao, lookback_hours=float(lh))
            # Trim summary to the essentials.
            data["track_summary"] = _project(
                summary,
                [
                    "icao",
                    "start_time",
                    "end_time",
                    "points",
                    "min_altitude",
                    "max_altitude",
                    "avg_ground_speed",
                    "min_lat",
                    "max_lat",
                    "min_lon",
                    "max_lon",
                ],
            )

        return _ok(data, warnings=warnings)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def get_aircraft_track(
    icao: str,
    limit: int | str = 200,
    start_time: str | None = None,
    end_time: str | None = None,
    fields: list[str] | str | None = None,
    downsample_every: int | str | None = None,
) -> str:
    """Get aircraft track (time series) with optional field selection and downsampling.

    Args:
        icao: ICAO hex.
        limit: Max points (newest-first).
        start_time: Optional ISO datetime lower bound.
        end_time: Optional ISO datetime upper bound.
        fields: Optional list (or comma-separated string) of position fields to return.
        downsample_every: If >1, returns every Nth point (after newest-first retrieval).

    Returns:
        JSON envelope with `points` newest-first.
    """

    try:
        lim = _parse_int(limit, default=200, min_v=1, max_v=5000)
        st = _parse_datetime_optional(start_time)
        et = _parse_datetime_optional(end_time)
        field_list = _parse_list_str(fields)
        ds = _parse_int(downsample_every, default=1, min_v=1, max_v=200)

        positions = get_vehicle_locations(icao, limit=lim, start_time=st, end_time=et)

        if ds > 1 and len(positions) > 0:
            positions = positions[::ds]

        points = [_position_to_dict(p, fields=field_list or None) for p in positions]
        truncated = len(points) >= lim
        return _ok(
            {
                "icao": (icao or "").strip().lower(),
                "count": len(points),
                "points": points,
            },
            truncated=truncated,
        )
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def analyze_aircraft_following(
    leader_icao: str,
    follower_icao: str,
    threshold_time_minutes: int | str = 60,
    threshold_distance_nm: float | str = 5.0,
    lookback_hours: float | str = 6.0,
) -> str:
    """Structured aircraft-following analysis.

    Returns both:
    - structured stats (hits/total/match_rate)
    - a compact summary string

    This currently reuses the existing helper's core logic by recomputing hits/total
    locally (so we don't rely on parsing a human-only sentence).
    """

    from datetime import timedelta
    from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm
    from backend.mcp_servers.adsb.helpers.basic_tools import normalize_icao

    try:
        leader = normalize_icao(leader_icao)
        follower = normalize_icao(follower_icao)
        if not leader or not follower:
            return _err("leader_icao and follower_icao are required")

        tmin = _parse_int(threshold_time_minutes, default=60, min_v=1, max_v=24 * 60)
        dnm = _parse_float(threshold_distance_nm, default=5.0, min_v=0.01, max_v=500.0)
        lh = _parse_float(lookback_hours, default=6.0, min_v=0.01, max_v=24.0 * 30)

        start_time = datetime.now().astimezone() - timedelta(hours=float(lh))
        max_points = 300

        leader_positions = get_vehicle_locations(leader, limit=max_points, start_time=start_time)
        follower_positions = get_vehicle_locations(follower, limit=max_points, start_time=start_time)

        window = timedelta(minutes=int(tmin))
        hits = 0
        for lp in leader_positions:
            lp_time = lp.timestamp
            close = False
            for fp in follower_positions:
                if lp_time - fp.timestamp > window:
                    continue
                if fp.timestamp - lp_time > window:
                    continue
                dist = haversine_distance_nm(lp.lat, lp.lon, fp.lat, fp.lon)
                if dist <= float(dnm):
                    close = True
                    break
            if close:
                hits += 1

        total = len(leader_positions)
        match_rate = (hits / total) if total else 0.0
        summary = (
            f"Aircraft {follower} was within {float(dnm):.1f} nm of {leader} "
            f"within ±{int(tmin)} minutes for {hits}/{total} leader positions "
            f"over the last {float(lh):g} hours."
        )

        return _ok(
            {
                "leader_icao": leader,
                "follower_icao": follower,
                "threshold_time_minutes": int(tmin),
                "threshold_distance_nm": float(dnm),
                "lookback_hours": float(lh),
                "hits": hits,
                "total": total,
                "match_rate": match_rate,
                "summary": summary,
            }
        )
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def find_nearby(
    latitude: float | str,
    longitude: float | str,
    radius_nm: float | str = 50.0,
    lookback_hours: float | str = 6.0,
    types: list[str] | str | None = None,
    limit: int | str = 5,
) -> str:
    """Find nearby aircraft/airports/navaids around a lat/lon.

    Args:
        latitude, longitude: decimal degrees.
        radius_nm: search radius.
        lookback_hours: used for latest-aircraft query.
        types: list (or comma-separated) of ["aircraft", "airports", "navaids"].
            Default is all.
        limit: per-type result limit.

    Returns:
        JSON envelope containing keys for each requested type.
    """

    try:
        lat = float(latitude)
        lon = float(longitude)
        rad = _parse_float(radius_nm, default=50.0, min_v=0.01, max_v=3000.0)
        lh = _parse_float(lookback_hours, default=6.0, min_v=0.01, max_v=24.0 * 30)
        lim = _parse_int(limit, default=5, min_v=1, max_v=50)

        t = {x.lower() for x in _parse_list_str(types)}
        if not t:
            t = {"aircraft", "airports", "navaids"}

        out: dict[str, Any] = {"center": {"lat": lat, "lon": lon}, "radius_nm": rad}

        if "aircraft" in t:
            aircraft = find_nearest_aircraft(lat, lon, lookback_hours=float(lh), radius_nm=float(rad), limit=int(lim))
            out["aircraft"] = [
                {
                    "icao": a.get("icao"),
                    "timestamp": a.get("timestamp"),
                    "lat": a.get("lat"),
                    "lon": a.get("lon"),
                    "altitude": a.get("altitude"),
                    "ground_speed": a.get("ground_speed"),
                    "track": a.get("track"),
                    "flight_number": a.get("flight_number"),
                    "reg_num": a.get("reg_num"),
                    "distance_nm": a.get("distance_nm"),
                    "bearing_deg": a.get("bearing_deg"),
                }
                for a in aircraft
            ]

        if "airports" in t:
            airports = find_nearest_airport(lat, lon, limit=int(lim), max_distance_nm=float(rad))
            out["airports"] = [
                {
                    **_airport_basic(a),
                    "distance_nm": a.get("distance_nm"),
                    "bearing_deg": a.get("bearing_deg"),
                }
                for a in airports
            ]

        if "navaids" in t:
            navaids = find_nearest_navaids(lat, lon, radius_nm=float(rad), limit=int(lim))
            out["navaids"] = [
                {
                    "ident": n.get("ident"),
                    "name": n.get("name"),
                    "type": n.get("type"),
                    "frequency_khz": n.get("frequency_khz"),
                    "latitude_deg": n.get("latitude_deg"),
                    "longitude_deg": n.get("longitude_deg"),
                    "iso_country": n.get("iso_country"),
                    "associated_airport": n.get("associated_airport"),
                    "distance_nm": n.get("distance_nm"),
                }
                for n in navaids
            ]

        return _ok(out)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def get_airport_context(
    ident: str,
    include: list[str] | str | None = None,
    runways_limit: int | str = 50,
    frequencies_limit: int | str = 100,
) -> str:
    """Get airport context with optional runways/frequencies.

    Args:
        ident: airport ident (e.g., KJFK).
        include: list (or comma-separated) of ["runways", "frequencies"]. Default none.
        runways_limit: max runways returned.
        frequencies_limit: max frequencies returned.

    Returns:
        JSON envelope containing airport basic info and optional included datasets.
    """

    try:
        includes = {x.lower() for x in _parse_list_str(include)}
        rlim = _parse_int(runways_limit, default=50, min_v=1, max_v=500)
        flim = _parse_int(frequencies_limit, default=100, min_v=1, max_v=500)

        airport = get_airport_by_ident(ident)
        if airport is None:
            return _err("Airport not found")

        data: dict[str, Any] = {"airport": _airport_basic(airport)}

        if "runways" in includes:
            runways = get_airport_runways(airport_ident=str(airport.get("ident") or ident), limit=int(rlim))
            data["runways"] = [_runway_compact(r) for r in runways]

        if "frequencies" in includes:
            freqs = get_airport_frequencies(airport_ident=str(airport.get("ident") or ident), limit=int(flim))
            data["frequencies"] = [_freq_compact(f) for f in freqs]

        return _ok(data)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def search_airports_tool(
    query: str | None = None,
    iso_country: str | None = None,
    iso_region: str | None = None,
    municipality: str | None = None,
    limit: int | str = 20,
) -> str:
    """Search airports with compact results.

    Args:
        query: substring match against airport name.
        iso_country: optional ISO country filter.
        iso_region: optional ISO region filter.
        municipality: optional substring filter.
        limit: max results.

    Returns:
        JSON envelope containing compact list results.
    """

    try:
        lim = _parse_int(limit, default=20, min_v=1, max_v=200)
        rows = search_airports(
            name_contains=query,
            iso_country=iso_country,
            iso_region=iso_region,
            municipality_contains=municipality,
            limit=int(lim),
        )
        out = [_airport_basic(r) for r in rows]
        return _ok({"count": len(out), "results": out}, truncated=len(out) >= lim)
    except Exception as e:
        return _err(str(e))


@mcp.tool()
def query_adsb(
    preset: str | None = None,
    args_json: str | dict[str, Any] | None = None,
    sql_query: str | None = None,
    params_json: str | list[Any] | None = None,
    max_rows: int | str = 200,
) -> str:
    """Read-only ADS-B query tool (preset-first).

    Recommended usage for LLMs:
    - Use `preset` for common queries (safe + predictable output)
    - Use `sql_query` only for advanced / debugging

    Presets (initial set):
    - `aircraft_latest_position`: args {"icao": "..."}
    - `aircraft_track_since`: args {"icao": "...", "start_time": "<iso>"}
    - `airport_by_ident`: args {"ident": "KJFK"}

    Returns:
        JSON envelope with rows/columns + metadata.
    """

    def _count_percent_s_placeholders(query: str) -> int:
        return len(re.findall(r"(?<!%)%s", query or ""))

    def _parse_params(params_value: str | list[Any] | None) -> list[Any]:
        if params_value is None or params_value == "":
            return []
        if isinstance(params_value, list):
            return params_value
        raw = (params_value or "").strip()
        if raw == "" or raw.lower() == "null":
            return []
        parsed: Any = json.loads(raw)
        for _ in range(2):
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            else:
                break
        if parsed is None:
            return []
        if not isinstance(parsed, list):
            raise ValueError("params_json must be a JSON array")
        return parsed

    try:
        if preset and sql_query:
            return _err("Provide either preset or sql_query, not both")
        max_rows_i = _parse_int(max_rows, default=200, min_v=1, max_v=2000)

        if preset:
            preset_n = (preset or "").strip().lower()
            args_obj: dict[str, Any] = {}
            if args_json is None or args_json == "":
                args_obj = {}
            elif isinstance(args_json, dict):
                args_obj = args_json
            else:
                parsed: Any = json.loads(str(args_json))
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
                if not isinstance(parsed, dict):
                    return _err("args_json must be a JSON object")
                args_obj = parsed

            if preset_n == "aircraft_latest_position":
                icao = str(args_obj.get("icao", "")).strip().lower()
                if not icao:
                    return _err("preset aircraft_latest_position requires args_json {icao}")
                sql = (
                    "SELECT id, icao, timestamp, lat, lon, altitude, ground_speed, track, vertical_rate, flight_number "
                    "FROM adsb_positions WHERE icao = %s ORDER BY timestamp DESC LIMIT 1"
                )
                params = [icao]
            elif preset_n == "aircraft_track_since":
                icao = str(args_obj.get("icao", "")).strip().lower()
                start_time_s = str(args_obj.get("start_time", "")).strip()
                if not icao or not start_time_s:
                    return _err("preset aircraft_track_since requires args_json {icao, start_time}")
                st = _parse_datetime_optional(start_time_s)
                if st is None:
                    return _err("start_time must be ISO datetime")
                sql = (
                    "SELECT id, icao, timestamp, lat, lon, altitude, ground_speed, track, vertical_rate, flight_number "
                    "FROM adsb_positions WHERE icao = %s AND timestamp >= %s ORDER BY timestamp DESC LIMIT %s"
                )
                params = [icao, st, int(max_rows_i)]
            elif preset_n == "airport_by_ident":
                ident = str(args_obj.get("ident", "")).strip().upper()
                if not ident:
                    return _err("preset airport_by_ident requires args_json {ident}")
                sql = (
                    "SELECT ident, type, name, latitude_deg, longitude_deg, iso_country, iso_region, municipality, iata_code, icao_code "
                    "FROM airports WHERE ident = %s LIMIT 1"
                )
                params = [ident]
            else:
                return _err(
                    "Unknown preset. Supported: aircraft_latest_position, aircraft_track_since, airport_by_ident"
                )

            with get_conn() as conn:
                rows = execute_readonly_query(conn, sql, params=params, max_rows=max_rows_i)

            columns = sorted({k for r in rows for k in r.keys()})
            return _ok(
                {
                    "mode": "preset",
                    "preset": preset_n,
                    "columns": columns,
                    "row_count": len(rows),
                    "max_rows": max_rows_i,
                    "rows": rows,
                },
                truncated=(len(rows) >= max_rows_i),
                warnings=[
                    "Prefer presets over raw SQL.",
                    "If you need raw SQL, keep it SELECT/WITH only and always include a LIMIT.",
                ],
            )

        # Raw SQL path
        if not sql_query or not str(sql_query).strip():
            return _err("Provide either preset or sql_query")

        params = _parse_params(params_json)
        placeholder_count = _count_percent_s_placeholders(str(sql_query))
        warning: str | None = None
        if placeholder_count == 0 and params:
            warning = "Query has 0 %s placeholders; ignoring provided params_json."
            params = []

        with get_conn() as conn:
            rows = execute_readonly_query(conn, str(sql_query), params=params, max_rows=max_rows_i)

        columns = sorted({k for r in rows for k in r.keys()})
        warnings: list[str] = [
            "Raw SQL is advanced. Prefer presets when possible.",
            "Only SELECT/WITH is allowed. Multiple statements are rejected.",
        ]
        if warning:
            warnings.append(warning)

        return _ok(
            {
                "mode": "sql",
                "columns": columns,
                "row_count": len(rows),
                "max_rows": max_rows_i,
                "rows": rows,
            },
            truncated=(len(rows) >= max_rows_i),
            warnings=warnings,
        )

    except Exception as e:
        return _err(str(e))


if __name__ == "__main__":
    mcp.run()
