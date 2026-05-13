from backend.mcp_servers.utils.distance_calculation import haversine_distance_nm
from backend.mcp_servers.ais.helpers.vessel_query import get_vessel_name, get_vessel_position_history_helper


from datetime import timedelta



def ship_following(mmsi1, mmsi2):
    """Determine if two vessels have been following each other."""
    
    mmsi1_name = get_vessel_name(mmsi1)
    mmsi2_name = get_vessel_name(mmsi2)
    THRESHOLD_TIME = timedelta(hours=1)
    THRESHOLD_DISTANCE = 5.0  # Latitude/longitude degrees for now

    positions1 = get_vessel_position_history_helper(mmsi1)
    positions2 = get_vessel_position_history_helper(mmsi2)

    in_previous_area = []
    
    for position1 in positions1:
        follows_past_hour = []
        for position2 in positions2:
            if position1['basedatetime'] - position2['basedatetime'] <= THRESHOLD_TIME: 
                    follows_past_hour.append(position2)
                    
                    for follows in follows_past_hour:
                        distance = haversine_distance_nm(position1['lat'], position1['lon'], follows['lat'], follows['lon'])
                        if distance <= THRESHOLD_DISTANCE: 
                            in_previous_area.append(True)
                            break                                    #make sure this does the right thing to go to the next for loop, might be break
                    
                    in_previous_area.append(False)
                

        
    
    string = f"Vessel {mmsi2_name} went to the same area as {mmsi1_name} within {THRESHOLD_TIME.total_seconds() / 3600:.1f} hours of when {mmsi1_name} was there {sum(in_previous_area)}/{len(in_previous_area)} times."
    return string