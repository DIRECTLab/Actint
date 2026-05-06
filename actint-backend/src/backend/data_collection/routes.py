"""
route predictor and detector

goal -  get routes for airplanes that tie flight numbers to departing and arriving airports 
        could also get detailed paths by decimating the pos data of a flight to get more accurate routes 

options for how to do this:
1. use our ADS-B pos data to approximate which airports are tied to which flight number routes using new leg and flight number changes
    psuedocode
    loop over position data for each aircraft
        find changes in flight numbers and get all position entries between the change
        find all airports within a radius (radius could be estimated off of altitude and descent rate)
        find most likely airport based on heading, point to point and directional cone calc
        say that is the airport and record it to the flight number

    pros    we could also do a path decimation pass to get common way points on the route (better than just airport to airport)
            easier to customize and get exactly what we want
    
    cons    potential for error as ADS-B data isn't perfectly transmitted during landings and taxi
            potential for long run time
            somewhat longer development time and troubleshooting

    
2. use a web scrapper and get routes based on flight numbers and airport to airport 
    could use this but not sure how easy it is to get flight numbers from the website they scrap (see https://github.com/Jonty/airline-route-data/blob/main/scrape_airline_routes.py)

    pros    no guessing on what airport flight numbers are attached to

    cons    have to scrap and navigate other peoples data
            not as customizable 
            only has point to point routes and doesn't capture all the segments of a flight 

3. go full ML and make a model that predicts next ADSB message lat, long, altitude, and time given the previous n ADSB messages 

    pros    potential to be the most accurate
            don't have to manually assign probability to segment transitions based on some data 

    cons    not clear how it reaches its conclusions
            training time (probably similar to build the routes db but still)
            
data structure end goal

1. table of all route segments (id, start_lat, start_long, start altitude, end_lat, end_long, end_altitude) for basic info with additional metadata (want to capture summary stats of this route, how many planes a day, which planes and their frequency)
2. table of flights (id, start airport, end airport, flight number, associated route segments, flight duration, distance, any others?)
3. table of segment transitions with probabilities (id, from_segment_id, to_segment_id, aircraft_type, airline, altitude_band, time_of_day, transition_count, probability, confidence, last_updated)

AI table schema design

flights — Stores individual flight instances reconstructed from ADS-B data, representing a single aircraft movement from departure to arrival.
flights (id, aircraft_icao, flight_number, departure_airport, arrival_airport, departure_time, arrival_time, duration_seconds, distance_nm, route_id)

route_segments — Breaks each flight into ordered spatial-temporal trajectory segments used for path reconstruction and analysis.
route_segments (id, flight_id, geom, start_lat, start_lon, end_lat, end_lon, start_time, end_time, altitude_avg, speed_avg)

routes — Represents aggregated airport-to-airport connections derived from multiple flights as a canonical route definition.
routes (id, origin_airport, destination_airport, flight_count, aircraft_count, avg_duration_seconds, avg_distance_km, confidence, last_updated)

flight_route_mapping — Stores probabilistic assignments linking individual flights to candidate routes along with confidence and inference method metadata.
flight_route_mapping (id, flight_id, route_id, confidence, method, features)

segment_transitions — Models learned probabilities of movement between trajectory segments to enable next-segment prediction and behavior modeling.
segment_transitions (id, from_segment_id, to_segment_id, aircraft_type, db_flags, altitude_band, time_of_day, transition_count, probability, confidence, last_updated)

segment_route_mapping — Links fine-grained trajectory segments to higher-level routes with probabilistic weighting for explainability and refinement.
segment_route_mapping (segment_id, route_id, probability)


"""