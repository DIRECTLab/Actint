import os
import psycopg
from backend.config import config

def test_postgres_connection():
    try:
        # Read environment variables
        db_config = {
            "host": config.DB_HOST,
            "dbname": config.DB_NAME,
            "user": config.DB_USER,
            "password": config.DB_PASS,
            "port": config.DB_PORT,
        }

        # Validate required vars
        for key, value in db_config.items():
            if value is None:
                raise ValueError(f"Missing environment variable: {key}")

        # Connect
        with psycopg.connect(**db_config) as conn:
            with conn.cursor() as cursor:

                # Create test table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_table (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # Insert test row
                cursor.execute(
                    "INSERT INTO test_table (name) VALUES (%s) RETURNING id;",
                    ("test_entry",)
                )

                new_id = cursor.fetchone()[0]

            conn.commit()

        print(f"Connected successfully. Inserted row ID: {new_id}")

    except Exception as e:
        print("Error:")
        print(e)


if __name__ == "__main__":
    test_postgres_connection()