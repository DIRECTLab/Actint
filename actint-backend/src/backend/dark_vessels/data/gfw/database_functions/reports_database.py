from backend.config import config
import psycopg

def connect_to_report_db():
    try:
        # Read environment variables
        db_config = {
            "host": config.DB_HOST,
            "dbname": config.FISHY_REPORTS_DB_NAME,
            "user": config.DB_USER,
            "password": config.DB_PASS,
            "port": config.DB_PORT,
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



# It might eventually be good if the report is in markdown or something that can have nice formatting so that it is nicer for the user to read.
def write_report(region: str, report: str):
    conn = connect_to_report_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {region}_reports (
            id SERIAL PRIMARY KEY,
            report TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    cursor.execute(f"INSERT INTO {region}_reports (report) VALUES (%s);", (report,))
    conn.commit()
    conn.close()



if __name__ == "__main__":
    write_report("Pacific_Ocean", "This is a sample report.")