"""These are things that I think we should get rid of. I organized these by the things I think are still most likely to be relevant at the top and the ones that I think are least likely to be relevant at the bottom"""



"""The AI should know the approximate loction for each of these based off its general knowledge. These will probably only be useful if there are custom secret military ports or something that the AI doesn't already konw about"""

# @mcp.tool()
# def identify_maritime_region(latitude: float | str, longitude: float | str) -> str:   # Ideally the AI should just know what maritime region it is in based on the latitude and longitude
#     """Identify which maritime region a lat/lon coordinate is in.
    
#     Args:
#         latitude (float): Latitude in decimal degrees
#         longitude (float): Longitude in decimal degrees
    
#     Returns:
#         str: JSON with the name of the maritime region or "Unknown"
#     """
#     try:
#         latitude = float(latitude)
#         longitude = float(longitude)
#         region = identify_maritime_region_helper(latitude, longitude)
#         result = "Region" + str(region) if region else "Region unknown"
#         return result
#     except Exception as e:
#         return "Error" + str(e)


# @mcp.tool()
# def identify_nearest_port(latitude: float | str, longitude: float | str) -> str:    # Ideally the AI should just know what maritime region it is in based on the latitude and longitude
#     """Find the nearest major port to a given lat/lon.
    
#     Args:
#         latitude (float): Latitude in decimal degrees
#         longitude (float): Longitude in decimal degrees
    
#     Returns:
#         str: JSON with port name and distance in nautical miles
#     """
#     try:
#         latitude = float(latitude)
#         longitude = float(longitude)
#         port_name, distance = identify_nearest_port_helper(latitude, longitude)
#         result = "Port name:" + str(port_name) + "\tDistance:" + str(distance)
#         return json.dumps(result, indent=2)
#     except Exception as e:
#         return "Error" + str(e)


# @mcp.tool()
# def identify_nearest_waterway(latitude: float | str, longitude: float | str) -> str:    # Ideally the AI should just know what maritime region it is in based on the latitude and longitude
#     """Find the nearest strategic waterway to a given lat/lon.
    
#     Args:
#         latitude (float): Latitude in decimal degrees
#         longitude (float): Longitude in decimal degrees
    
#     Returns:
#         str: JSON with waterway name and distance in nautical miles
#     """
#     try:
#         latitude = float(latitude)
#         longitude = float(longitude)
#         waterway_name, distance = identify_nearest_waterway_helper(latitude, longitude)
#         result = "Waterwau Name:" + str(waterway_name) + "Distance:" + str(distance)
#         return result
#     except Exception as e:
#         return "Error" + str(e)



""" This could maybe be in here, but the AI has access to getting nearby ships and getting data for where the ship currently is. It might be a better idea to have the AI decide if a ship is following."""

"""This could still be useful though if the AI doesn't do a very good job at identifying ships following another ship."""

# @mcp.tool()
# def ship_following_analysis(mmsi1: int | str, mmsi2: int | str) -> str:
#     """Determine if one vessel has been following another vessel's path.
    
#     Args:
#         mmsi1 (int): MMSI of the initial vessel
#         mmsi2 (int): MMSI of the vessel to check if following
    
#     Returns:
#         str: Analysis string indicating how many times vessel 2 was near vessel 1
#     """
#     try:
#         mmsi1 = int(mmsi1)
#         mmsi2 = int(mmsi2)
#         result = ship_following(mmsi1, mmsi2)
#         return json.dumps({"analysis": result})
#     except Exception as e:
#         return json.dumps({"error": str(e)})





"""The AI has access to getting the fleet position and finding where a ship is. It should probably be up to the AI to make decisions about if a ship is in its fleet."""

# @mcp.tool()
# def ship_near_fleet(mmsi: int | str) -> str:                               # Ideally the AI should know if the ship is approximately "in the fleet" based on the data it can get for the ship's location and the fleet's location
#     """Check if a vessel is within fleet proximity (10 nautical miles).
    
#     Args:
#         mmsi (int): MMSI of the vessel to check
    
#     Returns:
#         str: String indicating if ship is in fleet or outside fleet proximity
#     """
#     try:
#         mmsi = int(mmsi)
#         result_str = ship_near_fleet_helper(mmsi)
#         return result_str
#     except Exception as e:
#         return "error: " + str(e)




"""The AI has access to a ship's latitude and longitude. It also has a pretty good idea of what things are in certain areas. This might be unnecessary and less useful that just the AI's general knowledge"""


# ============================================================================
# Tools: Geographic Context
# ============================================================================

# @mcp.tool()
# def get_location_context(latitude: float | str, longitude: float | str) -> str:
#     """Get geographic context for a lat/lon including maritime region, nearest ports, and strategic waterways.
    
#     Args:
#         latitude (float): Latitude in decimal degrees
#         longitude (float): Longitude in decimal degrees
    
#     Returns:
#         str: JSON with maritime region, nearest port, nearest waterway, and reverse geocoding info
#     """
#     try:
#         latitude = float(latitude)
#         longitude = float(longitude)
#         context = get_geolocation_context(latitude, longitude)
#         result = {
#             "latitude": latitude,
#             "longitude": longitude,
#             "maritime_region": context.maritime_region,
#             "nearest_port": {
#                 "name": context.nearest_port_name,
#                 "distance_nm": context.nearest_port_distance_nm,
#             } if context.nearest_port_name else None,
#             "nearest_waterway": {
#                 "name": context.nearest_waterway_name,
#                 "distance_nm": context.nearest_waterway_distance_nm,
#             } if context.nearest_waterway_name else None,
#             "reverse_geocoding": context.reverse_geocoding_result,
#         }
#         return json.dumps(result, indent=2)
#     except Exception as e:
#         return json.dumps({"error": str(e)})





"""The AI can use other tools to get the previous latitudes and longitudes of a ship and guess where it is going based off of that and its knowledge of world geography. This is unnecessary"""

# ============================================================================
# Tools: Destination Prediction
# ============================================================================

# @mcp.tool()
# def get_vessel_destination(mmsi: int | str, number_detections: int | str = 300) -> str:        
#     """Predict where a vessel is heading based on recent trajectory.
    
#     Args:
#         mmsi (int): MMSI of the vessel
#         number_detections (int): Number of recent position detections to consider (default: 300)
    
#     Returns:
#         str: JSON with analysis result and note about trajectory analysis
#     """
#     try:
#         mmsi = int(mmsi)
#         number_detections = int(number_detections)
#         calculate_vector_and_distance_sum(mmsi, number_detections)
#         result = {
#             "mmsi": mmsi,
#             "note": "Destination analysis completed. See server logs for trajectory analysis."
#         }
#         return json.dumps(result, indent=2)
#     except Exception as e:
#         return json.dumps({"error": str(e)})






""" The AI should know roughly the disance between two ships based on its knowledge of their lattitude and longitude"""


# @mcp.tool()
# def get_distance_between(lat1: float | str, lon1: float | str, lat2: float | str, lon2: float | str) -> str:  # The AI ideally should be able to know the approximate distance between two different lattitude and longitude points
#     """Calculate distance and bearing between two geographic points.
    
#     Args:
#         lat1 (float): Latitude of first point
#         lon1 (float): Longitude of first point
#         lat2 (float): Latitude of second point
#         lon2 (float): Longitude of second point
    
#     Returns:
#         str: JSON with distance in nautical miles and bearing in degrees
#     """
#     try:
#         lat1 = float(lat1)
#         lon1 = float(lon1)
#         lat2 = float(lat2)
#         lon2 = float(lon2)
#         result = calc_distance_between(lat1, lon1, lat2, lon2)
#         return json.dumps(result, indent=2)
#     except Exception as e:
#         return json.dumps({"error": str(e)})







"""The get ship general information has replaced this. It will tell the LLM the ship's latest detection making this deprecated."""



#@mcp.tool()
# def get_vessel_latest_location(mmsi: int | str) -> str:
#     """Get the most recent position of a vessel.
    
#     Args:
#         mmsi (int): Maritime Mobile Service Identity number of the vessel
    
#     Returns:
#         str: Information about the latest position of the vessel
#     """
#     try:
#         mmsi = int(mmsi)
#         location = get_vessel_latest_location_helper(mmsi)
#         if location:
#             result = "Current Vessel information:\n"
#             result += location
#             return result
#         else:
#             return "Error: No positions found for this vessel, this may be becuase of a wrong mmsi"
#     except Exception as e:
#         return "Error:\n" + str(e)






"""These should probably die becuase if the AI makes a query that returns like infinite data, it could ruin its context really bad."""


# # ============================================================================
# # Tools: Database Introspection
# # ============================================================================

# def _quote_sqlite_identifier(identifier: str) -> str:
#     """Safely quote a SQLite identifier (table/column name) using double quotes."""
#     return '"' + (identifier or "").replace('"', '""') + '"'


# @mcp.tool()
# def get_database_info() -> str:                                                     # This should maybe be in a helper function or in the system prompt
#     """Get basic SQLite database schema info (tables and column definitions).

#     Returns:
#         str: JSON object containing database path and a list of tables with columns.
#     """
#     try:
#         sqlite_path = _resolve_sqlite_path()
#         if not sqlite_path.exists():
#             return json.dumps({"error": f"SQLite database not found at {sqlite_path}"})

#         conn = sqlite3.connect(str(sqlite_path))
#         cursor = conn.cursor()

#         cursor.execute(
#             "SELECT name FROM sqlite_master "
#             "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
#             "ORDER BY name;"
#         )
#         table_names = [r[0] for r in cursor.fetchall()]

#         tables: list[dict] = []
#         for table_name in table_names:
#             quoted = _quote_sqlite_identifier(table_name)
#             cursor.execute(f"PRAGMA table_info({quoted});")
#             # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
#             columns = []
#             for cid, name, col_type, notnull, dflt_value, pk in cursor.fetchall():
#                 columns.append(
#                     {
#                         "cid": cid,
#                         "name": name,
#                         "type": col_type,
#                         "notnull": bool(notnull),
#                         "default": dflt_value,
#                         "pk": bool(pk),
#                     }
#                 )

#             tables.append({"name": table_name, "columns": columns})

#         conn.close()

#         return json.dumps(
#             {
#                 "db_path": str(sqlite_path),
#                 "table_count": len(tables),
#                 "tables": tables,
#             },
#             indent=2,
#         )
#     except sqlite3.Error as e:
#         return json.dumps({"error": f"Database error: {str(e)}"})
#     except Exception as e:
#         return json.dumps({"error": f"Introspection error: {str(e)}"})


# ============================================================================
# Tools: Database Query
# ============================================================================

# @mcp.tool()
# def query_database(sql_query: str, max_rows: int | str = 200) -> str:               
#     """Execute a read-only SQL query against the AIS database and return results.
    
#     Args:
#         sql_query (str): Read-only SQL query to execute (SELECT / WITH ... SELECT)
#         max_rows (int): Maximum number of rows to return (default: 200)
    
#     Returns:
#         str: JSON with query results and column names, or error message
#     """
#     try:
#         max_rows = int(max_rows)
#         query = (sql_query or "").strip()
#         if not query:
#             return json.dumps({"error": "sql_query is required"})

#         # Guardrails: read-only, single-statement queries only
#         ql = query.lower().lstrip()
#         if not (ql.startswith("select") or ql.startswith("with")):
#             return json.dumps({"error": "Only read-only SELECT queries are allowed"})

#         forbidden = [
#             "insert ", "update ", "delete ", "drop ", "alter ", "create ",
#             "attach ", "detach ", "vacuum", "pragma", "reindex", "replace ",
#             "truncate ",
#         ]
#         if any(tok in ql for tok in forbidden):
#             return json.dumps({"error": "Query contains forbidden keywords"})

#         # Disallow multi-statement execution; allow a single trailing semicolon
#         if ";" in query.rstrip(";"):
#             return json.dumps({"error": "Multiple SQL statements are not allowed"})

#         if max_rows <= 0:
#             max_rows = 200
#         if max_rows > 5000:
#             max_rows = 5000

#         conn = sqlite3.connect(str(_resolve_sqlite_path()))
#         cursor = conn.cursor()

#         cursor.execute(query)
        
#         # Get column names
#         columns = [description[0] for description in cursor.description] if cursor.description else []
        
#         # Fetch bounded results
#         rows = cursor.fetchmany(max_rows + 1)
        
#         # Convert rows to list of dicts
#         result_list = []
#         truncated = False
#         if len(rows) > max_rows:
#             truncated = True
#             rows = rows[:max_rows]

#         for row in rows:
#             row_dict = {col: val for col, val in zip(columns, row)}
#             result_list.append(row_dict)
        
#         conn.close()
        
#         result = {
#             "columns": columns,
#             "row_count": len(result_list),
#             "truncated": truncated,
#             "max_rows": max_rows,
#             "rows": result_list
#         }
#         return json.dumps(result, indent=2)
#     except sqlite3.Error as e:
#         return json.dumps({"error": f"Database error: {str(e)}"})
#     except Exception as e:
#         return json.dumps({"error": f"Query error: {str(e)}"})


# def _resolve_sqlite_path() -> Path:
#     """Resolve SQLite path, allowing benchmark overrides via env var."""
#     override = os.getenv("ACTINT_SQLITE_PATH")
#     if override:
#         return Path(override).expanduser().resolve()
#     return SQLITE_PATH
