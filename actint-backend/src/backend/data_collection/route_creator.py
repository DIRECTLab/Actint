"""
general idea:   take heat map point find all ADS-B pings within a radius of that point and average them to one point, store that point, 
                once we have all points do a decimation pass to remove redundant and minimally changing points along the route


"""

from h3 import cell_to_latlng
from backend.mcp_servers.adsb.helpers.adsb_locations import bbox_from_radius_nm, get_conn


def cell_to_bbox(cell, radius_nm=5):
    lat, lon = cell_to_latlng(cell)
    result = bbox_from_radius_nm(lat, lon, radius_nm) #returns lat_min, lat_max, lon_min, lon_max, wrapped 
    
    #testing
    #lat_min, lat_max, lon_min, lon_max, wrap = result
    #print(f"https://bboxfinder.com/#{lat_min:.6f},{lon_min:.6f},{lat_max:.6f},180.0")
    #print(f"https://bboxfinder.com/#{lat_min:.6f},-180.0,{lat_max:.6f},{lon_max:.6f}")

    return result


def query(result):
    """
    query the db for all lat lon within our bounding box from the cell
    return a list of lat, lon points
    """
   
    base_query = """
                SELECT
                    lat,
                    lon
                FROM adsb_positions
                WHERE lat IS NOT NULL
                  AND lon IS NOT NULL
                  AND lat BETWEEN %s AND %s
                  AND lon BETWEEN %s AND %s
            """

    lat_min, lat_max, lon_min, lon_max, wrapped = result    

    if wrapped:

        params1 = (lat_min, lat_max, lon_min, 180)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(base_query,params1)
                rows1 = cur.fetchall()


        params2 = (lat_min, lat_max, -180, lon_max)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(base_query,params2)
                rows2 = cur.fetchall()

        rows = rows1.extend(rows2)

        return rows
    
    else:

        params = (lat_min, lat_max, lon_min, lon_max)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(base_query,params)
                rows = cur.fetchall()

        return rows
    

def mean(points, wrapped):

    if not points:
        print("No points found within bbox!")
        return

    count = 0
    lat_sum = lon_sum = 0

    if wrapped:

        ref = points[0][1]

        for coord in points:
            diff = coord[1] - ref
            # Adjust for wrap-around
            if diff > 180:
                lon_sum += (coord[1] - 360)
            elif diff < -180:
                lon_sum += (coord[1] + 360)
            else:
                lon_sum += coord[1]

            count += 1
            lat_sum += coord[0]

        mean_lat = lat_sum/count
        mean_lon = lon_sum/count
        
        # Normalize back to [-180, 180]
        if mean_lon > 180: mean_lon -= 360
        if mean_lon < -180: mean_lon += 360


    else: 

        for coord in points:
            count += 1
            lat_sum += coord[0]
            lon_sum += coord[1]

        mean_lat = lat_sum/count
        mean_lon = lon_sum/count

        print(f"\nMean Lat,Long: {mean_lat:.6f},{mean_lon:.6f}")


    return mean_lat, mean_lon



if __name__ == "__main__":
    
    result = cell_to_bbox("832695fffffffff", 10)
   # result = cell_to_bbox("810dbffffffffff", 10)
    list_points = query(result)
    mean = mean(list_points, result[4])
    print(mean) 
