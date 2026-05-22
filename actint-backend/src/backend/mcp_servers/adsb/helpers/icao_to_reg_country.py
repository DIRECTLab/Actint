#general idea
"""
icao comes in as argument
use icao on aircraft table to get registration number
using reg num use max fit search to find country iso in reg_num_to_country_iso
use country_iso to find country name and other context in avi_countries
"""

from backend.mcp_servers.adsb.helpers.basic_tools import icao_to_reg, reg_to_country_iso, country_iso_to_name, normalize_icao
from backend.data_processing.query_database import DatabaseConnectionTypes, get_conn


def icao_to_country(icao: str) -> dict:
    """Resolve ICAO -> registration -> ISO country -> country name.

    Returns a dict so higher-level tools (and later MCP) can serialize cleanly.
    """

    icao_n = normalize_icao(icao)
    if not icao_n:
        raise ValueError("icao is required")

    with get_conn(DatabaseConnectionTypes.ADSB) as conn:
        reg_num = icao_to_reg(conn, icao_n)
        iso_country = reg_to_country_iso(conn, reg_num) if reg_num else None
        country_name = country_iso_to_name(conn, iso_country) if iso_country else None

    return {
        "icao": icao_n,
        "reg_num": reg_num,
        "iso_country": iso_country,
        "country_name": country_name,
    }


if __name__ == "__main__":
    print(icao_to_country('ac1988')) # test case
    print(icao_to_country('06a088')) # test case
    print(icao_to_country('7cad43')) # test case
    
    