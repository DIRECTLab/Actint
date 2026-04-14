import json

INPUT_FILE = "testing_data.json"
OUTPUT_FILE = "flattened_traces.json"

def process_file():
    with open(INPUT_FILE, "r") as f:
        data = json.load(f)

    with open(OUTPUT_FILE, "w") as out:

        for record in data:
            base = {
                "icao": record.get("icao"),
                "reg_num": record.get("r"),
                "type": record.get("t"),
                "desc": record.get("desc"),
                "dbFlags": record.get("dbFlags"),
                "military": bool(record.get("dbFlags", 0) & 1),
                #"interesting": bool(record.get("dbFlags", 0) & 2),
                #"pia": bool(record.get("dbFlags", 0) & 4),
                #"ladd": bool(record.get("dbFlags", 0) & 8),
                #"timestamp": record.get("timestamp"),
            }

            TIMESTAMP = record.get("timestamp")

            trace_list = record.get("trace", [])

            for entry in trace_list:
                if not isinstance(entry, list):
                    continue

                # unpack with safe indexing
                trace_obj = {
                    **base,
                    #"TIME_OFFSET": entry[0] if len(entry) > 0 else None,
                    "TIMESTAMP": TIMESTAMP + (entry[0] if len(entry) > 0 else None),
                    "lat": entry[1] if len(entry) > 1 else None,
                    "lon": entry[2] if len(entry) > 2 else None,
                    "altitude": entry[3] if len(entry) > 3 else None,
                    "ground_speed": entry[4] if len(entry) > 4 else None,
                    "track": entry[5] if len(entry) > 5 else None,
                    "flags": entry[6] if len(entry) > 6 else None,
                    "vertical_rate": entry[7] if len(entry) > 7 else None,
                    #"aircraft_meta": entry[8] if len(entry) > 8 else None,
                    "position_source": entry[9] if len(entry) > 9 else None,
                    "alt_geom": entry[10] if len(entry) > 10 else None,
                    "geom_rate": entry[11] if len(entry) > 11 else None,
                    "ias": entry[12] if len(entry) > 12 else None,
                    "roll": entry[13] if len(entry) > 13 else None,
                }

                # optional: decode flags
                flags = trace_obj["flags"]
                if isinstance(flags, int):
                    trace_obj["flag_pos_stale"] = bool(flags & 1)
                    trace_obj["flag_new_leg"] = bool(flags & 2)
                    trace_obj["flag_geom_rate"] = bool(flags & 4)
                    trace_obj["flag_geom_alt"] = bool(flags & 8)

                out.write(json.dumps(trace_obj) + "\n")

if __name__ == "__main__":
    process_file()