"""MCP Server for ADS-B Aircraft Intelligence Tools.

Standalone Model Context Protocol server that exposes ADS-B (aircraft) data tools
from Postgres to be consumed by LLM applications via stdio.

This is intentionally parallel to `actint.mcp.mcp_server` (AIS) but uses the
Postgres-backed ADS-B tools in `actint.tools.ADSB`.

Environment variables required for DB access:
- DB_HOST, ADSB_DB_NAME, DB_USER, DB_PASS, DB_PORT

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
from datetime import date, datetime
from typing import Any

from fastmcp import FastMCP

from backend.mcp_servers.adsb.helpers.adsb_locations import (
    aircraft_following,
    get_track_summary,
    get_vehicle_current_position,
    get_vehicle_locations,
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
    list_tables,
)
from backend.data_processing.query_database import (
    DatabaseConnectionTypes,
    get_conn,
)
from backend.mcp_servers.adsb.helpers.icao_to_reg_country import icao_to_country


mcp = FastMCP("ADSB Aircraft Intelligence", "0.1.0")

_PAGE_SIZE = 8


def _get_adsb_conn():
    """Always returns a connection to the ADSB database."""
    return get_conn(DatabaseConnectionTypes.ADSB)


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
    """Simple tool to test connectivity and responsiveness of the MCP server."""
    return "Hello! The ADS-B Aircraft Intelligence MCP server is up and running."


# ============================================================================
# Tools: Aircraft Locations
# ============================================================================


@mcp.tool()
def get_aircraft_locations(icao: str, page: str = "1") -> str:
    """Get recorded positions for an aircraft by ICAO hex. Data is paginated
    (50 positions per page, newest-first) to avoid returning too much information.

    Args:
        icao (str): ICAO hex identifier (e.g., "a1b2c3").
        page (str): Page number of positions. Start with '1'.

    Returns:
        A list of aircraft positions.
    """
    try:
        page_i = max(1, int(page))
        fetch_limit = page_i * _PAGE_SIZE
        all_positions = get_vehicle_locations(icao, limit=fetch_limit)

        start = (page_i - 1) * _PAGE_SIZE
        positions_slice = all_positions[start:fetch_limit]

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
            for p in positions_slice
        ]

        output = _dumps(
            {
                "page": page_i,
                "positions_returned": len(result),
                "positions": result,
            }
        )

        if len(all_positions) == fetch_limit:
            output += (
                f"\n\nMore positions may be available. "
                f"Call `get_aircraft_locations` again with "
                f"icao='{icao}' and page='{page_i + 1}' to retrieve the next page."
            )

        return output
    except Exception as e:
        return _dumps({"error": str(e)})



@mcp.tool()
def aircraft_following_analysis(
    leader_icao: str,
    follower_icao: str,
    threshold_time_minutes: str = "60",
    threshold_distance_nm: str = "5.0",
    lookback_hours: str = "6.0",
) -> str:
    """Determine whether one aircraft has been following another's flight path.

    Args:
        leader_icao (str): ICAO hex of the aircraft being followed.
        follower_icao (str): ICAO hex of the suspected following aircraft.
        threshold_time_minutes (str): Time window in minutes for position matching. Default '60'.
        threshold_distance_nm (str): Max distance in nautical miles between matched positions. Default '5.0'.
        lookback_hours (str): Hours of track history to analyse. Default '6.0'.

    Returns:
        Analysis results indicating whether following behaviour was detected.
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
def get_aircraft_track_summary(icao: str, lookback_hours: str = "6.0") -> str:
    """Return aggregate statistics for a recent aircraft track (distance, altitude
    range, speed range, etc.). Use `get_aircraft_locations` when individual
    position points are needed.

    Args:
        icao (str): ICAO hex identifier (e.g., "a1b2c3").
        lookback_hours (str): Hours of history to summarise. Default '6.0'.

    Returns:
        Aggregate track statistics for the requested period.
    """
    try:
        summary = get_track_summary(icao, lookback_hours=float(lookback_hours))
        return _dumps(summary)
    except Exception as e:
        return _dumps({"error": str(e)})


# ============================================================================
# Tools: Airport Lookup / Destination Prediction
# ============================================================================


@mcp.tool()
def find_nearest_airports(
    latitude: str,
    longitude: str,
    limit: str = "5",
    max_distance_nm: str | None = None,
) -> str:
    """Find airports nearest to a given latitude/longitude.

    Args:
        latitude (str): Latitude in decimal degrees (e.g., "40.6413").
        longitude (str): Longitude in decimal degrees (e.g., "-73.7781").
        limit (str): Maximum number of airports to return. Default '5'.
        max_distance_nm (str | None): Optional search radius cap in nautical miles. Omit or leave blank to search without a distance cap.

    Returns:
        A list of nearest airports ordered by distance.
    """
    try:
        # Treat empty string, "null", "none" etc. as absent
        _max_dist: float | None = None
        if max_distance_nm and max_distance_nm.strip().lower() not in ("", "null", "none"):
            _max_dist = float(max_distance_nm)

        airports = find_nearest_airport(
            float(latitude),
            float(longitude),
            limit=int(limit),
            max_distance_nm=_max_dist,
        )
        return _dumps(airports)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def get_airport(ident: str) -> str:
    """Look up an airport by its ICAO or IATA identifier.

    Args:
        ident (str): Airport identifier (e.g., "KJFK", "EGLL").

    Returns:
        Full airport details, or an error if the identifier is not found.
    """
    try:
        airport = get_airport_by_ident(ident)
        if airport is None:
            return _dumps({"error": f"Airport '{ident}' not found"})
        return _dumps(airport)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def search_airports_tool(
    name_contains: str | None = "",
    iso_country: str | None = "",
    iso_region: str | None = "",
    municipality_contains: str | None = "",
    limit: str = "50",
) -> str:
    """Search airports by name, country, region, or municipality.
    All text filters are optional case-insensitive partial matches.

    iso_region must be the full hyphenated code (e.g. "US-UT", not "UT").

    Args:
        name_contains (str | None): Partial airport name.
        iso_country (str | None): Two-letter ISO country code (e.g. "US").
        iso_region (str | None): Full ISO region code (e.g. "US-UT").
        municipality_contains (str | None): Partial city name.
        limit (str): Maximum results to return. Default '50'.

    Returns:
        A list of matching airports ordered by score descending.
    """
    def _empty_to_none(v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip().lower()
        if not cleaned or cleaned in ("null", "none", "n/a"):
            return None
        return v.strip()

    try:
        results = search_airports(
            name_contains=_empty_to_none(name_contains),
            iso_country=_empty_to_none(iso_country),
            iso_region=_empty_to_none(iso_region),
            municipality_contains=_empty_to_none(municipality_contains),
            limit=int(limit),
        )
        return _dumps(results)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def get_airport_runways_tool(airport_ident: str) -> str:
    """Get runway information for an airport.

    Args:
        airport_ident (str): Airport ICAO or IATA identifier (e.g., "KJFK").

    Returns:
        A list of runways with length, width, surface type, and headings.
    """
    try:
        return _dumps(get_airport_runways(airport_ident=airport_ident))
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def get_airport_frequencies_tool(
    airport_ident: str, freq_type: str | None = ""
) -> str:
    """Get radio communication frequencies for an airport.

    Args:
        airport_ident (str): Airport ICAO or IATA identifier (e.g., "KJFK").
        freq_type (str | None): Optional type filter (e.g., "ATIS", "TWR",
            "GND", "APP"). Leave blank or omit for all frequencies.

    Returns:
        A list of frequencies with type and MHz value.
    """
    def _empty_to_none(v: str | None) -> str | None:
        if not (v or "").strip():
            return None
        cleaned = v.strip().lower()
        if cleaned in ("null", "none", "n/a"):
            return None
        return v.strip()

    try:
        rows = get_airport_frequencies(
            airport_ident=airport_ident,
            freq_type=_empty_to_none(freq_type),
            limit=50,  # hard cap — airports rarely have more than ~20
        )
        # Return only the fields the agent actually needs
        slim = [
            {
                "type": r["type"],
                "description": r["description"],
                "frequency_mhz": r["frequency_mhz"],
            }
            for r in rows
        ]
        return _dumps(slim)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def get_possible_airport_destinations_for_aircraft_tool(
    icao: str,
    n_points: str = "50",
    radius_nm: str = "300.0",
    tolerance_deg: str = "15.0",
    limit: str = "10",
) -> str:
    """Suggest candidate destination airports based on an aircraft's recent
    direction of travel.

    Args:
        icao (str): ICAO hex identifier (e.g., "a1b2c3").
        n_points (str): Recent track points used to compute heading. Default '50'.
        radius_nm (str): Search radius in nautical miles ahead of the aircraft. Default '300.0'.
        tolerance_deg (str): Heading tolerance in degrees for path matching. Default '15.0'.
        limit (str): Maximum number of candidate airports to return. Default '10'.

    Returns:
        A list of candidate airports ranked by likelihood.
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


# ============================================================================
# Tools: Aviation Reference
# ============================================================================


@mcp.tool()
def find_nearest_navaids_tool(
    latitude: str,
    longitude: str,
    radius_nm: str = "100.0",
    limit: str = "10",
) -> str:
    """Find navigation aids (VOR, NDB, ILS, etc.) near a given position.

    Args:
        latitude (str): Latitude in decimal degrees (e.g., "40.6413").
        longitude (str): Longitude in decimal degrees (e.g., "-73.7781").
        radius_nm (str): Search radius in nautical miles. Default '100.0'.
        limit (str): Maximum number of navaids to return. Default '10'.

    Returns:
        A list of navaids ordered by distance.
    """
    try:
        result = find_nearest_navaids(
            float(latitude),
            float(longitude),
            radius_nm=float(radius_nm),
            limit=int(limit),
        )
        return _dumps(result)
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def icao_to_country_tool(icao: str) -> str:
    """Resolve an ICAO hex code to a country of registration.

    Args:
        icao (str): ICAO hex identifier (e.g., "a1b2c3").

    Returns:
        The resolved registration prefix, ISO country code, and country name.
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
    """List all public tables in the ADS-B Postgres database.

    Returns:
        Total table count and a list of table names.
    """
    try:
        with _get_adsb_conn() as conn:
            tables = list_tables(conn)
        return _dumps({"table_count": len(tables), "tables": tables})
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def describe_adsb_table(table_name: str) -> str:
    """Describe the columns of a table in the ADS-B Postgres database.

    Args:
        table_name (str): Name of the table to inspect (e.g., "adsb_positions").

    Returns:
        A list of column descriptors with name, data type, and nullability.
    """
    try:
        with _get_adsb_conn() as conn:
            columns = describe_table(conn, table_name)
        return _dumps({"table": table_name, "columns": columns})
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def count_adsb_rows(table_name: str) -> str:
    """Count the number of rows in an ADS-B database table.

    Args:
        table_name (str): Name of the table. Use `list_adsb_tables` to see available tables.

    Returns:
        The table name and its row count.
    """
    try:
        with _get_adsb_conn() as conn:
            n = count_rows(conn, table_name)
        return _dumps({"table": table_name, "row_count": n})
    except Exception as e:
        return _dumps({"error": str(e)})


@mcp.tool()
def query_adsb_database(
    sql_query: str,
    params_json: str | None = None,
    max_rows: str = "200",
) -> str:
    """Execute a read-only SQL query against the ADS-B Postgres database.
    Only SELECT and WITH (CTE) queries are permitted.

    Args:
        sql_query (str): A read-only SQL query starting with SELECT or WITH.
        params_json (str | None): Optional JSON array of positional parameters for %s placeholders (e.g., '["a1b2c3"]').
        max_rows (str): Maximum number of rows to return. Default '200'.

    Returns:
        Columns, row count, and rows from the query result.
    """
    try:
        max_rows_i = int(max_rows)
        params: list[Any] = []
        if params_json:
            parsed = json.loads(params_json)
            if not isinstance(parsed, list):
                return _dumps({"error": "params_json must be a JSON array"})
            params = parsed

        with _get_adsb_conn() as conn:
            rows = execute_readonly_query(
                conn, sql_query, params=params, max_rows=max_rows_i
            )

        columns = sorted({k for r in rows for k in r.keys()})
        return _dumps(
            {
                "columns": columns,
                "row_count": len(rows),
                "max_rows": max_rows_i,
                "rows": rows,
            }
        )
    except Exception as e:
        return _dumps({"error": str(e)})


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    import sys

    try:
        with _get_adsb_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        print("[ADSB MCP] DB connection OK.", file=sys.stderr)
    except Exception as e:
        print(
            f"[ADSB MCP] STARTUP FAILED — DB connection error: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    mcp.run()