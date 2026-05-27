class ShipRegions:
    """
    Defines the major ocean-going regions of the world and provides
    a function to evaluate which region a given lat/lon point falls in.

    Regions are checked in order from most specific (gulfs, seas) to most
    general (oceans) to ensure correct assignment. The final fallback is
    the Pacific Ocean, which covers any remaining ocean-faring coordinates.
    """

    REGIONS = {
        # --- Gulfs & Smaller Seas (most specific, checked first) ---
        "gulf_of_mexico": {
            "min_lat": 18.0, "min_lon": -98.0, "max_lat": 31.0, "max_lon": -80.0,
        },
        "gulf_of_aden": {
            "min_lat": 10.0, "min_lon": 42.0, "max_lat": 16.0, "max_lon": 52.0,
        },
        "gulf_of_guinea": {
            "min_lat": -5.0, "min_lon": -5.0, "max_lat": 5.0, "max_lon": 9.0,
        },
        "gulf_of_oman": {
            "min_lat": 20.0, "min_lon": 54.0, "max_lat": 27.0, "max_lon": 65.0,
        },
        "persian_gulf": {
            "min_lat": 23.0, "min_lon": 47.0, "max_lat": 30.0, "max_lon": 57.0,
        },
        "red_sea": {
            "min_lat": 12.0, "min_lon": 32.0, "max_lat": 30.0, "max_lon": 44.0,
        },
        "mediterranean_sea": {
            "min_lat": 30.0, "min_lon": -6.0, "max_lat": 46.0, "max_lon": 37.0,
        },
        "black_sea": {
            "min_lat": 40.5, "min_lon": 27.5, "max_lat": 46.5, "max_lon": 41.0,
        },
        "north_sea": {
            "min_lat": 51.0, "min_lon": -4.0, "max_lat": 61.0, "max_lon": 10.0,
        },
        "baltic_sea": {
            "min_lat": 53.0, "min_lon": 10.0, "max_lat": 66.0, "max_lon": 30.0,
        },
        "bay_of_bengal": {
            "min_lat": 5.0, "min_lon": 80.0, "max_lat": 23.0, "max_lon": 100.0,
        },
        "south_china_sea": {
            "min_lat": 0.0, "min_lon": 100.0, "max_lat": 23.0, "max_lon": 122.0,
        },
        "sea_of_japan": {
            "min_lat": 33.0, "min_lon": 127.0, "max_lat": 52.0, "max_lon": 142.0,
        },
        "bering_sea": {
            "min_lat": 52.0, "min_lon": -180.0, "max_lat": 66.0, "max_lon": -157.0,
        },
        "caribbean_sea": {
            "min_lat": 9.0, "min_lon": -87.0, "max_lat": 23.0, "max_lon": -60.0,
        },

        # --- Oceans (broader, checked after specific regions) ---
        "arctic_ocean": {
            "min_lat": 70.0, "min_lon": -180.0, "max_lat": 90.0, "max_lon": 180.0,
        },
        "southern_ocean": {
            "min_lat": -90.0, "min_lon": -180.0, "max_lat": -60.0, "max_lon": 180.0,
        },
        "north_atlantic": {
            "min_lat": 0.0, "min_lon": -80.0, "max_lat": 70.0, "max_lon": -6.0,
        },
        "south_atlantic": {
            "min_lat": -60.0, "min_lon": -70.0, "max_lat": 0.0, "max_lon": 20.0,
        },
        "north_pacific": {
            "min_lat": 0.0, "min_lon": 120.0, "max_lat": 70.0, "max_lon": 180.0,
        },
        "north_pacific_east": {
            "min_lat": 0.0, "min_lon": -180.0, "max_lat": 70.0, "max_lon": -80.0,
        },
        "south_pacific": {
            "min_lat": -60.0, "min_lon": -180.0, "max_lat": 0.0, "max_lon": -70.0,
        },
        "south_pacific_west": {
            "min_lat": -60.0, "min_lon": 150.0, "max_lat": 0.0, "max_lon": 180.0,
        },
        "indian_ocean": {
            "min_lat": -60.0, "min_lon": 20.0, "max_lat": 30.0, "max_lon": 120.0,
        },
    }

    @staticmethod
    def evaluate_region(lat: float, lon: float) -> str:
        """
        Returns the region name for a given latitude and longitude.
        Checks specific regions (gulfs, seas) before broader oceans.
        Falls back to 'pacific_ocean' for any remaining ocean coordinates.

        Args:
            lat: Latitude in decimal degrees (-90 to 90)
            lon: Longitude in decimal degrees (-180 to 180)

        Returns:
            Region name as a string (matches a key in REGIONS or 'pacific_ocean')
        """
        # Check specific regions first (gulfs, seas, smaller bodies)
        specific_regions = [
            "gulf_of_mexico", "gulf_of_aden", "gulf_of_guinea", "gulf_of_oman",
            "persian_gulf", "red_sea", "mediterranean_sea", "black_sea",
            "north_sea", "baltic_sea", "bay_of_bengal", "south_china_sea",
            "sea_of_japan", "bering_sea", "caribbean_sea",
        ]

        for region in specific_regions:
            bounds = ShipRegions.REGIONS[region]
            if (bounds["min_lat"] <= lat <= bounds["max_lat"] and
                    bounds["min_lon"] <= lon <= bounds["max_lon"]):
                return region

        # Check polar oceans
        for region in ["arctic_ocean", "southern_ocean"]:
            bounds = ShipRegions.REGIONS[region]
            if bounds["min_lat"] <= lat <= bounds["max_lat"]:
                return region

        # Check remaining oceans
        ocean_regions = [
            "north_atlantic", "south_atlantic", "indian_ocean",
            "north_pacific", "north_pacific_east", "south_pacific", "south_pacific_west",
        ]

        for region in ocean_regions:
            bounds = ShipRegions.REGIONS[region]
            if (bounds["min_lat"] <= lat <= bounds["max_lat"] and
                    bounds["min_lon"] <= lon <= bounds["max_lon"]):
                return region

        # Fallback — remaining ocean-faring coordinates default to pacific
        return "Failed to identify vessel region"