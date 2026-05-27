


def query_region(region):
    """Return the list of fishy vessels in a region"""
    pass


def query_vessel(mmsi):
    """See if a specific vessel is in the list of fishy vessels"""
    pass


def get_fishy_vessel_locations(region):
    """Get the most recent locations of vessels in a region marked as suspicious based on dark vessel analysis."""
    pass


def detect_fishy_clusters(region):
    # What defines a cluster? How many ships in what level of proximity?
    """Detect clusters of fishy vessels based on the proximity between their most recent estimated locations."""
    pass


def re_evaluate_region(region):
    # Call main.py of fishy_vessels with argument for the region.
    # This might just be done in the tools file
    """Re-run region analysis for fishy vessels."""
    pass


def get_fishy_vessel_trajectories(region):
    # For each fishy vessel in the region
        # Get its trajectory, save to a dictionary? Dataframe? Something else?
    """Use the ship_going tools to figure out where each fishy vessel in a region is likely headed"""
    pass