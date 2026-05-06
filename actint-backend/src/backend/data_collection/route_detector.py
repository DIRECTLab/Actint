"""
route-detector.py

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

            
data structure end goal

1. table of all route segments (id, start_lat, start_long, end_lat, end_long) for basic info with additional metadata (want to capture summary stats of this route, how many planes a day, which planes and their frequency)
2. table of flights (id, start airport, end airport, flight number, associated route segments, flight duration, distance, any others?)
3. table of segment probabilities (route_id1, route_id2, idk how to relate these probablistically)
"""