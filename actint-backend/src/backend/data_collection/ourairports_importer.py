from pathlib import Path

from backend.data_processing.query_database import get_conn, DatabaseConnectionTypes

DATA_DIR = Path(__file__).parent / "data" / "csv" / "ourairports"

FILES = {
    "countries": DATA_DIR / "countries.csv",
    "regions": DATA_DIR / "regions.csv",
    "airports": DATA_DIR / "world-airports.csv",
    "frequencies": DATA_DIR / "airport-frequencies.csv",
    "runways": DATA_DIR / "runways.csv",
    "navaids": DATA_DIR / "navaids.csv",
}



def create_schema(conn):
    with conn.cursor() as cur:

        # Countries
        cur.execute("""
        CREATE TABLE IF NOT EXISTS avi_countries (
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE,
            name TEXT,
            continent TEXT,
            wikipedia_link TEXT,
            keywords TEXT
        );
        """)

        # Regions
        cur.execute("""
        CREATE TABLE IF NOT EXISTS avi_regions (
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE,
            local_code TEXT,
            name TEXT,
            continent TEXT,
            iso_country TEXT REFERENCES avi_countries(code),
            wikipedia_link TEXT,
            keywords TEXT
        );
        """)

        # Airports
        cur.execute("""
        CREATE TABLE IF NOT EXISTS airports (
            id INTEGER PRIMARY KEY,
            ident TEXT UNIQUE NOT NULL,
            type TEXT,
            name TEXT,
            latitude_deg DOUBLE PRECISION NOT NULL,
            longitude_deg DOUBLE PRECISION NOT NULL,
            elevation_ft INTEGER,
            continent TEXT,
            country_name TEXT,
            iso_country TEXT REFERENCES avi_countries(code),
            region_name TEXT,
            iso_region TEXT REFERENCES avi_regions(code),
            local_region TEXT,
            municipality TEXT,
            scheduled_service BOOLEAN,
            gps_code TEXT,
            icao_code TEXT,
            iata_code TEXT,
            local_code TEXT,
            home_link TEXT,
            wikipedia_link TEXT,
            keywords TEXT,
            score INTEGER,
            last_updated TIMESTAMPTZ
        );
        """)

        # Frequencies
        cur.execute("""
        CREATE TABLE IF NOT EXISTS airport_frequencies (
            id INTEGER PRIMARY KEY,
            airport_ref INTEGER REFERENCES airports(id),
            airport_ident TEXT REFERENCES airports(ident),
            type TEXT,
            description TEXT,
            frequency_mhz REAL
        );
        """)

        # Runways
        cur.execute("""
        CREATE TABLE IF NOT EXISTS runways (
            id INTEGER PRIMARY KEY,
            airport_ref INTEGER REFERENCES airports(id),
            airport_ident TEXT REFERENCES airports(ident),
            length_ft INTEGER,
            width_ft INTEGER,
            surface TEXT,
            lighted BOOLEAN,
            closed BOOLEAN,
            le_ident TEXT,
            le_latitude_deg DOUBLE PRECISION,
            le_longitude_deg DOUBLE PRECISION,
            le_elevation_ft INTEGER,
            le_heading_degT DOUBLE PRECISION,
            le_displaced_threshold_ft INTEGER,
            he_ident TEXT,
            he_latitude_deg DOUBLE PRECISION,
            he_longitude_deg DOUBLE PRECISION,
            he_elevation_ft INTEGER,
            he_heading_degT DOUBLE PRECISION,
            he_displaced_threshold_ft INTEGER
        );
        """)

        # Navaids
        cur.execute("""
        CREATE TABLE IF NOT EXISTS avi_navaids (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            ident TEXT,
            name TEXT,
            type TEXT,
            frequency_khz INTEGER,
            latitude_deg DOUBLE PRECISION,
            longitude_deg DOUBLE PRECISION,
            elevation_ft INTEGER,
            iso_country TEXT REFERENCES avi_countries(code),
            dme_frequency_khz INTEGER,
            dme_channel TEXT,
            dme_latitude_deg DOUBLE PRECISION,
            dme_longitude_deg DOUBLE PRECISION,
            dme_elevation_ft INTEGER,
            slaved_variation_deg DOUBLE PRECISION,
            magnetic_variation_deg DOUBLE PRECISION,
            usageType TEXT,
            power TEXT,
            associated_airport TEXT REFERENCES airports(ident)
        );
        """)

    conn.commit()
    print("Schema created.")



def copy_csv(conn, table, columns, path, preprocess=None):
    """
    Generic copy function that will copy a csv to a defined pre-created sql table
    Args:
        conn: sql connection to DB
        table: sql table name of the destination table
        columns: sql column names of the destination table
        path: path to the csv file to copy
        preprocess: run a parsing function on the csv line to clean it as desired
    """
    with conn.cursor() as cur:
        with open(path, "r", encoding="utf-8") as f:
            next(f)

            with cur.copy(f"""
                COPY {table} ({','.join(columns)})
                FROM STDIN
                WITH (FORMAT CSV, QUOTE '"', DELIMITER ',', NULL '')
            """) as copy:

                for line in f:
                    if preprocess:
                        line = preprocess(line)
                    copy.write(line)

    conn.commit()
    print(f"Loaded {table}")



def fix_yes_no(line):
    # Convert yes/no → true/false for scheduled_service
    return line.replace(",yes,", ",true,").replace(",no,", ",false,")


def fix_01_bool(line):
    # Convert ,1, and ,0, to boolean
    return line.replace(",1,", ",true,").replace(",0,", ",false,")



def load_all(conn):
    """
    loading pipeline, order matters here for the foreign keys
    """

    # 1. Countries
    copy_csv(conn, "avi_countries",
        ["id","code","name","continent","wikipedia_link","keywords"],
        FILES["countries"]
    )

    # 2. Regions (depends on countries)
    copy_csv(conn, "avi_regions",
        ["id","code","local_code","name","continent","iso_country","wikipedia_link","keywords"],
        FILES["regions"]
    )

    # 3. Airports (depends on regions + countries)
    copy_csv(conn, "airports",
        ["id","ident","type","name","latitude_deg","longitude_deg","elevation_ft",
            "continent","country_name","iso_country","region_name","iso_region","local_region",
            "municipality","scheduled_service","gps_code","icao_code","iata_code","local_code",
            "home_link","wikipedia_link","keywords","score","last_updated"],
        FILES["airports"]
    )

    # 4. Frequencies
    copy_csv(conn, "airport_frequencies",
        ["id","airport_ref","airport_ident","type","description","frequency_mhz"],
        FILES["frequencies"]
    )

    # 5. Runways
    copy_csv(conn, "runways",
        ["id","airport_ref","airport_ident","length_ft","width_ft","surface",
         "lighted","closed","le_ident","le_latitude_deg","le_longitude_deg",
         "le_elevation_ft","le_heading_degT","le_displaced_threshold_ft",
         "he_ident","he_latitude_deg","he_longitude_deg","he_elevation_ft",
         "he_heading_degT","he_displaced_threshold_ft"],
        FILES["runways"],
    )

    # 6. Navaids
    copy_csv(conn, "avi_navaids",
        ["id","filename","ident","name","type","frequency_khz",
         "latitude_deg","longitude_deg","elevation_ft","iso_country",
         "dme_frequency_khz","dme_channel","dme_latitude_deg",
         "dme_longitude_deg","dme_elevation_ft","slaved_variation_deg",
         "magnetic_variation_deg","usageType","power","associated_airport"],
        FILES["navaids"]
    )




def main():
    with get_conn(conn_type=DatabaseConnectionTypes.ADSB) as conn:
        create_schema(conn)
        load_all(conn)


if __name__ == "__main__":
    main()