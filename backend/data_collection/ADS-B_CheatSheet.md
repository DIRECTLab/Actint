# ADS-B Data Format CheatSheet

Use this cheat sheet to get a quick overview of what is included in the ADS-B data we will be using. 
This data is coming from globe_history_202* repos on [ASD-B.lol's github](https://github.com/adsblol).
The data was decoded and recorded using Readsb which defines the json formatting.

## References 
1. readsb ADS-B JSON Scheme - [Documentation](https://github.com/wiedehopf/readsb/blob/dev/README-json.md#trace-jsons)
2. List of aircraft registration prefixes - [Wiki](https://en.wikipedia.org/wiki/List_of_aircraft_registration_prefixes)
3. List of aircraft type designations - [FAA pdf](https://www.faa.gov/documentLibrary/media/Order/2019-10-10_Order_JO_7360.1E_Aircraft_Type_Designators_FINAL.pdf)


## Example Data
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

