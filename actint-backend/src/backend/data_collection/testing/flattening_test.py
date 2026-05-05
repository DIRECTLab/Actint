import json

INPUT_FILE = "ref_data/testing_data.json"
OUTPUT_FILE = "flattened_traces.jsonl"

def process_file():
    with open(INPUT_FILE, "r") as f:
        data = json.load(f)

    with open(OUTPUT_FILE, "w") as out:

        flattened = []

        for record in data:

            base = {
                "ICAO": record.get("icao"),
                "REG_NUM": record.get("r") if record.get("r") else f"noRegData: {record.get("noRegData")}"  ,
                "TYPE": record.get("t"),
                "DESC": record.get("desc"),
                "DBFLAGS": record.get("dbFlags"),
                "MILITARY": bool(record.get("dbFlags", 0) & 1),
                #"interesting": bool(record.get("dbFlags", 0) & 2),
                #"pia": bool(record.get("dbFlags", 0) & 4),
                #"ladd": bool(record.get("dbFlags", 0) & 8),
                #"TIMESTAMP": record.get("timestamp"),
            }

            TIMESTAMP = record.get("timestamp")

            trace_list = record.get("trace", [])

            for entry in trace_list:
                if not isinstance(entry, list):
                    continue

                meta = entry[8] if len(entry) > 8 and isinstance(entry[8], dict) else {}
                
                # unpack with safe indexing
                trace_obj = {
                    **base,
                    #"TIME_OFFSET": entry[0] if len(entry) > 0 else None,
                    "TIMESTAMP": TIMESTAMP + (entry[0] if len(entry) > 0 else None),
                    "LAT": entry[1] if len(entry) > 1 else None,
                    "LON": entry[2] if len(entry) > 2 else None,
                    "ALTITUDE": entry[3] if len(entry) > 3 else None,
                    "GROUND_SPEED": entry[4] if len(entry) > 4 else None,
                    "TRACK": entry[5] if len(entry) > 5 else None,
                    "FLAGS": entry[6] if len(entry) > 6 else None,
                    "VERTICAL_RATE": entry[7] if len(entry) > 7 else None,
                    #"aircraft_meta": entry[8] if len(entry) > 8 else None,
                    "POS_SOURCE": entry[9] if len(entry) > 9 else None,
                    "ALT_GEOM": entry[10] if len(entry) > 10 else None,
                    "GEOM_RATE": entry[11] if len(entry) > 11 else None,
                    "IAS": entry[12] if len(entry) > 12 else None,
                    "ROLL": entry[13] if len(entry) > 13 else None,

                    # ===== NEW ADS-B METADATA =====
                    "FLIGHT_NUMBER": meta.get("flight"),
                    "EMERGENCY": meta.get("emergency"),
                    "CATEGORY": meta.get("category"),

                    "NAV_ALTITUDE_MCP": meta.get("nav_altitude_mcp"),
                    "NAV_ALTITUDE_FMS": meta.get("nav_altitude_fms"),
                    "NAV_MODES": meta.get("nav_modes"),
                    "NAV_HEADING": meta.get("nav_heading"),

                    "NIC": meta.get("nic"),
                    "RC_METERS": meta.get("rc"),

                    "NIC_BARO": meta.get("nic_baro"),
                    "NAC_P": meta.get("nac_p"),
                    "NAC_V": meta.get("nac_v"),

                    "SIL": meta.get("sil"),
                    "SIL_TYPE": meta.get("sil_type"),

                    "GVA": meta.get("gva"),
                    "SDA": meta.get("sda"),

                    "WD": meta.get("wd"),
                    "WS": meta.get("ws"),
                }

                # optional: decode flags
                flags = trace_obj["FLAGS"]
                if isinstance(flags, int):
                    trace_obj["FLAG_POS_STALE"] = bool(flags & 1)
                    trace_obj["FLAG_NEW_LEG"] = bool(flags & 2)
                    trace_obj["FLAG_GEOM_RATE"] = bool(flags & 4)
                    trace_obj["FLAG_GEOM_ALT"] = bool(flags & 8)
            
                #remove ground text on altitude and change to 0
                if trace_obj["ALTITUDE"] == "ground":
                    trace_obj["ALTITUDE"] = 0

                flattened.append(trace_obj)

                out.write(json.dumps(trace_obj) + "\n")

if __name__ == "__main__":
    process_file()