"""MCP Server for ADS-B Aircraft Intelligence Tools.

Standalone Model Context Protocol server that exposes ADS-B (aircraft) data tools
from Postgres to be consumed by LLM applications via stdio.

This is intentionally parallel to `actint.mcp.mcp_server` (AIS) but uses the
Postgres-backed ADS-B tools in `actint.tools.ADSB`.

Environment variables required for DB access:
- DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT

Tools provided (initial, simple set):
- Aircraft position history and current position
- "Following" analysis between two aircraft
- Track summary aggregates
- Nearest airport / candidate destinations
- Basic aviation reference lookups (navaids)
- Postgres introspection and read-only SQL query tool
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from fastmcp import FastMCP





# Import tool functions from parent package
from backend.mcp_servers.adsb.helpers.adsb_locations import (
    aircraft_following,
    get_track_summary,
    get_vehicle_current_position,
    get_vehicle_locations,
    find_nearest_aircraft,
)
from backend.mcp_servers.adsb.helpers.airport_tools import (
    find_nearest_airport,
    get_airport_by_ident,
    get_airport_frequencies,
    get_airport_runways,
    get_possible_airport_destinations_for_aircraft,
    search_airports,
)
from backend.mcp_servers.adsb.helpers.avi import find_nearest_navaids
from backend.mcp_servers.adsb.helpers.basic_tools import (
    count_rows,
    describe_table,
    execute_readonly_query,
    get_conn,
    list_tables,
)
from backend.mcp_servers.adsb.helpers.icao_to_reg_country import icao_to_country


mcp = FastMCP("ADSB Aircraft Intelligence", "0.1.0")


def _json_default(obj: Any):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=_json_default)


# ============================================================================
# Health & Info
# ============================================================================


@mcp.tool()
def say_hello() -> str:
    """Simple tool to test connectivity and responsiveness of the MCP server.

    Returns:
        str: Plain-text greeting confirming the server is running.
    """

    return "Hello! The ADS-B Aircraft Intelligence MCP server is up and running."


# ============================================================================
# Tools: Aircraft Locations
# ============================================================================


@mcp.tool()
def get_aircraft_locations(
    icao: str,
    limit: int | str = 200,
) -> str:
    """Get recent recorded positions for an aircraft by ICAO hex.

    Args:
        icao: ICAO hex identifier (e.g., "a1b2c3").
        limit: Max number of positions to return (newest-first).

    Returns:
        str: JSON list of position objects (newest-first).
    """

    try:
        limit_i = int(limit)
        positions = get_vehicle_locations(icao, limit=limit_i)
        result = [
            {
                "id": p.id,
                "icao": p.icao,
                "timestamp": p.timestamp,
                "latitude": p.lat,
                "longitude": p.lon,
                "altitude": p.altitude,
                "ground_speed": p.ground_speed,
                "track": p.track,
                "vertical_rate": p.vertical_rate,
                "flight_number": p.flight_number,
                "emergency": p.emergency,
                "category": p.category,
            }
            for p in positions
        ]
        return _dumps(result)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def get_aircraft_current_position(icao: str) -> str:
    """Get the most recent position of an aircraft.

    Args:
        icao: ICAO hex identifier (e.g., "a1b2c3") of the aircraft.

    Returns:
        str: JSON object with the latest position fields, or an error object.
    """

    try:
        p = get_vehicle_current_position(icao)
        if p is None:
            return _dumps({"error": "No positions found for this aircraft"})

        result = {
            "id": p.id,
            "icao": p.icao,
            "timestamp": p.timestamp,
            "latitude": p.lat,
            "longitude": p.lon,
            "altitude": p.altitude,
            "ground_speed": p.ground_speed,
            "track": p.track,
            "vertical_rate": p.vertical_rate,
            "flight_number": p.flight_number,
            "emergency": p.emergency,
            "category": p.category,
        }
        return _dumps(result)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def aircraft_following_analysis(
    leader_icao: str,
    follower_icao: str,
    threshold_time_minutes: int | str = 60,
    threshold_distance_nm: float | str = 5.0,
    lookback_hours: float | str = 6.0,
) -> str:
    """Determine if one aircraft has been following another aircraft's path.

    Args:
        leader_icao: ICAO hex for the leader aircraft.
        follower_icao: ICAO hex for the follower aircraft.
        threshold_time_minutes: Time tolerance for a match.
        threshold_distance_nm: Distance threshold (nautical miles).
        lookback_hours: How far back to analyze.

    Returns:
        str: JSON object with a human-readable analysis string, or an error object.
    """

    try:
        analysis = aircraft_following(
            leader_icao,
            follower_icao,
            threshold_time_minutes=int(threshold_time_minutes),
            threshold_distance_nm=float(threshold_distance_nm),
            lookback_hours=float(lookback_hours),
        )
        return _dumps({"analysis": analysis})
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def get_aircraft_track_summary(icao: str, lookback_hours: float | str = 6.0) -> str:
    """Return simple aggregate stats for an aircraft track.

    Args:
        icao: ICAO hex identifier of the aircraft.
        lookback_hours: How far back to summarize.

    Returns:
        str: JSON object with summary statistics, or an error object.
    """

    try:
        summary = get_track_summary(icao, lookback_hours=float(lookback_hours))
        return _dumps(summary)
    except Exception as e:
        return _dumps({"error": str(e)})


# ============================================================================
# Tools: Airport Lookup / Destination Prediction (ADS-B analogue)
# ============================================================================


@mcp.tool()
def find_nearest_airports(
    latitude: float | str,
    longitude: float | str,
    limit: int | str = 5,
    max_distance_nm: float | str | None = None,
) -> str:
    """Find nearest airports to a lat/lon.

    Args:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
        limit: Max number of airports to return.
        max_distance_nm: Optional max search radius (nautical miles). If omitted/blank,
            the helper may expand the radius until results are found.

    Returns:
        str: JSON list of airport objects with distance/bearing fields when available,
            or an error object.
    """

    try:
        lat = float(latitude)
        lon = float(longitude)
        lim = int(limit)
        md = (
            None
            if (
                max_distance_nm is None
                or (isinstance(max_distance_nm, str) and max_distance_nm.strip() == "")
            )
            else float(max_distance_nm)
        )
        airports = find_nearest_airport(lat, lon, limit=lim, max_distance_nm=md)
        return _dumps(airports)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def get_airport(ident: str) -> str:
    """Lookup airport by ident (e.g., "KJFK", "EGLL").

    Args:
        ident: Airport ident/code.

    Returns:
        str: JSON airport object, or an error object if not found.
    """

    try:
        airport = get_airport_by_ident(ident)
        if airport is None:
            return _dumps({"error": "Airport not found"})
        return _dumps(airport)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def search_airports_tool(
    name_contains: str | None = None,
    iso_country: str | None = None,
    iso_region: str | None = None,
    municipality_contains: str | None = None,
    limit: int | str = 50,
) -> str:
    """Search airports by name/region/country.

    Args:
        name_contains: Substring match against airport name.
        iso_country: Optional ISO country code filter.
        iso_region: Optional ISO region code filter.
        municipality_contains: Substring match against municipality.
        limit: Max number of rows to return.

    Returns:
        str: JSON list of matching airports, or an error object.
    """

    try:
        results = search_airports(
            name_contains=name_contains,
            iso_country=iso_country,
            iso_region=iso_region,
            municipality_contains=municipality_contains,
            limit=int(limit),
        )
        return _dumps(results)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def get_airport_runways_tool(airport_ident: str) -> str:
    """Get runways for an airport ident.

    Args:
        airport_ident: Airport ident/code.

    Returns:
        str: JSON list of runway records, or an error object.
    """

    try:
        return _dumps(get_airport_runways(airport_ident=airport_ident))
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def get_airport_frequencies_tool(airport_ident: str, freq_type: str | None = None) -> str:
    """Get radio frequencies for an airport ident.

    Args:
        airport_ident: Airport ident/code.
        freq_type: Optional frequency type filter.

    Returns:
        str: JSON list of frequency records, or an error object.
    """

    try:
        return _dumps(get_airport_frequencies(airport_ident=airport_ident, freq_type=freq_type))
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def get_possible_airport_destinations_for_aircraft_tool(
    icao: str,
    n_points: int | str = 50,
    radius_nm: float | str = 300.0,
    tolerance_deg: float | str = 15.0,
    limit: int | str = 10,
) -> str:
    """Suggest candidate destination airports based on recent direction of travel.

    Args:
        icao: ICAO hex identifier of the aircraft.
        n_points: Number of recent points to estimate direction.
        radius_nm: Search radius for candidate airports (nautical miles).
        tolerance_deg: Allowed heading deviation in degrees.
        limit: Max number of candidates.

    Returns:
        str: JSON object including current position, inferred direction, and candidate airports,
            or an error object.
    """

    try:
        result = get_possible_airport_destinations_for_aircraft(
            icao,
            n_points=int(n_points),
            radius_nm=float(radius_nm),
            tolerance_deg=float(tolerance_deg),
            limit=int(limit),
        )
        return _dumps(result)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def find_nearest_aircraft_to_airport(
    airport_ident: str,
    lookback_hours: float | str = 6.0,
    radius_nm: float | str = 50.0,
    limit: int | str = 5,
) -> str:
    """Find the nearest aircraft to an airport (by ident) using latest ADS-B positions.

    Args:
        airport_ident: Airport ident/code.
        lookback_hours: Lookback window for "latest" positions.
        radius_nm: Search radius around the airport (nautical miles).
        limit: Max number of aircraft candidates.

    Returns:
        str: JSON object with airport metadata and a candidate list, or an error object.
    """

    try:
        airport = get_airport_by_ident(airport_ident)
        if airport is None:
            return _dumps({"error": "Airport not found"})

        lat = float(airport["latitude_deg"])
        lon = float(airport["longitude_deg"])

        results = find_nearest_aircraft(
            lat,
            lon,
            lookback_hours=float(lookback_hours),
            radius_nm=float(radius_nm),
            limit=int(limit),
        )

        return _dumps(
            {
                "airport": {
                    "ident": airport.get("ident"),
                    "name": airport.get("name"),
                    "latitude_deg": airport.get("latitude_deg"),
                    "longitude_deg": airport.get("longitude_deg"),
                },
                "candidates": results,
            }
        )
    except Exception as e:
        return _dumps({"error": str(e)})


# ============================================================================
# Tools: Aviation reference
# ============================================================================


@mcp.tool()
def find_nearest_navaids_tool(
    latitude: float | str,
    longitude: float | str,
    radius_nm: float | str = 100.0,
    limit: int | str = 10,
) -> str:
    """Find nearest navigation aids (VOR/NDB/etc) within radius.

    Args:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
        radius_nm: Search radius (nautical miles).
        limit: Max number of navaids to return.

    Returns:
        str: JSON list of navaid records with distance fields, or an error object.
    """

    try:
        lat = float(latitude)
        lon = float(longitude)
        result = find_nearest_navaids(lat, lon, radius_nm=float(radius_nm), limit=int(limit))
        return _dumps(result)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def icao_to_country_tool(icao: str) -> str:
    """Resolve ICAO hex -> registration -> ISO country -> country name.

    Args:
        icao: ICAO hex identifier.

    Returns:
        str: JSON object with registration and country fields, or an error object.
    """

    try:
        result = icao_to_country(icao)
        return _dumps(result)
    except Exception as e:
        return _dumps({"error": str(e)})


# ============================================================================
# Tools: Database Introspection / Query (Postgres)
# ============================================================================


@mcp.tool()
def list_adsb_tables() -> str:
    """List public tables in the ADS-B Postgres database.

    Returns:
        str: JSON object containing table names and count, or an error object.
    """

    try:
        with get_conn() as conn:
            tables = list_tables(conn)
        return _dumps({"table_count": len(tables), "tables": tables})
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def describe_adsb_table(table_name: str) -> str:
    """Describe a Postgres table (columns, types, nullable).

    Args:
        table_name: Table name to describe.

    Returns:
        str: JSON object with column metadata, or an error object.
    """

    try:
        with get_conn() as conn:
            columns = describe_table(conn, table_name)
        return _dumps({"table": table_name, "columns": columns})
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def count_adsb_rows(table_name: str) -> str:
    """Count rows in a table.

    Args:
        table_name: Table name to count.

    Returns:
        str: JSON object with row count, or an error object.
    """

    try:
        with get_conn() as conn:
            n = count_rows(conn, table_name)
        return _dumps({"table": table_name, "row_count": n})
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def query_adsb_database(
    sql_query: str, params_json: str | list[Any] | None = None, max_rows: int | str = 200
) -> str:
    """Execute a read-only SQL query against ADS-B Postgres and return results.

    Args:
        sql_query: Read-only query starting with SELECT or WITH.
        params_json: Optional positional parameters for %s placeholders.

            Accepts either:
            - a JSON-encoded array (e.g. `[]`, `["US", 123]`), or
            - a JSON-encoded string containing an array (e.g. `"[]"`), or
            - an actual Python list (some MCP clients may send this).
        max_rows: Maximum number of rows to return.

    Returns:
        str: JSON object with rows/columns/metadata, or an error object.
    """

    def _parse_params(params_value: str | list[Any] | None) -> list[Any]:
        def _normalize_list(lst: list[Any]) -> list[Any]:
            # Common model bug: params_json='["[]"]' -> list ['[]']
            if len(lst) == 1 and isinstance(lst[0], str):
                candidate = lst[0].strip()
                if candidate == "" or candidate.lower() == "null":
                    return []
                if candidate.startswith("[") and candidate.endswith("]"):
                    try:
                        nested: Any = json.loads(candidate)
                        # Sometimes nested is a JSON-encoded string of JSON.
                        for _ in range(2):
                            if isinstance(nested, str):
                                nested = json.loads(nested)
                            else:
                                break
                        if isinstance(nested, list):
                            return nested
                    except Exception:
                        pass
            return lst

        if params_value is None or params_value == "":
            return []

        if isinstance(params_value, list):
            return _normalize_list(params_value)

        raw = params_value.strip()
        if raw == "" or raw.lower() == "null":
            return []

        # Some models/tool-callers mistakenly double-encode JSON, e.g. params_json='"[]"'.
        parsed: Any = json.loads(raw)
        if parsed is None:
            return []

        # Unwrap up to a couple layers of JSON-encoded strings.
        for _ in range(2):
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
            else:
                break

        if parsed is None:
            return []

        if not isinstance(parsed, list):
            raise ValueError("params_json must be a JSON array")
        return _normalize_list(parsed)

    def _count_percent_s_placeholders(query: str) -> int:
        # Approximate placeholder count for psycopg `%s` placeholders.
        # Ignores escaped percents like `%%s` (literal "%s").
        return len(re.findall(r"(?<!%)%s", query or ""))

    try:
        max_rows_i = int(max_rows)
        params = _parse_params(params_json)

        placeholder_count = _count_percent_s_placeholders(sql_query)
        warning: str | None = None
        if placeholder_count == 0 and params:
            # Another common model bug: always sending params even when the query has no placeholders.
            warning = "Query has 0 %s placeholders; ignoring provided params_json."
            params = []

        with get_conn() as conn:
            rows = execute_readonly_query(conn, sql_query, params=params, max_rows=max_rows_i)

        columns = sorted({k for r in rows for k in r.keys()})
        payload: dict[str, Any] = {
            "columns": columns,
            "row_count": len(rows),
            "max_rows": max_rows_i,
            "rows": rows,
        }
        if warning:
            payload["warning"] = warning
        return _dumps(payload)
    except Exception as e:
        return _dumps({"error": str(e)})


# ============================================================================
# Server Entry Point
# ============================================================================


if __name__ == "__main__":
    mcp.run()
