"""
RAG (Retrieval-Augmented Generation) pipeline for AIS vessel queries.

Handles questions like "where is USS KIDD right now?" by:
1. Using ChromaDB for semantic vessel matching
2. Querying SQLite for actual position data
3. Returning formatted context for LLM response generation
"""

import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions


# Default paths
DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
DB_DIR = DATA_DIR / "db"
SQLITE_PATH = DB_DIR / "ais.db"
CHROMA_PATH = DB_DIR / "chroma"


@dataclass
class VesselPosition:
    """Represents a vessel's position at a point in time."""
    mmsi: int
    vessel_name: str
    timestamp: str
    lat: float
    lon: float
    sog: Optional[float] = None  # Speed Over Ground
    cog: Optional[float] = None  # Course Over Ground
    heading: Optional[float] = None
    
    def to_context_string(self) -> str:
        """Format position as a human-readable context string."""
        parts = [
            f"{self.vessel_name} (MMSI: {self.mmsi})",
            f"Position: {self.lat:.5f}°N, {self.lon:.5f}°W" if self.lon < 0 
                else f"Position: {self.lat:.5f}°N, {self.lon:.5f}°E",
            f"Last reported: {self.timestamp}",
        ]
        
        if self.sog is not None:
            parts.append(f"Speed: {self.sog:.1f} knots")
        
        if self.cog is not None:
            parts.append(f"Course: {self.cog:.1f}°")
        
        if self.heading is not None and self.heading != 511.0:  # 511 = not available
            parts.append(f"Heading: {self.heading:.1f}°")
        
        return ". ".join(parts)


@dataclass
class VesselInfo:
    """Extended vessel information from metadata."""
    mmsi: int
    vessel_name: str
    vessel_class: Optional[str] = None
    vessel_type: Optional[str] = None
    pennant_number: Optional[int] = None
    home_base: Optional[str] = None
    parent_command: Optional[str] = None
    fleet: Optional[str] = None
    
    def to_context_string(self) -> str:
        """Format vessel info as context string."""
        parts = [f"Vessel: {self.vessel_name}"]
        
        if self.vessel_type and self.pennant_number:
            parts.append(f"Designation: {self.vessel_type}-{self.pennant_number}")
        
        if self.vessel_class:
            parts.append(f"Class: {self.vessel_class}")
        
        if self.fleet:
            parts.append(f"Fleet: {self.fleet}")
        
        if self.home_base:
            parts.append(f"Home port: {self.home_base}")
        
        if self.parent_command:
            parts.append(f"Command: {self.parent_command}")
        
        return ". ".join(parts)


class RAGPipeline:
    """
    RAG pipeline for answering vessel location queries.
    
    Uses ChromaDB for semantic search to find vessels, then SQLite
    for retrieving actual position data.
    """
    
    def __init__(
        self,
        sqlite_path: Path = SQLITE_PATH,
        chroma_path: Path = CHROMA_PATH,
    ):
        self.sqlite_path = sqlite_path
        self.chroma_path = chroma_path
        
        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(path=str(chroma_path))
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        
        # Get the vessels collection
        self.collection = self.chroma_client.get_collection(
            name="vessels",
            embedding_function=self.embedding_fn,
        )
    
    def _get_sqlite_connection(self) -> sqlite3.Connection:
        """Get a SQLite connection."""
        return sqlite3.connect(self.sqlite_path)
    
    def extract_vessel_name(self, query: str) -> Optional[str]:
        """
        Extract vessel name from a natural language query.
        
        Handles patterns like:
        - "where is USS KIDD right now?"
        - "What is the position of USS MONTGOMERY?"
        - "Find USS MILWAUKEE"
        """
        # Common patterns for vessel location queries
        patterns = [
            r"where\s+is\s+(?:the\s+)?(.+?)(?:\s+right\s+now|\s+currently|\s+located|\s+at|\?|$)",
            r"position\s+of\s+(?:the\s+)?(.+?)(?:\?|$)",
            r"find\s+(?:the\s+)?(.+?)(?:\?|$)",
            r"locate\s+(?:the\s+)?(.+?)(?:\?|$)",
            r"track\s+(?:the\s+)?(.+?)(?:\?|$)",
            r"what\s+is\s+(.+?)'s\s+(?:position|location)",
        ]
        
        query_lower = query.lower().strip()
        
        for pattern in patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                vessel_name = match.group(1).strip()
                # Clean up common suffixes
                vessel_name = re.sub(r"\s*(right now|currently|now|today)\s*$", "", vessel_name)
                return vessel_name
        
        # Fallback: look for "USS" pattern directly
        uss_match = re.search(r"(uss\s+\w+)", query_lower)
        if uss_match:
            return uss_match.group(1)
        
        return None
    
    def search_vessels(self, query: str, n_results: int = 3) -> list[dict]:
        """
        Search for vessels matching the query using semantic search.
        
        Returns list of matching vessel metadata and documents.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        matches = []
        if results["ids"] and results["ids"][0]:
            for i, id_ in enumerate(results["ids"][0]):
                matches.append({
                    "mmsi": int(id_),
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                })
        
        return matches
    
    def get_latest_position(self, mmsi: int) -> Optional[VesselPosition]:
        """Get the most recent position for a vessel by MMSI."""
        conn = self._get_sqlite_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                mmsi, vessel_name, base_datetime, lat, lon, sog, cog, heading
            FROM ais_positions
            WHERE mmsi = ?
            ORDER BY base_datetime DESC
            LIMIT 1
        """, (mmsi,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return VesselPosition(
                mmsi=row[0],
                vessel_name=row[1] or "Unknown",
                timestamp=row[2],
                lat=row[3],
                lon=row[4],
                sog=row[5],
                cog=row[6],
                heading=row[7],
            )
        
        return None
    
    def get_vessel_info(self, mmsi: int) -> Optional[VesselInfo]:
        """Get vessel metadata by MMSI."""
        conn = self._get_sqlite_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                mmsi, vessel_name, class, type, pennant_number,
                home_base, parent_command, fleet
            FROM vessels
            WHERE mmsi = ?
        """, (mmsi,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return VesselInfo(
                mmsi=row[0],
                vessel_name=row[1] or "Unknown",
                vessel_class=row[2],
                vessel_type=row[3],
                pennant_number=row[4],
                home_base=row[5],
                parent_command=row[6],
                fleet=row[7],
            )
        
        return None
    
    def get_recent_positions(self, mmsi: int, limit: int = 5) -> list[VesselPosition]:
        """Get the most recent N positions for a vessel."""
        conn = self._get_sqlite_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                mmsi, vessel_name, base_datetime, lat, lon, sog, cog, heading
            FROM ais_positions
            WHERE mmsi = ?
            ORDER BY base_datetime DESC
            LIMIT ?
        """, (mmsi, limit))
        
        positions = []
        for row in cursor.fetchall():
            positions.append(VesselPosition(
                mmsi=row[0],
                vessel_name=row[1] or "Unknown",
                timestamp=row[2],
                lat=row[3],
                lon=row[4],
                sog=row[5],
                cog=row[6],
                heading=row[7],
            ))
        
        conn.close()
        return positions
    
    def retrieve_context(self, query: str, n_results: int = 3) -> str:
        """
        Main retrieval method: search for vessels and get their positions.
        
        Returns a formatted context string suitable for LLM augmentation.
        """
        # Try to extract a specific vessel name
        vessel_name = self.extract_vessel_name(query)
        search_query = vessel_name if vessel_name else query
        
        # Search for matching vessels
        matches = self.search_vessels(search_query, n_results=n_results)
        
        if not matches:
            return f"No vessels found matching query: '{search_query}'"
        
        context_parts = []
        
        for match in matches:
            mmsi = match["mmsi"]
            
            # Get vessel info
            vessel_info = self.get_vessel_info(mmsi)
            if vessel_info:
                context_parts.append(f"=== {vessel_info.vessel_name} ===")
                context_parts.append(vessel_info.to_context_string())
            
            # Get latest position
            position = self.get_latest_position(mmsi)
            if position:
                context_parts.append(f"Current Position: {position.to_context_string()}")
            else:
                context_parts.append("No position data available.")
            
            context_parts.append("")  # Empty line between vessels
        
        return "\n".join(context_parts)
    
    def answer_location_query(self, query: str) -> dict:
        """
        Answer a location query with structured data.
        
        Returns a dict with:
        - query: original query
        - vessel_name_extracted: extracted vessel name (if any)
        - matches: list of matching vessels with positions
        - context: formatted context string for LLM
        """
        vessel_name = self.extract_vessel_name(query)
        search_query = vessel_name if vessel_name else query
        
        matches = self.search_vessels(search_query, n_results=3)
        
        result = {
            "query": query,
            "vessel_name_extracted": vessel_name,
            "search_query": search_query,
            "matches": [],
            "context": "",
        }
        
        context_parts = []
        
        for match in matches:
            mmsi = match["mmsi"]
            
            vessel_data = {
                "mmsi": mmsi,
                "distance_score": match["distance"],
            }
            
            # Get vessel info
            vessel_info = self.get_vessel_info(mmsi)
            if vessel_info:
                vessel_data["info"] = {
                    "name": vessel_info.vessel_name,
                    "class": vessel_info.vessel_class,
                    "type": vessel_info.vessel_type,
                    "pennant": vessel_info.pennant_number,
                    "home_base": vessel_info.home_base,
                    "fleet": vessel_info.fleet,
                }
                context_parts.append(f"=== {vessel_info.vessel_name} ===")
                context_parts.append(vessel_info.to_context_string())
            
            # Get latest position
            position = self.get_latest_position(mmsi)
            if position:
                vessel_data["position"] = {
                    "lat": position.lat,
                    "lon": position.lon,
                    "timestamp": position.timestamp,
                    "sog": position.sog,
                    "cog": position.cog,
                    "heading": position.heading,
                }
                context_parts.append(f"Current Position: {position.to_context_string()}")
            
            context_parts.append("")
            result["matches"].append(vessel_data)
        
        result["context"] = "\n".join(context_parts)
        
        return result


def create_rag_pipeline(
    sqlite_path: Optional[Path] = None,
    chroma_path: Optional[Path] = None,
) -> RAGPipeline:
    """Factory function to create a RAG pipeline with optional custom paths."""
    return RAGPipeline(
        sqlite_path=sqlite_path or SQLITE_PATH,
        chroma_path=chroma_path or CHROMA_PATH,
    )


# CLI for testing
if __name__ == "__main__":
    import sys
    
    print("Initializing RAG Pipeline...")
    pipeline = create_rag_pipeline()
    
    # Default test queries
    test_queries = [
        "Where is USS KIDD right now?",
        "What is the position of USS MONTGOMERY?",
        "Find USS MILWAUKEE",
        "Where are the destroyers?",
    ]
    
    # Use command line args if provided
    if len(sys.argv) > 1:
        test_queries = [" ".join(sys.argv[1:])]
    
    for query in test_queries:
        print("\n" + "=" * 60)
        print(f"Query: {query}")
        print("=" * 60)
        
        result = pipeline.answer_location_query(query)
        
        print(f"Extracted vessel name: {result['vessel_name_extracted']}")
        print(f"Search query: {result['search_query']}")
        print(f"Matches found: {len(result['matches'])}")
        print("\n--- Context for LLM ---")
        print(result["context"])
