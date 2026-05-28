from backend.data_processing.query_database import get_conn, DatabaseConnectionTypes


def query_region(region):
    #TODO: Add a check to make sure the region is a region we have data for
    """Return the list of fishy vessels in a region"""
    conn = get_conn(DatabaseConnectionTypes.FISHY_VESSELS)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sampletable;")
    results = cursor.fetchall()
    conn.close()
    return results


def query_vessel(name):
    """See if a specific vessel is in the list of fishy vessels"""
    conn = get_conn(DatabaseConnectionTypes.FISHY_VESSELS)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sampletable WHERE name = %s;", (name,))
    results = cursor.fetchall()
    conn.close()
    if len(results) == 0:
        return (f"No vessel with name {name} found in fishy vessels database.")
    else: 
        return results


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


def run_tests():
    """Run tests for the functions in this file."""
    failed = False

    if len(query_region("somewhere_cold")) == 0:
        print("query_region test failed: No vessels found in region.")
        failed = True

    if len(query_vessel("steve")) == 0:
        print("query_vessel test failed: No vessel with name steve found.")
        failed = True

    if not failed:
        print("All tests passed.")

run_tests()