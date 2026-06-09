from pathlib import Path
from backend.mcp_servers.adsb.helpers.basic_tools import get_conn

DATA_DIR = Path(__file__).parent / "data" / "FAA" 

FILES = {
    "Routes": DATA_DIR / "ATS_Route.csv",
    "Points": DATA_DIR / "Designated_Point.csv"
}


# ----------------------------
# SCHEMA
# ----------------------------
def create_schema(conn):
    with conn.cursor() as cur:

        # routes
        cur.execute("""
        CREATE TABLE ats_routes (
            OBJECTID            INTEGER PRIMARY KEY,
            GLOBAL_ID           TEXT NOT NULL,

            IDENT               TEXT,
            TYPE_CODE           TEXT,
            LEVEL               TEXT,
            WKHR_CODE           TEXT,
            WKHR_RMK            TEXT,

            MAA_VAL             DOUBLE PRECISION,
            MAA_UOM             TEXT,

            MEA_E_VAL           DOUBLE PRECISION,
            MEA_E_UOM           TEXT,

            MEA_W_VAL           DOUBLE PRECISION,
            MEA_W_UOM           TEXT,

            GMEA_E_VAL          DOUBLE PRECISION,
            GMEA_E_UOM          TEXT,

            GMEA_W_VAL          DOUBLE PRECISION,
            GMEA_W_UOM          TEXT,

            DMEA_VAL            DOUBLE PRECISION,
            DMEA_UOM            TEXT,

            MOCA_VAL            DOUBLE PRECISION,
            MOCA_UOM            TEXT,

            MEAGAP             SMALLINT,

            TRUETRK            DOUBLE PRECISION,
            MAGTRK             DOUBLE PRECISION,
            REVTRUETRK         DOUBLE PRECISION,
            REVMAGTRK          DOUBLE PRECISION,

            NMAGTRK            DOUBLE PRECISION,
            NREVMAGTRK         DOUBLE PRECISION,

            LENGTH_VAL         DOUBLE PRECISION,

            COPDIST            DOUBLE PRECISION,
            COPNAV_ID          TEXT,

            REPATCSTAR         TEXT,
            REPATCEND          TEXT,

            DIRECTION          TEXT,
            FREQ_CLASS         TEXT,

            STATUS             SMALLINT,

            STARTPT_ID         TEXT,
            ENDPT_ID           TEXT,

            RTPORT_ID          TEXT,
            ENRINFO_ID         TEXT,

            WIDTHRIGHT         DOUBLE PRECISION,
            WIDTHLEFT          DOUBLE PRECISION,
            WIDTH_UOM          TEXT,

            MCA1_VAL           DOUBLE PRECISION,
            MCA1_UOM           TEXT,
            MCA1_DIR           TEXT,

            MCA2_VAL           DOUBLE PRECISION,
            MCA2_UOM           TEXT,
            MCA2_DIR           TEXT,

            MCAPT_ID           TEXT,
            MCAPT_TYPE         SMALLINT,

            TFLAG_CODE         SMALLINT,

            REMARKS            TEXT,

            AK_LOW             SMALLINT,
            AK_HIGH            SMALLINT,
            US_LOW             SMALLINT,
            US_HIGH            SMALLINT,
            US_AREA            SMALLINT,
            PACIFIC            SMALLINT,

            SHAPE_LENGTH       DOUBLE PRECISION
        );
        """)

        cur.execute("""
            COMMENT ON TABLE ats_routes IS 
            'FAA airway route segment dataset. Each row represents a route segment between two designated points defined by start and end point column.';
            
            COMMENT ON COLUMN ats_routes.OBJECTID IS 
            'Internal database object identifier.';
            
            COMMENT ON COLUMN ats_routes.GLOBAL_ID IS 
            'Globally unique identifier for this route feature.';
            
            COMMENT ON COLUMN ats_routes.IDENT IS 
            'Published route identifier (e.g. A332, B453).';
            
            COMMENT ON COLUMN ats_routes.TYPE_CODE IS 
            'Route type: CONV (navaid based route), ADV (advisory route), OCEAN (oceanic route), RNAV (Area Navigation), GRNAV (ground based RNAV), SUB (Substitute Route), UCON (Uncontrolled Route), DIR (direct or track), AKCAP (alaska capstone route)';
            
            COMMENT ON COLUMN ats_routes.LEVEL IS 
            'Altitude classification: U=High, L=Low, B=Both.';
            
            COMMENT ON COLUMN ats_routes.WKHR_CODE IS 
            'RMK - Indicates route is one-way during specified hours.';
            
            COMMENT ON COLUMN ats_routes.WKHR_RMK IS 
            'Hours during which a route is single directional.';
            
            COMMENT ON COLUMN ats_routes.MAA_VAL IS 
            'Maximum Authorized Altitude.';
            
            COMMENT ON COLUMN ats_routes.MAA_UOM IS 
            'Unit for MAA_VAL: FL (flight level) or FT (feet).';
            
            COMMENT ON COLUMN ats_routes.MEA_E_VAL IS 
            'Minimum Enroute Altitude eastbound.';
            
            COMMENT ON COLUMN ats_routes.MEA_E_UOM IS 
            'Unit for MEA_E_VAL.';
            
            COMMENT ON COLUMN ats_routes.MEA_W_VAL IS 
            'Minimum Enroute Altitude westbound.';
            
            COMMENT ON COLUMN ats_routes.MEA_W_UOM IS 
            'Unit for MEA_W_VAL.';
            
            COMMENT ON COLUMN ats_routes.GMEA_E_VAL IS 
            'GNSS-based Minimum Enroute Altitude eastbound.';
            
            COMMENT ON COLUMN ats_routes.GMEA_E_UOM IS 
            'Unit for GMEA_E_VAL.';
            
            COMMENT ON COLUMN ats_routes.GMEA_W_VAL IS 
            'GNSS-based Minimum Enroute Altitude westbound.';
            
            COMMENT ON COLUMN ats_routes.GMEA_W_UOM IS 
            'Unit for GMEA_W_VAL.';
            
            COMMENT ON COLUMN ats_routes.DMEA_VAL IS 
            'DME/DME/IRU Minimum Enroute Altitude.';
            
            COMMENT ON COLUMN ats_routes.DMEA_UOM IS 
            'Unit for DMEA_VAL.';
            
            COMMENT ON COLUMN ats_routes.MOCA_VAL IS 
            'Minimum Obstruction Clearance Altitude.';
            
            COMMENT ON COLUMN ats_routes.MOCA_UOM IS 
            'Unit for MOCA_VAL.';
            
            COMMENT ON COLUMN ats_routes.MEAGAP IS 
            'Indicates if a routes minimum enroute altitude is established with a gap in navigation signal coverage. 0=No, 1=Yes.';
            
            COMMENT ON COLUMN ats_routes.TRUETRK IS 
            'Forward true course/bearing.';
            
            COMMENT ON COLUMN ats_routes.MAGTRK IS 
            'Forward magnetic course/bearing.';
            
            COMMENT ON COLUMN ats_routes.REVTRUETRK IS 
            'Reverse true course/bearing.';
            
            COMMENT ON COLUMN ats_routes.REVMAGTRK IS 
            'Reverse magnetic course/bearing.';
            
            COMMENT ON COLUMN ats_routes.NMAGTRK IS 
            'Forward magnetic course based on navaid-to-navaid calculation.';
            
            COMMENT ON COLUMN ats_routes.NREVMAGTRK IS 
            'Reverse magnetic course based on navaid-to-navaid calculation.';
            
            COMMENT ON COLUMN ats_routes.LENGTH_VAL IS 
            'Length of route segment.';
            
            COMMENT ON COLUMN ats_routes.COPDIST IS 
            'Distance from navaid to changeover point.';
            
            COMMENT ON COLUMN ats_routes.COPNAV_ID IS 
            'Referenced Navaid GLOBAL_ID used for COPDIST value calculation.';
            
            COMMENT ON COLUMN ats_routes.REPATCSTAR IS 
            'Compulsory reporting status at route start. C (Compulsory all Altitudes) C-LOW (Compulsory Low Altitude Only) C-HIGH (Compulsory High Altitude Only) R (On Request/Non-Compulsory)';
            
            COMMENT ON COLUMN ats_routes.REPATCEND IS 
            'Compulsory reporting status at route end. C (Compulsory all Altitudes) C-LOW (Compulsory Low Altitude Only) C-HIGH (Compulsory High Altitude Only) R (On Request/Non-Compulsory)';
            
            COMMENT ON COLUMN ats_routes.DIRECTION IS 
            'Permitted route direction. E (Eastbound Only) W (Westbound Only) BE (Both directions) BW (Both Directions)';
            
            COMMENT ON COLUMN ats_routes.FREQ_CLASS IS 
            'Navaid frequency class used by conventional routes - CONV, A (UHF/VHF) B (LF/MF).';
            
            COMMENT ON COLUMN ats_routes.STATUS IS 
            'Usability flag. 0=Not usable, 1=Usable, Null=Usable.';
            
            COMMENT ON COLUMN ats_routes.STARTPT_ID IS 
            'Starting designated point GLOBAL_ID.';
            
            COMMENT ON COLUMN ats_routes.ENDPT_ID IS 
            'Ending designated point GLOBAL_ID.';
            
            COMMENT ON COLUMN ats_routes.RTPORT_ID IS 
            'Related Route Portion GLOBAL_ID.';
            
            COMMENT ON COLUMN ats_routes.ENRINFO_ID IS 
            'Related Enroute Information GLOBAL_ID.';
            
            COMMENT ON COLUMN ats_routes.WIDTHRIGHT IS 
            'Route width to the right of centerline.';
            
            COMMENT ON COLUMN ats_routes.WIDTHLEFT IS 
            'Route width to the left of centerline.';
            
            COMMENT ON COLUMN ats_routes.WIDTH_UOM IS 
            'Unit for route width, normally nautical miles (NM).';
            
            COMMENT ON COLUMN ats_routes.MCA1_VAL IS 
            'First Minimum Crossing Altitude.';
            
            COMMENT ON COLUMN ats_routes.MCA1_UOM IS 
            'Unit for MCA1_VAL. FT (feet)';
            
            COMMENT ON COLUMN ats_routes.MCA1_DIR IS 
            'Direction associated with MCA1.';
            
            COMMENT ON COLUMN ats_routes.MCA2_VAL IS 
            'Second Minimum Crossing Altitude.';
            
            COMMENT ON COLUMN ats_routes.MCA2_UOM IS 
            'Unit for MCA2_VAL.';
            
            COMMENT ON COLUMN ats_routes.MCA2_DIR IS 
            'Direction associated with MCA2.';
            
            COMMENT ON COLUMN ats_routes.MCAPT_ID IS 
            'Global ID of the Point or navaid at which MCA is located.';
            
            COMMENT ON COLUMN ats_routes.MCAPT_TYPE IS 
            'Indicates what the MCA point is, 0=Navaid, 1=Designated Point.';
            
            COMMENT ON COLUMN ats_routes.TFLAG_CODE IS 
            'Indicates if there is a change in altitude at ...: 0=None,1=Start,2=End,3=Both.';
            
            COMMENT ON COLUMN ats_routes.REMARKS IS 
            'Published route remarks.';
            
            COMMENT ON COLUMN ats_routes.AK_LOW IS 
            'Appears on Alaska low-altitude chart.';
            
            COMMENT ON COLUMN ats_routes.AK_HIGH IS 
            'Appears on Alaska high-altitude chart.';
            
            COMMENT ON COLUMN ats_routes.US_LOW IS 
            'Appears on U.S. low-altitude chart.';
            
            COMMENT ON COLUMN ats_routes.US_HIGH IS 
            'Appears on U.S. high-altitude chart.';
            
            COMMENT ON COLUMN ats_routes.US_AREA IS 
            'Appears on U.S. area chart.';
            
            COMMENT ON COLUMN ats_routes.PACIFIC IS 
            'Appears on Pacific enroute chart.';
            
            COMMENT ON COLUMN ats_routes.SHAPE_LENGTH IS 
            'Internal source geometry length attribute.';
        """)


        # points
        cur.execute("""
        CREATE TABLE IF NOT EXISTS ats_designated_points (
            OBJECTID        INTEGER PRIMARY KEY,
            GLOBAL_ID       TEXT UNIQUE NOT NULL,
            REMARKS         TEXT,
            IDENT           TEXT,

            LATITUDE        DOUBLE PRECISION,
            LONGITUDE       DOUBLE PRECISION,

            TYPE_CODE       TEXT,
            MIL_CODE        TEXT,

            REPATC          TEXT,

            MAGVAR          DOUBLE PRECISION,
            MAGVAR_DT       DATE,

            ONSHORE         SMALLINT,
            STRUCTURE       TEXT,
            REFFAC          TEXT,

            MRA_VAL         DOUBLE PRECISION,
            MRA_UOM         TEXT,

            STATE           TEXT,
            COUNTRY         TEXT,

            AK_LOW          SMALLINT,
            AK_HIGH         SMALLINT,
            US_LOW          SMALLINT,
            US_HIGH         SMALLINT,
            US_AREA         SMALLINT,
            PACIFIC         SMALLINT
        );
        """)

        cur.execute("""
            COMMENT ON TABLE ats_designated_points IS
            'FAA Designated Point dataset. Represents waypoints, reporting points, RNAV fixes, GPS fixes, and other navigation reference points.';

            COMMENT ON COLUMN ats_designated_points.OBJECTID IS
            'Internal database object identifier.';

            COMMENT ON COLUMN ats_designated_points.GLOBAL_ID IS
            'Globally unique identifier for the designated point.';

            COMMENT ON COLUMN ats_designated_points.REMARKS IS
            'Published remarks associated with the designated point.';

            COMMENT ON COLUMN ats_designated_points.IDENT IS
            'Published identifier of the designated point.';

            COMMENT ON COLUMN ats_designated_points.LATITUDE IS
            'Latitude as provided in source data.';

            COMMENT ON COLUMN ats_designated_points.LONGITUDE IS
            'Longitude as provided in source data.';

            COMMENT ON COLUMN ats_designated_points.TYPE_CODE IS
            'Designated point type. CNF - Computer NavFix, GND - Ground Based Waypoint, GPS - GPS Waypoint, MB - Mileage Breakdown, MRPT - Military Reporting Point, NRS - Navigation Reference System Waypoint, RNAV - RNAV Waypoint, RPT - Reporting Point, WPT - Waypoint.';

            COMMENT ON COLUMN ats_designated_points.MIL_CODE IS
            'Civil or military designation of the point. CIVIL - Non Military, MIL - Military Only, OTHER - Other (Only used with MB Type_Code)';

            COMMENT ON COLUMN ats_designated_points.REPATC IS
            'Compulsory reporting status for the point. C - Compulsory all Altitudes, C-LOW - Compulsory Low Altitude Only, C-HIGH - Compulsory High Altitude Only, R - On Request/Non-Compulsory, N - No Report';

            COMMENT ON COLUMN ats_designated_points.MAGVAR IS
            'Magnetic variation value associated with the point.';

            COMMENT ON COLUMN ats_designated_points.MAGVAR_DT IS
            'Effective date of magnetic variation value.';

            COMMENT ON COLUMN ats_designated_points.ONSHORE IS
            '1 if the point is within the U.S. 12 NM maritime limit.';

            COMMENT ON COLUMN ats_designated_points.STRUCTURE IS
            'Chart structures or products in which the point is used.';

            COMMENT ON COLUMN ats_designated_points.REFFAC IS
            'Referenced navaid GLOBAL_ID used to define a ground-based waypoint.';

            COMMENT ON COLUMN ats_designated_points.MRA_VAL IS
            'Minimum Reception Altitude value.';

            COMMENT ON COLUMN ats_designated_points.MRA_UOM IS
            'Unit of measure for MRA_VAL. Currently FT (feet).';

            COMMENT ON COLUMN ats_designated_points.STATE IS
            'State or province containing the point.';

            COMMENT ON COLUMN ats_designated_points.COUNTRY IS
            'Country containing the point.';

            COMMENT ON COLUMN ats_designated_points.AK_LOW IS
            'Appears on Alaska low-altitude enroute chart.';

            COMMENT ON COLUMN ats_designated_points.AK_HIGH IS
            'Appears on Alaska high-altitude enroute chart.';

            COMMENT ON COLUMN ats_designated_points.US_LOW IS
            'Appears on U.S. low-altitude enroute chart.';

            COMMENT ON COLUMN ats_designated_points.US_HIGH IS
            'Appears on U.S. high-altitude enroute chart.';

            COMMENT ON COLUMN ats_designated_points.US_AREA IS
            'Appears on U.S. area chart.';

            COMMENT ON COLUMN ats_designated_points.PACIFIC IS
            'Appears on Pacific enroute chart.';
        """)

    conn.commit()
    print("Schema created.")


# ----------------------------
# GENERIC COPY
# ----------------------------
def copy_csv(conn, table, columns, path, preprocess=None):
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


# ----------------------------
# PREPROCESSORS
# ----------------------------

import csv
import io


def dms_to_decimal(coord: str) -> str:
    """
    Convert FAA coordinate:

        31-53-41.240N
        086-15-32.060W

    to decimal degrees.
    """

    if not coord:
        return ""

    coord = coord.strip()

    hemi = coord[-1]
    dms = coord[:-1]

    deg, minutes, seconds = dms.split("-")

    decimal = (
        float(deg)
        + float(minutes) / 60.0
        + float(seconds) / 3600.0
    )

    if hemi in ("S", "W"):
        decimal *= -1

    return f"{decimal:.8f}"


def points_preprocess(line):
    row = next(csv.reader([line]))

    # remove X,Y
    row = row[2:]

    # convert coordinates
    row[4] = dms_to_decimal(row[4])
    row[5] = dms_to_decimal(row[5])

    # remove NOTES_ID
    del row[6]

    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow(row)

    return out.getvalue() + "\n"


# ----------------------------
# LOAD PIPELINE (ORDER MATTERS FOR FOREIGN KEYS)
# ----------------------------
def load_all(conn):

    # 1. Countries
    copy_csv(conn, "ats_routes",
        ["OBJECTID","GLOBAL_ID","IDENT","TYPE_CODE","LEVEL","WKHR_CODE","WKHR_RMK","MAA_VAL","MAA_UOM","MEA_E_VAL","MEA_E_UOM","MEA_W_VAL","MEA_W_UOM","GMEA_E_VAL","GMEA_E_UOM","GMEA_W_VAL","GMEA_W_UOM","DMEA_VAL","DMEA_UOM","MOCA_VAL","MOCA_UOM","MEAGAP","TRUETRK","MAGTRK","REVTRUETRK","REVMAGTRK","NMAGTRK","NREVMAGTRK","LENGTH_VAL","COPDIST","COPNAV_ID","REPATCSTAR","REPATCEND","DIRECTION","FREQ_CLASS","STATUS","STARTPT_ID","ENDPT_ID","RTPORT_ID","ENRINFO_ID","WIDTHRIGHT","WIDTHLEFT","WIDTH_UOM","MCA1_VAL","MCA1_UOM","MCA1_DIR","MCA2_VAL","MCA2_UOM","MCA2_DIR","MCAPT_ID","MCAPT_TYPE","TFLAG_CODE","REMARKS","AK_LOW","AK_HIGH","US_LOW","US_HIGH","US_AREA","PACIFIC","SHAPE_Length"],
        FILES["Routes"],
    )

    # 2. Regions (depends on countries)
    copy_csv(conn, "ats_designated_points",
        ["OBJECTID","GLOBAL_ID","REMARKS","IDENT","LATITUDE","LONGITUDE","TYPE_CODE","MIL_CODE","REPATC","MAGVAR","MAGVAR_DT","ONSHORE","STRUCTURE","REFFAC","MRA_VAL","MRA_UOM","STATE","COUNTRY","AK_LOW","AK_HIGH","US_LOW","US_HIGH","US_AREA","PACIFIC"],
        FILES["Points"],
        preprocess=points_preprocess
    )



# ----------------------------
# MAIN
# ----------------------------
def main():
    with get_conn() as conn:
        create_schema(conn)
        load_all(conn)


def test_preprocess():
    result = points_preprocess(",,2,C6998622-EED7-4B4E-9FE3-A9100A464117, || COMPULSORY,SHARK,22-30-54.640N,156-05-23.020W,,CIVIL,RPT,C,9.5,2026/01/01 00:00:00+00,1,ENROUTE HIGH|ENROUTE LOW|STAR,,16000,FT,HAWAII,UNITED STATES,0,0,0,0,0,1")
    print(f"result: {result}")

if __name__ == "__main__":
    main()