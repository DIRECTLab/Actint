import os
import psycopg

reg_num_to_country_iso = [
        ('N', 'US'),
        ('C', 'CA'),
        ('G', 'GB'),
        ('F', 'FR'),
        ('D', 'DE'),
        ('I', 'IT'),
        ('YA', 'AF'),
        ('ZA', 'AL'),
        ('7T', 'DZ'),
        ('C3', 'AD'),
        ('D2', 'AO'),
        ('VP-A', 'AI'),
        ('V2', 'AG'),
        ('LV', 'AR'),
        ('LQ', 'AR', 'government-owned'),
        ('EK', 'AM'),
        ('P4', 'AW'),
        ('VH', 'AU'),
        ('OE', 'AT'),
        ('4K', 'AZ'),
        ('C6', 'BS'),
        ('A9C', 'BH'),
        ('S2', 'BD'),
        ('8P', 'BB'),
        ('EW', 'BY'),
        ('OO', 'BE'),
        ('V3', 'BZ'),
        ('TY', 'BJ'),
        ('VP-B', 'BM'),
        ('VQ-B', 'BM'),
        ('A5', 'BT'),
        ('CP', 'BO'),
        ('E7', 'BA'),
        ('A2', 'BW'),
        ('PP', 'BR'),
        ('PT', 'BR'),
        ('PR', 'BR'),
        ('PU', 'BR', 'micro-lights and experimental LSA aircraft'),
        ('PS', 'BR'),
        ('VP-L', 'VG'),
        ('V8', 'BN'),
        ('LZ', 'BG'),
        ('XT', 'BF'),
        ('9U', 'BI'),
        ('XU', 'KH'),
        ('TJ', 'CM'),
        ('D4', 'CV'),
        ('VP-C', 'KY'),
        ('VQ-C', 'KY'),
        ('TL', 'CF'),
        ('TT', 'TD'),
        ('CC', 'CL'),
        ('B', 'CN', 'shared allocation with Taiwan (TW)'),
        ('HJ', 'CO'),
        ('HK', 'CO'),
        ('D6', 'KM'),
        ('TN', 'CG'),
        ('9S', 'CD'),
        ('9T', 'CD'),
        ('E5', 'CK'),
        ('TI', 'CR'),
        ('9A', 'HR'),
        ('CU', 'CU'),
        ('5B', 'CY'),
        ('OK', 'CZ'),
        ('OY', 'DK'),
        ('J2', 'DJ'),
        ('J7', 'DM'),
        ('HI', 'DO'),
        ('4W', 'TL'),
        ('HC', 'EC'),
        ('SU', 'EG'),
        ('YS', 'SV'),
        ('3C', 'GQ'),
        ('E3', 'ER'),
        ('ES', 'EE'),
        ('3D', 'SZ'),
        ('3DC', 'SZ'),
        ('ET', 'ET'),
        ('VP-F', 'FK'),
        ('DQ', 'FJ'),
        ('OH', 'FI'),
        ('F-O', 'PF', 'check geo location data, could also be from French Guiana (GF), French West Indies, New Caledonia (NC), Reunion (RE) or Martinique (MQ)'),
        ('TR', 'GA'),
        ('C5', 'GM'),
        ('4L', 'GE'),
        ('9G', 'GH'),
        ('9GR', 'GH', 'remotely piloted aircraft'),
        ('VP-G', 'GI'),
        ('SX', 'GR'),
        ('J3', 'GD'),
        ('TG', 'GT'),
        ('2', 'GG'),
        ('3X', 'GN'),
        ('J5', 'GW'),
        ('8R', 'GY'),
        ('HH', 'HT'),
        ('HR', 'HN'),
        ('B-H', 'HK'),
        ('B-K', 'HK'),
        ('B-L', 'HK'),
        ('HA', 'HU'),
        ('TF', 'IS'),
        ('VT', 'IN'),
        ('PK', 'ID'),
        ('EP', 'IR'),
        ('YI', 'IQ'),
        ('EI', 'IE', 'normal allocation (not VIP or business aircraft)'),
        ('EJ', 'IE', 'VIP or business aircraft'),
        ('M', 'IM'),
        ('4X', 'IL'),
        ('4Z', 'IL'),
        ('TU', 'CI'),
        ('6Y', 'JM'),
        ('JA', 'JP'),
        ('JR', 'JP', 'ultralight, gyro, or other homebuilt aircraft'),
        ('JY', 'JO'),
        ('4YB', 'JO', 'also iraq (IQ) for international operating agency: Arab Air Cargo'),
        ('UP', 'KZ'),
        ('5Y', 'KE'),
        ('T3', 'KI'),
        ('Z6', 'XK'),
        ('9K', 'KW'),
        ('EX', 'KG'),
        ('RDPL', 'LA'),
        ('YL', 'LV'),
        ('LV', 'LV', 'balloons and gliders'),
        ('OD', 'LB'),
        ('7P', 'LS'),
        ('A8', 'LR'),
        ('5A', 'LY'),
        ('HB', 'CH', 'shared allocation with liechtenstein (LI)'),
        ('LY', 'LT'),
        ('LX', 'LU'),
        ('B-M', 'MO'),
        ('5R', 'MG'),
        ('7Q', 'MW'),
        ('9M', 'MY'),
        ('8Q', 'MV'),
        ('TZ', 'ML'),
        ('9H', 'MT'),
        ('V7', 'MH'),
        ('5T', 'MR'),
        ('3B', 'MU'),
        ('XA', 'MX', 'commerical aircraft'),
        ('XB', 'MX', 'private aircraft'),
        ('XC', 'MX', 'government aircraft'),
        ('V6', 'FM'),
        ('ER', 'MD'),
        ('3A-M', 'MC'),
        ('JU', 'MN'),
        ('4O', 'ME'),
        ('VP-M', 'MS'),
        ('CN', 'MA'),
        ('C9', 'MZ'),
        ('XY', 'MM'),
        ('XZ', 'MM'),
        ('V5', 'NA'),
        ('C2', 'NR'),
        ('9N', 'NP', 'commerical aircraft'),
        ('9N-R', 'NP', 'government aircraft'),
        ('PH', 'NL'),
        ('PJ', 'CW', 'also used for Sint Maarten (SX) and Netherlands Antilles'),
        ('ZK', 'NZ'),
        ('ZL', 'NZ'),
        ('ZM', 'NZ'),
        ('YN', 'NI'),
        ('5U', 'NE'),
        ('5N', 'NG'),
        ('P', 'KP'),
        ('Z3', 'MK'),
        ('LN', 'NO'),
        ('A4O', 'OM'),
        ('AP', 'PK'),
        ('HP', 'PA'),
        ('P2', 'PG'),
        ('ZP', 'PY'),
        ('OB', 'PE'),
        ('RP', 'PH'),
        ('SP', 'PL', 'non-government aircraft'),
        ('SN', 'PL', 'government aircraft'),
        ('CR', 'PT'),
        ('CS', 'PT'),
        ('A7', 'QA'),
        ('YR', 'RO'),
        ('RA', 'RU', 'non-government aircraft'),
        ('RF', 'RU', 'government aircraft'),
        ('9XR', 'RW'),
        ('VQ-H', 'SH'),
        ('V4', 'KN'),
        ('J6', 'LC'),
        ('J8', 'VC'),
        ('5W', 'WS'),
        ('T7', 'SM'),
        ('S9', 'ST'),
        ('HZ', 'SA'),
        ('6V', 'SN'),
        ('6W', 'SN'),
        ('YU', 'RS'),
        ('S7', 'SC'),
        ('9L', 'SL'),
        ('9V', 'SG'),
        ('OM', 'SK'),
        ('S5', 'SI'),
        ('H4', 'SB'),
        ('6O', 'SO'),
        ('ZS', 'ZA', 'type certified aircraft'),
        ('ZT', 'ZA', 'type certified rotorcraft, civil RPAS'),
        ('ZU', 'ZA', 'non-type certified aircraft'),
        ('HL', 'KR'),
        ('Z8', 'SS'),
        ('EC', 'ES', 'non-military aircraft'),
        ('EM', 'ES', 'military aircraft'),
        ('4R', 'LK'),
        ('ST', 'SD'),
        ('PZ', 'SR'),
        ('SE', 'SE'),
        ('YK', 'SY'),
        ('EY', 'TJ'),
        ('5H', 'TZ'),
        ('HS', 'TH'),
        ('U', 'TH', 'ultralight aircraft'),
        ('5V', 'TG'),
        ('A3', 'TO'),
        ('9Y', 'TT'),
        ('TS', 'TN'),
        ('TC', 'TR'),
        ('EZ', 'TM'),
        ('VQ-T', 'TC'),
        ('T2', 'TV'),
        ('5X', 'UG'),
        ('UR', 'UA'),
        ('A6', 'AE'),
        ('DU', 'AE', 'Dubai police aircraft'),
        ('CX', 'UY'),
        ('UK', 'UZ'),
        ('YJ', 'VU'),
        ('YV', 'VE'),
        ('VN', 'VN'),
        ('7O', 'YE'),
        ('9J', 'ZM'),
        ('Z', 'ZW')

    ]


def get_conn():
    try:
        # Read environment variables
        db_config = {
            "host": os.getenv("DB_HOST"),
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASS"),
            "port": int(os.getenv("DB_PORT")),
        }

        # Validate required vars
        for key, value in db_config.items():
            if value is None:
                raise ValueError(f"Missing environment variable: {key}")

        # Connect
        conn = psycopg.connect(**db_config)
        return conn
        
    except Exception as e:
        print("Error:")
        print(e)


# ----------------------------
# SCHEMA
# ----------------------------
def create_schema(conn):
    with conn.cursor() as cur:

        # Regions
        cur.execute("""
        CREATE TABLE IF NOT EXISTS reg_num_to_country_iso (
            id SERIAL PRIMARY KEY,
            prefix TEXT UNIQUE NOT NULL,
            iso_country TEXT NOT NULL REFERENCES avi_countries(code),
            notes TEXT
        );
        """)

    conn.commit()
    print("Schema created.")


def normalize_data(data):
    normalized = []
    for row in data:
        if len(row) == 2:
            normalized.append((row[0], row[1], None))
        elif len(row) == 3:
            normalized.append(row)
        else:
            raise ValueError(f"Invalid row length: {row}")
    return normalized


def insert_aircraft_prefixes(conn):

    query = """
        INSERT INTO reg_num_to_country_iso
        (prefix, iso_country, notes)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING;
    """

    with conn.cursor() as cur:
        cur.executemany(query, normalize_data(reg_num_to_country_iso))

    conn.commit()



# ----------------------------
# MAIN
# ----------------------------
def main():
    with get_conn() as conn:
        create_schema(conn)
        insert_aircraft_prefixes(conn)


if __name__ == "__main__":
    main()