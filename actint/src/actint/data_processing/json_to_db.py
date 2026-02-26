"""
AIS JSON to SQLite + ChromaDB processing pipeline.

Loads AIS data from JSON, normalizes it, stores structured data in SQLite,
and creates embeddings in ChromaDB for RAG-based queries.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Any

import chromadb
from chromadb.utils import embedding_functions
import pandas as pd

# Paths
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DB_DIR = DATA_DIR / "db"
JSON_PATH = DATA_DIR / "ais_merged.json"
SQLITE_PATH = DB_DIR / "ais.db"
CHROMA_PATH = DB_DIR / "chroma"

# Fleet name normalization mapping
FLEET_NORMALIZATION = {
    "3rd Fleet": "US_3RD_FLEET",
    "U.S. 3rd Fleet": "US_3RD_FLEET",
    "4th Fleet": "US_4TH_FLEET",
    "U.S. 4th Fleet": "US_4TH_FLEET",
    "U.S. PAC Fleet": "US_PAC_FLEET",
    "USFFC": "US_FLEET_FORCES_COMMAND",
    "U.S. Fleet Forces Command": "US_FLEET_FORCES_COMMAND",
}


def normalize_fleet(fleet_name: str | None) -> str | None:
    """Normalize fleet name to canonical form."""
    if fleet_name is None:
        return None
    return FLEET_NORMALIZATION.get(fleet_name, fleet_name)


def consolidate_xy_fields(record: dict[str, Any]) -> dict[str, Any]:
    """
    Consolidate duplicate _x and _y fields from merged data.
    Prefers _x values, falls back to _y if _x is None.
    """
    consolidated = {}
    processed_bases = set()
    
    for key, value in record.items():
        if key.endswith("_x"):
            base_key = key[:-2]
            y_key = f"{base_key}_y"
            y_value = record.get(y_key)
            # Prefer _x, fallback to _y
            consolidated[base_key] = value if value is not None else y_value
            processed_bases.add(base_key)
        elif key.endswith("_y"):
            base_key = key[:-2]
            if base_key not in processed_bases:
                consolidated[base_key] = value
                processed_bases.add(base_key)
        else:
            consolidated[key] = value
    
    return consolidated


def load_json_data(json_path: Path) -> list[dict]:
    """Load and normalize AIS data from JSON file."""
    print(f"Loading JSON from {json_path}...")
    with open(json_path, "r") as f:
        data = json.load(f)
    
    print(f"Loaded {len(data)} records")
    
    # Process each record
    normalized_data = []
    for record in data:
        # Consolidate _x/_y fields
        consolidated = consolidate_xy_fields(record)
        
        # Normalize fleet name
        if "Fleet" in consolidated:
            consolidated["Fleet_Original"] = consolidated["Fleet"]
            consolidated["Fleet"] = normalize_fleet(consolidated["Fleet"])
        
        normalized_data.append(consolidated)
    
    return normalized_data


def create_sqlite_schema(conn: sqlite3.Connection) -> None:
    """Create SQLite tables for AIS data."""
    cursor = conn.cursor()
    
    # Main AIS positions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ais_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mmsi INTEGER NOT NULL,
            base_datetime TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            sog REAL,
            cog REAL,
            heading REAL,
            vessel_name TEXT,
            imo TEXT,
            call_sign TEXT,
            vessel_type REAL,
            status REAL,
            length REAL,
            width REAL,
            draft REAL,
            cargo REAL,
            transceiver_class TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Vessel metadata table (static info, normalized)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vessels (
            mmsi INTEGER PRIMARY KEY,
            vessel_name TEXT,
            call_sign TEXT,
            domain TEXT,
            class TEXT,
            type TEXT,
            pennant_number INTEGER,
            callsign_military TEXT,
            world_port_index_number INTEGER,
            home_base TEXT,
            parent_command TEXT,
            fleet TEXT,
            fleet_original TEXT,
            first_seen TEXT,
            last_seen TEXT
        )
    """)
    
    # Fleet reference table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fleets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT UNIQUE NOT NULL,
            display_name TEXT
        )
    """)
    
    # Create indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_mmsi ON ais_positions(mmsi)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_datetime ON ais_positions(base_datetime)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_coords ON ais_positions(lat, lon)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vessels_fleet ON vessels(fleet)")
    
    conn.commit()
    print("SQLite schema created")


def insert_to_sqlite(conn: sqlite3.Connection, data: list[dict]) -> None:
    """Insert normalized data into SQLite."""
    cursor = conn.cursor()
    
    # Track vessels for metadata table
    vessels_seen = {}
    fleets_seen = set()
    
    print("Inserting AIS positions...")
    for i, record in enumerate(data):
        # Insert position
        cursor.execute("""
            INSERT INTO ais_positions (
                mmsi, base_datetime, lat, lon, sog, cog, heading,
                vessel_name, imo, call_sign, vessel_type, status,
                length, width, draft, cargo, transceiver_class
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.get("MMSI"),
            record.get("BaseDateTime"),
            record.get("LAT"),
            record.get("LON"),
            record.get("SOG"),
            record.get("COG"),
            record.get("Heading"),
            record.get("VesselName"),
            record.get("IMO"),
            record.get("CallSign"),
            record.get("VesselType"),
            record.get("Status"),
            record.get("Length"),
            record.get("Width"),
            record.get("Draft"),
            record.get("Cargo"),
            record.get("TransceiverClass"),
        ))
        
        # Track vessel metadata
        mmsi = record.get("MMSI")
        if mmsi:
            dt = record.get("BaseDateTime", "")
            if mmsi not in vessels_seen:
                vessels_seen[mmsi] = {
                    "mmsi": mmsi,
                    "vessel_name": record.get("VesselName") or record.get("Name"),
                    "call_sign": record.get("CallSign"),
                    "domain": record.get("Domain"),
                    "class": record.get("Class"),
                    "type": record.get("Type"),
                    "pennant_number": record.get("Pennant Number"),
                    "callsign_military": record.get("Callsign"),
                    "world_port_index_number": record.get("World Port Index Number"),
                    "home_base": record.get("Home Base"),
                    "parent_command": record.get("Parent Command"),
                    "fleet": record.get("Fleet"),
                    "fleet_original": record.get("Fleet_Original"),
                    "first_seen": dt,
                    "last_seen": dt,
                }
            else:
                # Update last_seen
                if dt > vessels_seen[mmsi]["last_seen"]:
                    vessels_seen[mmsi]["last_seen"] = dt
        
        # Track fleets
        if record.get("Fleet"):
            fleets_seen.add((record["Fleet"], record.get("Fleet_Original", record["Fleet"])))
        
        if (i + 1) % 50000 == 0:
            print(f"  Processed {i + 1}/{len(data)} records...")
            conn.commit()
    
    conn.commit()
    print(f"Inserted {len(data)} position records")
    
    # Insert vessel metadata
    print("Inserting vessel metadata...")
    for vessel in vessels_seen.values():
        cursor.execute("""
            INSERT OR REPLACE INTO vessels (
                mmsi, vessel_name, call_sign, domain, class, type,
                pennant_number, callsign_military, world_port_index_number,
                home_base, parent_command, fleet, fleet_original,
                first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vessel["mmsi"],
            vessel["vessel_name"],
            vessel["call_sign"],
            vessel["domain"],
            vessel["class"],
            vessel["type"],
            vessel["pennant_number"],
            vessel["callsign_military"],
            vessel["world_port_index_number"],
            vessel["home_base"],
            vessel["parent_command"],
            vessel["fleet"],
            vessel["fleet_original"],
            vessel["first_seen"],
            vessel["last_seen"],
        ))
    
    conn.commit()
    print(f"Inserted {len(vessels_seen)} vessel records")
    
    # Insert fleets
    print("Inserting fleet reference data...")
    for canonical, display in fleets_seen:
        cursor.execute("""
            INSERT OR IGNORE INTO fleets (canonical_name, display_name)
            VALUES (?, ?)
        """, (canonical, display))
    
    conn.commit()
    print(f"Inserted {len(fleets_seen)} fleet records")


def create_vessel_summaries(conn: sqlite3.Connection) -> list[dict]:
    """
    Create text summaries for each vessel for embedding.
    These will be used for semantic search in ChromaDB.
    """
    cursor = conn.cursor()
    
    # Get vessel info with position stats
    cursor.execute("""
        SELECT 
            v.mmsi,
            v.vessel_name,
            v.class,
            v.type,
            v.pennant_number,
            v.home_base,
            v.parent_command,
            v.fleet,
            v.first_seen,
            v.last_seen,
            COUNT(p.id) as position_count,
            AVG(p.lat) as avg_lat,
            AVG(p.lon) as avg_lon,
            AVG(p.sog) as avg_speed,
            MIN(p.lat) as min_lat,
            MAX(p.lat) as max_lat,
            MIN(p.lon) as min_lon,
            MAX(p.lon) as max_lon
        FROM vessels v
        LEFT JOIN ais_positions p ON v.mmsi = p.mmsi
        GROUP BY v.mmsi
    """)
    
    summaries = []
    for row in cursor.fetchall():
        mmsi, name, vessel_class, vessel_type, pennant, home_base, parent_cmd, fleet, first_seen, last_seen, pos_count, avg_lat, avg_lon, avg_speed, min_lat, max_lat, min_lon, max_lon = row
        
        # Create human-readable summary
        summary_parts = [f"Vessel: {name or 'Unknown'} (MMSI: {mmsi})"]
        
        if vessel_type and pennant:
            summary_parts.append(f"Designation: {vessel_type}-{pennant}")
        
        if vessel_class:
            summary_parts.append(f"Class: {vessel_class}")
        
        if fleet:
            summary_parts.append(f"Fleet: {fleet}")
        
        if home_base:
            summary_parts.append(f"Home port: {home_base}")
        
        if parent_cmd:
            summary_parts.append(f"Command: {parent_cmd}")
        
        if pos_count and pos_count > 0:
            summary_parts.append(f"Tracked positions: {pos_count}")
            if avg_speed is not None:
                summary_parts.append(f"Average speed: {avg_speed:.1f} knots")
            if avg_lat and avg_lon:
                summary_parts.append(f"Operating area center: ({avg_lat:.2f}, {avg_lon:.2f})")
        
        if first_seen and last_seen:
            summary_parts.append(f"Active period: {first_seen[:10]} to {last_seen[:10]}")
        
        summary_text = ". ".join(summary_parts) + "."
        
        summaries.append({
            "id": str(mmsi),
            "text": summary_text,
            "metadata": {
                "mmsi": mmsi,
                "vessel_name": name,
                "vessel_type": vessel_type,
                "fleet": fleet,
                "home_base": home_base,
            }
        })
    
    return summaries


def setup_chromadb(summaries: list[dict], chroma_path: Path) -> None:
    """Create ChromaDB collection with vessel summaries."""
    print(f"Setting up ChromaDB at {chroma_path}...")
    
    # Use persistent client
    client = chromadb.PersistentClient(path=str(chroma_path))
    
    # Use default embedding function (all-MiniLM-L6-v2)
    # For production, consider using a more powerful model
    embedding_fn = embedding_functions.DefaultEmbeddingFunction()
    
    # Delete existing collection if it exists
    try:
        client.delete_collection("vessels")
    except Exception:
        pass
    
    # Create collection
    collection = client.create_collection(
        name="vessels",
        embedding_function=embedding_fn,
        metadata={"description": "AIS vessel summaries for semantic search"}
    )
    
    # Add documents in batches
    batch_size = 100
    for i in range(0, len(summaries), batch_size):
        batch = summaries[i:i + batch_size]
        
        collection.add(
            ids=[s["id"] for s in batch],
            documents=[s["text"] for s in batch],
            metadatas=[s["metadata"] for s in batch],
        )
        
        if (i + batch_size) % 500 == 0:
            print(f"  Embedded {min(i + batch_size, len(summaries))}/{len(summaries)} vessels...")
    
    print(f"Created ChromaDB collection with {len(summaries)} vessel embeddings")
    
    # Test query
    print("\nTest query: 'destroyer operating in Pacific'")
    results = collection.query(
        query_texts=["destroyer operating in Pacific"],
        n_results=3
    )
    print("Top results:")
    for i, (doc, dist) in enumerate(zip(results["documents"][0], results["distances"][0])):
        print(f"  {i+1}. (distance: {dist:.3f}) {doc[:100]}...")


def main():
    """Main processing pipeline."""
    print("=" * 60)
    print("AIS Data Processing Pipeline")
    print("=" * 60)
    
    # Create output directories
    DB_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load and normalize data
    data = load_json_data(JSON_PATH)
    
    # Setup SQLite
    print("\n" + "-" * 40)
    print("Setting up SQLite database...")
    print("-" * 40)
    
    # Remove existing database for fresh start
    if SQLITE_PATH.exists():
        SQLITE_PATH.unlink()
        print(f"Removed existing database: {SQLITE_PATH}")
    
    conn = sqlite3.connect(SQLITE_PATH)
    create_sqlite_schema(conn)
    insert_to_sqlite(conn, data)
    
    # Create summaries for ChromaDB
    print("\n" + "-" * 40)
    print("Creating vessel summaries for embedding...")
    print("-" * 40)
    summaries = create_vessel_summaries(conn)
    print(f"Created {len(summaries)} vessel summaries")
    
    conn.close()
    
    # Setup ChromaDB
    print("\n" + "-" * 40)
    print("Setting up ChromaDB vector store...")
    print("-" * 40)
    setup_chromadb(summaries, CHROMA_PATH)
    
    print("\n" + "=" * 60)
    print("Processing complete!")
    print(f"SQLite database: {SQLITE_PATH}")
    print(f"ChromaDB store: {CHROMA_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
