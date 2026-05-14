"""
general idea:   take heat map point find all ADS-B pings within a radius of that point and average them to one point, store that point, 
                once we have all points do a decimation pass to remove redundant and minimally changing points along the route


"""

from h3 import cell_to_latlng
from backend.mcp_servers.adsb.helpers.adsb_locations import bbox_from_radius_nm, get_conn
from alive_progress import alive_bar


def cell_to_bbox(cell, radius_nm=5):
    lat, lon = cell_to_latlng(cell)
    result = bbox_from_radius_nm(lat, lon, radius_nm) #returns lat_min, lat_max, lon_min, lon_max, wrapped 
    
    #testing
    #lat_min, lat_max, lon_min, lon_max, wrap = result
    #print(f"https://bboxfinder.com/#{lat_min:.6f},{lon_min:.6f},{lat_max:.6f},180.0")
    #print(f"https://bboxfinder.com/#{lat_min:.6f},-180.0,{lat_max:.6f},{lon_max:.6f}")

    return result


def position_query(conn, result):
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

        
        with conn.cursor() as cur:
            cur.execute(base_query,params1)
            rows1 = cur.fetchall()


        params2 = (lat_min, lat_max, -180, lon_max)

        
        with conn.cursor() as cur:
            cur.execute(base_query,params2)
            rows2 = cur.fetchall()

        rows1.extend(rows2)

        rows = rows1
        return rows
    
    else:

        params = (lat_min, lat_max, lon_min, lon_max)

        
        with conn.cursor() as cur:
            cur.execute(base_query,params)
            rows = cur.fetchall()

        return rows
    

def points_mean(points, wrapped):

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

        #print(f"\nMean Lat,Long: {mean_lat:.6f},{mean_lon:.6f}")


    return mean_lat, mean_lon

def create_tables(conn):

    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS route_averages (
        
                id BIGSERIAL PRIMARY KEY,
                lat DOUBLE PRECISION,
                lon DOUBLE PRECISION
            )
        """)

    conn.commit()
        

def get_heatmap_points(conn, noise_floor):

    with conn.cursor() as cur:
        cur.execute("""
            SELECT
            lat_center,
            lon_center,
            traversal_count
            FROM heatmap_h3_res7_routes
            WHERE traversal_count >= %s
        """, (noise_floor,))

        rows = cur.fetchall()

    return rows


def insert_mean(conn, mean):

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO route_averages (
            lat,
            lon
        )
        VALUES (%s, %s)
        """, mean)

    conn.commit()



def flush(table, conn, agg):
  
    with conn.cursor() as cur:
        cur.executemany(f"""
            INSERT INTO {table} (
                lat,
                lon
            )
            VALUES (%s, %s)
        """, agg)




def main():
    """
    create averages table schema
    get list of points to iterate over with noise cut offs
    loop over each point
        get bounding box from the center
        average the points inside of it
        store the average away

    run decimation pass over the points
    """


    with get_conn() as conn:

        mean_points=[]
        flush_limit = 1000

        create_tables(conn)
        points = get_heatmap_points(conn, 100) #noise floor 100 plane traversals over the year

        print(f"\nPoints found: {len(points)} \n")
        with alive_bar(len(points)) as bar:

            bar.title = 'Finding Average Routes'

            for point in points:

                lat_center, lon_center, traversal_count = point
                bbox = bbox_from_radius_nm(lat_center, lon_center, 2) #2 nm approx = 3.7 km which is slightly bigger than res 7 hex cell
                position_points = position_query(conn, bbox)

                wrapped = bbox[4]
                mean = points_mean(position_points, wrapped)
                bar.text(f"Mean: {mean[0]}, {mean[1]}")
                mean_points.append(mean)

                if len(mean_points) >= flush_limit: #periodic flush
                    flush("route_averages", conn, mean_points)
                    conn.commit()
                    mean_points.clear()
                    print("Flushed")
                
                bar()


        if mean_points: #final flush
            flush("route_averages", conn, mean_points)
            conn.commit()
            print("Final Flush")



if __name__ == "__main__":
    
    main()
#     result = cell_to_bbox("832695fffffffff", 10)
#    # result = cell_to_bbox("810dbffffffffff", 10)
#     list_points = position_query(result)
#     mean = mean(list_points, result[4])
#     print(mean) 
