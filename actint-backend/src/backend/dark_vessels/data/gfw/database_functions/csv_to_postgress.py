from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import psycopg
from psycopg import sql

from backend.config import config


def connect_to_region_csv_db():
    db_config = {
        "host": config.DB_HOST,
        "dbname": config.CSV_DATABASE_NAME,
        "user": config.DB_USER,
        "password": config.DB_PASS,
        "port": config.DB_PORT,
    }

    for key, value in db_config.items():
        if value is None:
            raise ValueError(f"Missing environment variable: {key}")

    return psycopg.connect(**db_config)


def validate_csv_name(csv_name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", csv_name):
        raise ValueError("csv_name may only contain letters, digits, and underscores")
    return csv_name


def infer_pg_type(value: str) -> str:
    """Guess a Postgres type from a sample string value."""
    if value is None or value.strip() == "":
        return "TEXT"
    v = value.strip()
    # Integer
    try:
        int(v)
        return "BIGINT"
    except ValueError:
        pass
    # Float
    try:
        float(v)
        return "DOUBLE PRECISION"
    except ValueError:
        pass
    # Date (basic YYYY-MM-DD check)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return "DATE"
    return "TEXT"


def infer_column_types(csv_path: Path, sample_rows: int = 100) -> dict[str, str]:
    """
    Read up to sample_rows rows and infer the best Postgres type per column.
    Defaults to TEXT if a column has mixed or unrecognised values.
    """
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV file is missing a header row")
        
        columns = list(reader.fieldnames)
        # Collect samples per column
        samples: dict[str, list[str]] = {col: [] for col in columns}
        for i, row in enumerate(reader):
            if i >= sample_rows:
                break
            for col in columns:
                val = row.get(col, "")
                if val and val.strip():
                    samples[col].append(val)

    # Infer type per column — if any sample disagrees, fall back to TEXT
    col_types: dict[str, str] = {}
    for col in columns:
        if not samples[col]:
            col_types[col] = "TEXT"
            continue
        inferred = {infer_pg_type(v) for v in samples[col]}
        # Priority: if all agree use that type, otherwise fall back
        if len(inferred) == 1:
            col_types[col] = inferred.pop()
        elif inferred <= {"BIGINT", "DOUBLE PRECISION"}:
            col_types[col] = "DOUBLE PRECISION"  # mixed int/float → float
        else:
            col_types[col] = "TEXT"

    return col_types


def create_csv_table(cursor, table_name: str, col_types: dict[str, str]) -> None:
    col_defs = [
        sql.SQL("{col} {type}").format(
            col=sql.Identifier(col),
            type=sql.SQL(pg_type),
        )
        for col, pg_type in col_types.items()
    ]

    cursor.execute(
        sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table} (id SERIAL PRIMARY KEY, {cols});"
        ).format(
            table=sql.Identifier(table_name),
            cols=sql.SQL(", ").join(col_defs),
        )
    )


def add_csv_to_database(csv_filepath: str, csv_name: str) -> None:
    csv_path = Path(csv_filepath)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_filepath}")

    table_name = validate_csv_name(f"{csv_name}_csv_database")

    # Infer schema from CSV
    col_types = infer_column_types(csv_path)
    columns   = list(col_types.keys())
    print(f"Detected {len(columns)} columns: {columns}")

    with connect_to_region_csv_db() as conn:
        with conn.cursor() as cursor:
            create_csv_table(cursor, table_name, col_types)

            with csv_path.open(newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)

                rows = []
                for row in reader:
                    rows.append(tuple(row.get(col) or None for col in columns))

                if rows:
                    col_identifiers = sql.SQL(", ").join(
                        sql.Identifier(c) for c in columns
                    )
                    placeholders = sql.SQL(", ").join(
                        sql.Placeholder() * len(columns)
                    )
                    insert_sql = sql.SQL(
                        "INSERT INTO {table} ({cols}) VALUES ({vals})"
                    ).format(
                        table=sql.Identifier(table_name),
                        cols=col_identifiers,
                        vals=placeholders,
                    )
                    cursor.executemany(insert_sql, rows)
                    print(f"Inserted {len(rows)} rows into '{table_name}'")

        conn.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load any CSV file into the CSV Postgres database.")
    parser.add_argument("--csv_filepath", required=True, help="Path to the CSV file to import")
    parser.add_argument("--csv_name", required=True, help="Base name for the target database table")
    args = parser.parse_args()

    add_csv_to_database(args.csv_filepath, args.csv_name)