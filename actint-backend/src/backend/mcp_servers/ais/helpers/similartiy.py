from backend.mcp_servers.ais.helpers.vessel_query import get_all_vessel_names, get_all_mmsis, get_all_fleet_names
from rapidfuzz import process, utils


def get_similar_vessel_names(query: str, number_results: int) -> list[str]:
    names = get_all_vessel_names()
    matches = process.extract(
        query,
        names, 
        limit=number_results,
        processor=utils.default_process # Handles case and whitespace automatically
    )
    names = [match[0] for match in matches]
    return names

def get_similar_mmsis(query: str | int, number_results: int) -> list[int]:
    mmsis_int = get_all_mmsis()
    mmsis_str = [str(mmsi) for mmsi in mmsis_int]
    matches = process.extract(
        str(query),
        mmsis_str, 
        limit=number_results,
        processor=utils.default_process # Handles case and whitespace automatically
    )
    mmsis = [match[0] for match in matches]
    return mmsis
    
def get_similar_fleet_names(query: str, number_results: int) -> list[str]:
    names = get_all_fleet_names()
    matches = process.extract(
        query,
        names, 
        limit=number_results,
        processor=utils.default_process # Handles case and whitespace automatically
    )
    names = [match[0] for match in matches]
    return names