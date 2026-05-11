from backend.mcp_servers.utils.important_locations import *
from backend.mcp_servers.ais.helpers.vessel_query import get_vessel_position_history_helper, get_vessel_latest_location_helper
from backend.mcp_servers.utils.distance_calculation import calculate_bearing, haversine_distance_nm
from backend.mcp_servers.ais.helpers.get_general_ship_context import identify_maritime_region_helper, identify_maritime_region_helper
from datetime import datetime, timedelta
import math


#This will tell the AI where the ship is going.


# if ship distance is more than 400 miles from a port, we have no idea which port the ship is going to 
# if the ship is more than 400 miles from a strategic waterway, we have no idea where the ship is going.
# A ship can be going toward any maritime region any distance away, but it cannot pass through any continent. 

"""Find unnormalized sum of the last X ship vectors (or within the last X time). Find where it is going and then divide its magnitude by the distance it travelled. 
If the ship isn't really travelling toward a destination, the ratio should be very small. 
If the ship is travelling exactly toward the target, the ratio will be 1"""

"""There will then be a comparison between distance travelled and time spent traveling. We can use this to caluclate the speed of the object and give it to the LLM"""

"""It might be a good idea to make this thing "smart" and only take the tracks that roughly follow a straight line"""

VECTOR_DISTANCE_RATIO = 0.9
DEGREE_THRESHOLD= 15

def calculate_vector_and_distance_sum(ship_mmsi: str, number_detections=300, tracking_time=timedelta(hours=1)):
    positions = get_vessel_position_history_helper(ship_mmsi)
    
    position1 = positions[number_detections]
    rescent_reversed_positions = reversed(positions[:number_detections])
    total_vector = [0.0, 0.0]
    total_distance = 0
    for position2 in rescent_reversed_positions:
        latlng = vectorize(position1['lat'], position1['lon'], position2['lat'], position2['lon'])
        total_vector[0] += latlng[0]
        total_vector[1] += latlng[1]
        total_distance += math.hypot(latlng[0], latlng[1])
    print(total_vector, total_distance)
    
    for position in rescent_reversed_positions:
        print(position)

    vector_distance_ratio = math.hypot(total_vector[0], total_vector[1])/total_distance
    print("Vector distance ratio", vector_distance_ratio)
    if(vector_distance_ratio > VECTOR_DISTANCE_RATIO):                                                       #Can use this to describe if the ship is going fast or slow
        print("The ship is going toward something")

        current_position = (positions[0]['lat'], positions[0]['lon'])
        print(get_possible_destinations_helper(current_position, total_vector))

    else:
        for position in reversed(positions[:number_detections]):
            pass
            # print(position)
        print("The ship is doing wierd stuff acting like a reet.")
        
    

def vectorize(lat1, lon1, lat2, lon2):
    lat = lat2-lat1
    lon = lon2-lon1
    return (lat, lon)


def within_angle(a, b, tolerance=15):
    diff = abs((a - b + 180) % 360 - 180)
    return diff <= tolerance


def get_possible_destinations_helper(current_position, direction_vector):

    current_lat = current_position[0]
    current_lon = current_position[1]

    #Find the nearest port or waterway that the ship is going toward
    nearest_potential_waterway_name = None
    nearest_potential_waterway = [999999, 999999]
    for name, location in STRATEGIC_WATERWAYS.items():
        location_degrees = calculate_bearing(current_lat, current_lon, location[0], location[1])
        direction_degrees = math.degrees(math.atan2(direction_vector[0], direction_vector[1]))
        if(within_angle(location_degrees, direction_degrees, DEGREE_THRESHOLD)):
            location_vector = vectorize(current_lat, current_lon, location[0], location[1])
            if(math.hypot(nearest_potential_waterway[0], nearest_potential_waterway[1]) > math.hypot(location_vector[0], location_vector[1])):
                nearest_potential_waterway = location_vector
                nearest_potential_waterway_name = name

    nearest_potential_port_name = None    
    nearest_potential_port = [999999, 999999]
    for name, location in MAJOR_PORTS.items():
        location_degrees = calculate_bearing(current_lat, current_lon, location[0], location[1])
        direction_degrees = math.degrees(math.atan2(direction_vector[0], direction_vector[1]))
        if(within_angle(location_degrees, direction_degrees, DEGREE_THRESHOLD)):
            location_vector = vectorize(current_lat, current_lon, location[0], location[1])
            if(math.hypot(nearest_potential_port[0], nearest_potential_port[1]) > math.hypot(location_vector[0], location_vector[1])):
                nearest_potential_port = location_vector
                nearest_potential_port_name = name

    if math.hypot(nearest_potential_waterway[0], nearest_potential_waterway[1]) < math.hypot(nearest_potential_port[0], nearest_potential_port[1]):
        nearest_thing = nearest_potential_waterway
        nearest_thing_name = nearest_potential_waterway_name
    else:
        nearest_thing = nearest_potential_port
        nearest_thing_name = nearest_potential_port_name

    max_fov_continent_name = None
    max_fov_maritime_name = None

    print(haversine_distance_nm(current_position[0], current_position[1], nearest_thing[0], nearest_thing[1]) )
    if haversine_distance_nm(current_position[0], current_position[1], nearest_thing[0], nearest_thing[1]) < 300:
        return f"The ship is going toward {nearest_thing_name}"

    else:

        for continent_name, bounding_box in CONTINENTS.items():
            
            lat_min = bounding_box['bounds']['lat_min']
            lat_max = bounding_box['bounds']['lat_max']
            lon_min = bounding_box['bounds']['lon_min']
            lon_max = bounding_box['bounds']['lon_max']

            current_lat = current_position[0]
            current_lon = current_position[1]

            
            degree1 = calculate_bearing(current_lat, current_lon, lat_min, lon_min)
            degree2 = calculate_bearing(current_lat, current_lon, lat_min, lon_max)
            degree3 = calculate_bearing(current_lat, current_lon, lat_max, lon_min)
            degree4 = calculate_bearing(current_lat, current_lon, lat_max, lon_max)  #get the degrees of all the bearings, then get the largest and smallest ones

            max_degree = max(degree1, degree2, degree3, degree4)
            min_degree = min(degree1, degree2, degree3, degree4)

            #subtract the bearing of the ship, and cut the two bearings off at the at a max +-DEGREE_THRESHOLD
            max_fov_degree = 0
            if(min_degree < DEGREE_THRESHOLD and max_degree > -1*DEGREE_THRESHOLD):
                
                fov_min_degree = max(min_degree, -1*DEGREE_THRESHOLD)
                fov_max_degree = min(max_degree, DEGREE_THRESHOLD)

                total_fov_degrees = fov_max_degree - fov_min_degree
                if total_fov_degrees > max_fov_degree:
                    max_fov_degree = total_fov_degrees
                    max_fov_continent_name = continent_name
                
                
        
        for maritime_name, bounding_box in MARITIME_REGIONS.items():
            
            maritime_name = identify_maritime_region_helper(current_lat, current_lon)
            if continent_name == maritime_name:
                continue
            
            lat_min = bounding_box['bounds']['lat_min']
            lat_max = bounding_box['bounds']['lat_max']
            lon_min = bounding_box['bounds']['lon_min']
            lon_max = bounding_box['bounds']['lon_max']

            current_lat = current_position[0]
            current_lon = current_position[1]

            degree1 = calculate_bearing(current_lat, current_lon, lat_min, lon_min)
            degree2 = calculate_bearing(current_lat, current_lon, lat_min, lon_max)
            degree3 = calculate_bearing(current_lat, current_lon, lat_max, lon_min)
            degree4 = calculate_bearing(current_lat, current_lon, lat_max, lon_max)  #get the degrees of all the bearings, then get the largest and smallest ones

            max_degree = max(degree1, degree2, degree3, degree4)
            min_degree = min(degree1, degree2, degree3, degree4)

            #subtract the bearing of the ship, and cut the two bearings off at the at a max +-DEGREE_THRESHOLD
            max_fov_degree = 0
            if(min_degree < DEGREE_THRESHOLD and max_degree > -1*DEGREE_THRESHOLD):
                
                fov_min_degree = max(min_degree, -1*DEGREE_THRESHOLD)
                fov_max_degree = min(max_degree, DEGREE_THRESHOLD)

                total_fov_degrees = fov_max_degree - fov_min_degree
                if total_fov_degrees > max_fov_degree:
                    max_fov_degree = total_fov_degrees
                    max_fov_maritime_name = continent_name
        
    return f"The ship is in going toward {maritime_name} to {max_fov_continent_name}"
    


if __name__ == "__main__":
    calculate_vector_and_distance_sum(369970707)