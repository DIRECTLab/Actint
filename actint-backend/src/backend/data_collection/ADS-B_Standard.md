# ADS-B Data Standard (Schema + Usage)

## 1. Overview

This dataset stores decoded ADS-B aircraft position reports in a **time-partitioned PostgreSQL table**. Each row represents a single aircraft message.
This data is coming from globe_history_202* repos on [ASD-B.lol's github](https://github.com/adsblol).
The data was decoded and recorded using Readsb which defines the json formatting [Documentation](https://github.com/wiedehopf/readsb/blob/dev/README-json.md#trace-jsons)


## 2. Core Table: `adsb_positions`

Each row represents one ADS-B position message.

| Field            | Type        | Meaning                                                                                                       | Units        |
| -----------------| ----------- | --------------------------------------------------------------------------------------------------------------| ------------ |
| `id`             | BIGSERIAL   | Internal SQL row ID                                                                                           | —            |
| `icao`           | TEXT        | Aircraft ICAO 24-bit identifier                                                                               | —            |
| `timestamp`      | TIMESTAMPTZ | Message timestamp from aircraft                                                                               | UTC datetime |
| `lat`            | REAL        | Latitude                                                                                                      | degrees      |
| `lon`            | REAL        | Longitude                                                                                                     | degrees      |
| `altitude`       | INTEGER     | Barometric altitude                                                                                           | ft           |
| `ground_speed`   | REAL        | Ground speed                                                                                                  | knots        |
| `track`          | REAL        | Direction of travel                                                                                           | degrees      |
| `flags`          | INTEGER     | state flags (see [Ref 1](https://github.com/wiedehopf/readsb/blob/dev/README-json.md#trace-jsons))            | —            |
| `vertical_rate`  | INTEGER     | Climb/descent rate                                                                                            | ft/min       |
| `flight_number`  | TEXT        | Airline flight identifier                                                                                     | —            |
| `emergency`      | TEXT        | Emergency status                                                                                              | —            |
| `category`       | TEXT        | Emiiter category/class (used to identify vehicle class when type or desc is missing)                          | —            |
| `rc_meters`      | INTEGER     | Position uncertainty estimate, aka radius of containment                                                      | m            |
| `pos_source`     | TEXT        | Data source (ADS-B / MLAT / fused)                                                                            | —            |
| `alt_geom`       | INTEGER     | geometric, GNSS/INS, altitude referenced to the WGS84 ellipsoid                                               | ft           |
| `geom_rate`      | INTEGER     | Geometric vertical rate                                                                                       | ft/min       |
| `ias`            | TEXT        | Indicated airspeed                                                                                            | knots        |
| `roll`           | TEXT        | Roll angle                                                                                                    | degrees      |
| `flag_pos_stale` | BOOLEAN     | flag for stale position as determined by Readsb                                                               | —            |
| `flag_new_leg`   | BOOLEAN     | flag for new leg of flight                                                                                    | —            |
| `flag_geom_rate` | BOOLEAN     | if true vertical rate is geometric and not barometric                                                         | —            |
| `flag_geom_alt`  | BOOLEAN     | if true altitude is geometric and not barometric                                                              | —            |
| `created_at`     | TIMESTAMPTZ | Ingestion timestamp                                                                                           | UTC datetime |


## 3. Partitioning Model

* Partition key: `timestamp`
* Strategy: **monthly range partitions**

Example:

```
adsb_positions_2025_08 → [2025-08-01, 2025-08-31]
adsb_positions_2025_09 → [2025-09-01, 2025-9-30]
```

Includes:

* automatic routing via Postgres (don't have to dig into partition tables for sql queries just use the parent table)
* default partition for out-of-range or anomalous data



## 4. Aircraft Metadata Table: `aircraft`

Stores persistent aircraft identity information.

| Field         | Type              | Meaning                                     |
| ------------- | ------------------| --------------------------------------------|
| `icao`        | TEXT PRIMARY KEY  | Primary aircraft identifier                 |
| `reg_num`     | TEXT              | Tail number                                 |
| `type`        | TEXT              | Aircraft model                              |
| `description` | TEXT              | Human-readable model number description     |
| `db_flags`    | INTEGER           | classification flags (see cheatsheet below) |
| `military`    | BOOLEAN           | if true aircraft is Military                |
| `first_seen`  | TIMESTAMPTZ       | First observed timestamp                    |
| `last_seen`   | TIMESTAMPTZ       | Last observed timestamp                     |



## 5. Usage Patterns

### 1. Flight Reconstruction (Per-Aircraft Tracking)

Rebuild full aircraft trajectories using ICAO + time ordering.

```sql id="u1f8aa"
SELECT *
FROM adsb_positions
WHERE icao = 'A35854'
AND timestamp BETWEEN '2025-08-22 00:00:00' AND '2025-08-22 23:59:59'
ORDER BY timestamp;
```

**Used for:**

* flight path reconstruction
* climb / cruise / descent segmentation
* replaying historical flights



### 2. Airspace / Region Monitoring

Query aircraft present in a geographic region during a time window.

```sql id="u2f7bb"
SELECT *
FROM adsb_positions
WHERE timestamp BETWEEN '2025-08-22 12:00:00' AND '2025-08-22 12:30:00'
AND lat BETWEEN 25.0 AND 27.0
AND lon BETWEEN -81.0 AND -79.0;
```

**Used for:**

* air traffic density mapping
* regional congestion analysis
* situational awareness over specific airspace



### 3. Fleet / Airline Tracking

Analyze behavior of a specific airline flight or fleet segment.

```sql id="u3f6cc"
SELECT *
FROM adsb_positions
WHERE flight_number = 'JBU2080'
AND timestamp >= NOW() - INTERVAL '1 day'
ORDER BY timestamp;
```

**Used for:**

* airline route tracking
* schedule deviation analysis
* operational performance monitoring



## 6. Key Design Notes

* `timestamp` is the authoritative time axis
* `icao` identifies aircraft identity across all data
* `id` is partition-local and not globally unique
* Missing fields are expected due to variable broadcast formats



  <br>
# CheatSheet and References 

Use this cheat sheet to get a quick overview of what is included in the ADS-B data we will be using. 

## References 
1. readsb ADS-B JSON Scheme - [Documentation](https://github.com/wiedehopf/readsb/blob/dev/README-json.md#trace-jsons)
2. List of aircraft registration prefixes - [Wiki](https://en.wikipedia.org/wiki/List_of_aircraft_registration_prefixes)
3. List of aircraft type designations - [FAA pdf](https://www.faa.gov/documentLibrary/media/Order/2019-10-10_Order_JO_7360.1E_Aircraft_Type_Designators_FINAL.pdf)


## Example Raw JSON Data
```json
{"icao":"aac800",
"r":"N794MM",
"t":"PA46",
"dbFlags":0,"desc":"PIPER PA-46-310/350",
"version": "readsb 3.16.6 b985831",
"timestamp": 1773100800.000,
"trace":[ 
[38849.24,-23.689819,-49.780477,27000,219.2,16.7,1,0,{"type":"adsb_icao","alt_geom":28650,"track":16.70,"baro_rate":0,"nic":8,"rc":186,"version":0,"nac_p":8,"nac_v":2,"sil":2,"sil_type":"perhour","alert":0,"spi":0},"adsb_icao",28650,null,null,null],
[38862.86,-23.676468,-49.776099,27000,220.5,16.9,0,0,null,"adsb_icao",28650,null,null,null],
[38869.44,-23.670044,-49.773966,27000,220.5,16.9,0,0,null,"adsb_icao",28650,null,null,null],
[38896.56,-23.643463,-49.765164,27000,220.5,16.9,1,0,null,"adsb_icao",28650,null,null,null],
[38913.16,-23.627060,-49.759725,27000,222.7,17.0,1,0,{"type":"adsb_icao","alt_geom":28650,"track":16.97,"baro_rate":0,"category":"A1","nic":8,"rc":186,"version":2,"nic_baro":1,"nac_p":9,"nac_v":2,"sil":3,"sil_type":"perhour","gva":2,"sda":2,"alert":0,"spi":0},"adsb_icao",28650,null,null,null],
[38932.53,-23.607880,-49.753367,27000,223.9,17.1,0,0,null,"adsb_icao",28650,null,null,null],
[38952.51,-23.588196,-49.746806,27000,224.9,17.1,0,0,null,"adsb_icao",28650,null,null,null],
[38972.28,-23.568327,-49.740186,27000,225.9,17.0,0,0,null,"adsb_icao",28650,null,null,null]]
 }
```

## Example Flattened JSON Data
```json
{"ICAO": "af6c00", "REG_NUM": "170751", "TYPE": "BE20", "DESC": "BEECH 200 Super King Air", "DBFLAGS": 1, "MILITARY": true, "TIMESTAMP": 1741790332.51, "LAT": 27.877808, "LON": -97.212784, "ALTITUDE": 10575, "GROUND_SPEED": 192.4, "TRACK": 351.0, "FLAGS": 5, "VERTICAL_RATE": 1856, "POS_SOURCE": "adsb_icao", "ALT_GEOM": 10950, "GEOM_RATE": 1856, "IAS": null, "ROLL": null, "FLIGHT_NUMBER": "BGST441 ", "EMERGENCY": "none", "CATEGORY": "A1", "NAV_ALTITUDE_MCP": 15008, "NAV_ALTITUDE_FMS": null, "NAV_MODES": null, "NAV_HEADING": 347.34, "NIC": 8, "RC_METERS": 186, "NIC_BARO": 1, "NAC_P": 10, "NAC_V": 1, "SIL": 3, "SIL_TYPE": "perhour", "GVA": 2, "SDA": 2, "WD": null, "WS": null, "FLAG_POS_STALE": true, "FLAG_NEW_LEG": false, "FLAG_GEOM_RATE": true, "FLAG_GEOM_ALT": false}
```

## JSON Key/Name Descriptions

* **icao** - digital identifier for aircraft, persistant, can be used for identification
  * The identifier may start with '~', this means that the address is a non-ICAO (e.g. from TIS-B).
* **r** - registration number, persistant, can be used for identification as well as country of origin detection  
  * See [Reference 2](https://en.wikipedia.org/wiki/List_of_aircraft_registration_prefixes)
* **t** - aircraft type - gives info on weight class, engine count, and many other factors
  * See [Reference 3](https://www.faa.gov/documentLibrary/media/Order/2019-10-10_Order_JO_7360.1E_Aircraft_Type_Designators_FINAL.pdf)
* **dbFlags** - identifies useful characteristics using bitwise logic, we will use military identifier the most
  
  ```python
   military = dbFlags & 1;
   interesting = dbFlags & 2;
   PIA = dbFlags & 4;
   LADD = dbFlags & 8;
    ```

* **desc** - manufacturer and model of the aircraft
* **version** - version of readsb program used to generate this json
* **timestamp** - unix timestamp in seconds since epoch (1970)

### JSON Trace Key/Name Descriptions

```yaml
    trace: [
        [ seconds after timestamp,
            lat,
            lon,
            altitude in ft or "ground" or null,
            ground speed in knots or null,
            track in degrees or null, (if altitude == "ground", this will be true heading instead of track)
            flags as a bitfield: (use bitwise and to extract data)
                (flags & 1 > 0): position is stale (no position received for 20 seconds before this one)
                (flags & 2 > 0): start of a new leg (tries to detect a separation point between landing and takeoff that separates fligths)
                (flags & 4 > 0): vertical rate is geometric and not barometric
                (flags & 8 > 0): altitude is geometric and not barometric
             ,
            vertical rate in fpm or null,
            aircraft object with extra details or null, (see aircraft.json documentation (Ref 1), note that not all fields are present as some are in the values above)
            // the following fields only in files generated 2022 and later (this applies to us):
            type / source of this position or null,
            geometric altitude or null,
            geometric vertical rate or null,
            indicated airspeed or null,
            roll angle or null
        ],
        [next entry like the one before],
        [next entry like the one before],
    ]
```


