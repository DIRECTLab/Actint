# Route Predictor & Detector

## Goal

Build a system that maps flight numbers to their departure and arrival airports using ADS-B position data. Optionally, decimate position data along a flight's path to reconstruct more accurate intermediate waypoints beyond just the endpoint airports.

---

## Implementation Options

### Option 1 — ADS-B Position Analysis 

Loop over position data for each aircraft, detect flight number changes, and infer the associated airports from the surrounding position data.

**Airport detection Pseudocode:**
```
for each aircraft:
    find changes in flight numbers
    collect all position entries between each change
    find all airports within a search radius
        (radius estimated from altitude + descent rate)
    score candidates by heading, point-to-point distance, and directional cone
    assign the highest-scoring airport to the flight number
```

| ✅ Pros | ❌ Cons |
|--------|--------|
| Enables path decimation for intermediate waypoints | ADS-B data is imperfect during landings and taxi |
| Fully customizable | Potentially long run time |
| No dependency on external data sources | Longer initial development and debugging |

---

### Option 2 — Web Scraping

Scrape airport-to-airport route data keyed by flight number from an existing source (e.g. [airline-route-data](https://github.com/Jonty/airline-route-data/blob/main/scrape_airline_routes.py)).

| ✅ Pros | ❌ Cons |
|--------|--------|
| No airport inference — data is authoritative | Dependent on third-party data and structure |
| Lower implementation complexity | Not customizable |
| | Only captures endpoint airports, not intermediate segments |

---

### Option 3 — ML Next-Position Prediction

Train a model to predict the next ADS-B message (lat, lon, altitude, time) given the previous *n* messages.

| ✅ Pros | ❌ Cons |
|--------|--------|
| Potentially the most accurate | Black-box — difficult to interpret |
| No manual probability assignment | Significant training time required |

---
<br/>

# Route Predictor — Implementation Decision Matrix

Scores are 1–5 (higher = better). Ratings are preliminary/vibes-based.

| Criteria | Option 1 — ADS-B Analysis | Option 2 — Web Scraping | Option 3 — ML Model |
|----------|:---:|:---:|:---:|
| **Effort & Speed** | | | |
| Time to first result | 3/5 | 4/5 | 1/5 |
| Implementation complexity | 3/5 | 4/5 | 1/5 |
| **Confidence in Output** | | | |
| Trust in the data | 3/5 | 4/5 | 2/5 |
| Debuggability | 4/5 | 3/5 | 1/5 |
| **Fit for Purpose** | | | |
| Route detail | 5/5 | 2/5 | 4/5 |
| Customizability | 5/5 | 1/5 | 3/5 |
| **Risk** | | | |
| External dependency | 5/5 | 2/5 | 4/5 |
| Long-term maintainability | 4/5 | 2/5 | 4/5 |
| **Total** | **32/40** | **22/40** | **20/40** |


# Data Model

## Start With these Tables

### `heatmap_bins`
Spatial trajectory segments, used for path reconstruction and analysis.

| Column | Type | Description |
|--------|------|-------------|
| `h3_index` | PK | |
| `lat_center` | float | |
| `lon_center` | float | |
| `contains_airport` | bool | |
| `traversal_count` |int||

### `route_segments`
Spatial trajectory segments, used for path reconstruction and analysis.

| Column | Type | Description |
|--------|------|-------------|
| `id` | PK | |
| `start_bin` | hex code | |
| `end_bin` | hex code | |
| `transition_count` |int||

### `route_stats`
per route per aircraft statistics 
per aircraft we want (ave speed, ave altitude, ave vertical rate, ave ias (airspeed))
these stats should be linked to edges (segments)
new entry in the table for each aircraft and each altitude band


| Column | Type | Description |
|--------|------|-------------|
| `segment_id` | FK → route_segments | |
| `aircraft_type` | string | |
| `ave_gnd_speed` | float | |
| `altitude_band` | float | Use FL avi designation |
| `ave_vert_rate` | float | |
| `ave_ias` | float | indicated air speed |
| `heading_variance` | float | how consistent is the heading|


### `segment_transitions`
Learned transition probabilities between trajectory segments for next-segment prediction and behavior modeling.

| Column | Type | Description |
|--------|------|-------------|
| `id` | PK | |
| `from_segment_id` | FK → route_segments | |
| `to_segment_id` | FK → route_segments | |
| `aircraft_type` | text | |
| `db_flags` | int | |
| `altitude_band` | text | |
| `time_of_day` | text | |
| `transition_count` | int | |
| `probability` | float | |
| `confidence` | float | |
| `last_updated` | timestamp | |




<br/>
<br/>

## OLD


### `flights`
Individual flight instances reconstructed from ADS-B data — a single aircraft movement from departure to arrival.

| Column | Type | Description |
|--------|------|-------------|
| `id` | PK | |
| `aircraft_icao` | text | |
| `flight_number` | text | |
| `departure_airport` | text | |
| `arrival_airport` | text | |
| `departure_time` | timestamp | |
| `arrival_time` | timestamp | |
| `duration_seconds` | int | |
| `distance_nm` | float |nautical miles |
| `route_id` | FK → routes | |

---

### `route_segments`
Ordered spatial-temporal trajectory segments for each flight, used for path reconstruction and analysis.

| Column | Type | Description |
|--------|------|-------------|
| `id` | PK | |
| `flight_id` | FK → flights | |
| `geom` | geometry | |
| `start_lat` |float||
| `start_lon` | float | |
| `start_alt` | int||
| `end_lat` |float||
| `end_lon` | float | |
| `end_alt` | int||
| `start_time` | timestamp | |
| `end_time` | timestamp | |
| `altitude_avg` | float | |
| `speed_avg` | float | |

---

### `routes`
Aggregated airport-to-airport connections derived from multiple flights, forming canonical route definitions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | PK | |
| `origin_airport` | text | |
| `destination_airport` | text | |
| `flight_count` | int | |
| `aircraft_count` | int | |
| `avg_duration_seconds` | int | |
| `avg_distance_nm` | float | |
| `confidence` | float | |
| `last_updated` | timestamp | |

---

### `flight_route_mapping`
Probabilistic assignments linking individual flights to candidate routes, including confidence and inference method metadata.

| Column | Type | Description |
|--------|------|-------------|
| `id` | PK | |
| `flight_id` | FK → flights | |
| `route_id` | FK → routes | |
| `confidence` | float | |
| `method` | text | Inference method used |
| `features` | json | Supporting feature data |

---

### `segment_transitions`
Learned transition probabilities between trajectory segments for next-segment prediction and behavior modeling.

| Column | Type | Description |
|--------|------|-------------|
| `id` | PK | |
| `from_segment_id` | FK → route_segments | |
| `to_segment_id` | FK → route_segments | |
| `aircraft_type` | text | |
| `db_flags` | int | |
| `altitude_band` | text | |
| `time_of_day` | text | |
| `transition_count` | int | |
| `probability` | float | |
| `confidence` | float | |
| `last_updated` | timestamp | |

---

### `segment_route_mapping`
Links fine-grained trajectory segments to higher-level routes with probabilistic weighting for explainability and refinement.

| Column | Type | Description |
|--------|------|-------------|
| `segment_id` | FK → route_segments | |
| `route_id` | FK → routes | |
| `probability` | float | |

---

### `route_stats`
per route per aircraft statistics 
per aircraft we want (ave speed, ave altitude, ave vertical rate, ave ias (airspeed))
these stats should be linked to edges (segments)
new entry in the table for each aircraft and each altitude band


| Column | Type | Description |
|--------|------|-------------|
| `segment_id` | FK → route_segments | |
| `aircraft_type` | string | |
| `ave_gnd_speed` | float | |
| `altitude_band` | float | Use FL avi designation |
| `ave_vert_rate` | float | |
| `ave_ias` | float | indicated air speed |