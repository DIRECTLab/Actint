from backend.mcp_servers.ais.helpers.vessel_query import get_all_vessels_latest_location, get_vessel_position_history_helper, query_static_data_helper
from backend.dark_vessels.src.regions import REGIONS
from backend.dark_vessels.data.gfw.ship_types import AIS_COUNTRY_CODES, AIS_VESSEL_TYPE_CODES
import pandas as pd

def get_ais_in_region(region: str):
    
    latest_locations = get_all_vessels_latest_location()
    bounding_box = REGIONS[region]["bbox"]
    lon_min = bounding_box[0]
    lat_min = bounding_box[1]
    lon_max = bounding_box[2]
    lat_max = bounding_box[3]

    mmsis_in_region = []
    for location in latest_locations:
        lat = location['lat']; lon = location['lon']
        if lat and lon:
            if lat > lat_min and lat < lat_max and lon > lon_min and lon < lon_max:
                mmsis_in_region.append(location['mmsi'])

    vessels_in_region_data = []
    for mmsi in mmsis_in_region:
        static_data = query_static_data_helper({"mmsi": mmsi})

        dynamic_data = get_vessel_position_history_helper(mmsi)
        vessels_in_region_data.append({"static_data": static_data, "dynamic_data": dynamic_data})

    return vessels_in_region_data



# reference_data_structure_for_ML = {
#             "mmsi": mmsi,
#             "vessel_type_key": vessel_key,                                  This can derived from vessel_type_code
#             "vessel_type_code": tmpl["type_code"],
#             "timestamp": t,
#             "lat": round(lat + RNG.normal(0, 0.0002), 5),
#             "lon": round(lon + RNG.normal(0, 0.0002), 5),
#             "sog": round(reported_sog, 1),
#             "cog": round(reported_cog, 1),
#             "heading": round(reported_cog + RNG.normal(0, 2), 1) % 360,
#             "nav_status": nav_status,                                       just status in dynamic data
#             "length": int(length),
#             "width": int(width),
#             "draught": draught,                                             Equal to the draft
#             "name": name,
#             "flag": flag,                                                   can be derived from the origin country
#             "ais_on": True,
#             "true_activity": phase,                                         This must be assigned
#             "had_dark_period": len(dark_segments) > 0,                      This must be derived from the AIS data
#         }


def prepare_data_for_ML(data):
    """This will be the function that converts the AIS data from the database into AIS data that we can feed into the ML machine. We will needd to somehow define a true_activity"""
    # print(data)
    prepared_ship_data = []
    for ship in data:
        static_data = ship["static_data"][0]
        dynamic_data = ship["dynamic_data"]
        print("static data:",static_data)

        ship_detection_objects = []
        for detection in dynamic_data:
            ship_detection_objects.append({
                "mmsi": static_data['mmsi'],
                "vessel_type_code": static_data["vesseltype"],
                "vessel_type_key": AIS_VESSEL_TYPE_CODES.get(static_data["vesseltype"], "Unknown"),
                "timestamp": detection["basedatetime"],
                "lat": detection["lat"],
                "lon": detection["lon"],
                "sog": detection["sog"],
                "cog": detection["cog"],
                "heading": detection["heading"],
                "nav_status": detection["status"],
                "length": static_data["length"],
                "width": static_data["width"],
                "draught": static_data["draft"],
                "name": static_data["vesselname"],
                "flag": AIS_COUNTRY_CODES.get(static_data["origincountry"], "Unknown"),
                "ais_on": True,
                "true_activity": None,
                "had_dark_period": None,
                # We will need to assign true_activity and had_dark_period based on the data we have
            })
        prepared_ship_data.extend(ship_detection_objects)

        return prepared_ship_data







if __name__ == "__main__":
    result = get_ais_in_region("brazil_eez")
    print(result)