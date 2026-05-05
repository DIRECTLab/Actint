#expose basic tools to other tools

from backend.mcp_servers.adsb.helpers.basic_tools import (
    get_conn,
    select_one,
    icao_to_reg,
    reg_to_country_iso,
    country_iso_to_name,
    get_last_location,
    get_last_seen_time,
    normalize_icao,
    bearing_diff_deg,
    bbox_from_radius_nm,
    execute_readonly_query,
    list_tables,
    describe_table,
    count_rows,
)

from backend.mcp_servers.adsb.helpers.adsb_locations import (
    AircraftPosition,
    get_vehicle_locations,
    get_vehicle_current_position,
    get_track_summary,
    get_direction_vector_for_aircraft,
    aircraft_following,
)

from backend.mcp_servers.adsb.helpers.airport_tools import (
    get_airport_by_ident,
    search_airports,
    find_nearest_airport,
    get_airport_frequencies,
    get_airport_runways,
    get_possible_airport_destinations,
    get_possible_airport_destinations_for_aircraft,
)

from backend.mcp_servers.adsb.helpers.avi import (
    get_country_info,
    search_countries,
    get_region_info,
    search_regions,
    get_navaid_by_ident,
    get_navaids_for_airport,
    find_nearest_navaids,
)

from backend.mcp_servers.adsb.helpers.icao_to_reg_country import icao_to_country

__all__ = [
    "get_conn",
    "select_one",
    "icao_to_reg",
    "reg_to_country_iso",
    "country_iso_to_name",
    "get_last_location",
    "get_last_seen_time",

    "normalize_icao",
    "bearing_diff_deg",
    "bbox_from_radius_nm",
    "execute_readonly_query",
    "list_tables",
    "describe_table",
    "count_rows",

    "AircraftPosition",
    "get_vehicle_locations",
    "get_vehicle_current_position",
    "get_track_summary",
    "get_direction_vector_for_aircraft",
    "aircraft_following",

    "get_airport_by_ident",
    "search_airports",
    "find_nearest_airport",
    "get_airport_frequencies",
    "get_airport_runways",
    "get_possible_airport_destinations",
    "get_possible_airport_destinations_for_aircraft",

    "get_country_info",
    "search_countries",
    "get_region_info",
    "search_regions",
    "get_navaid_by_ident",
    "get_navaids_for_airport",
    "find_nearest_navaids",

    "icao_to_country",
]