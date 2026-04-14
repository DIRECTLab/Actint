"""CSV logger for LLM query telemetry."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class QueryLLMCSVLogger:
    """Append query/response statistics to a CSV file."""

    FIELDNAMES = [
        "timestamp_utc",
        "query",
        "context",
        "response",
        "use_llm",
        "matches_found",
        "rag_distance_score",
        "rag_confidence",
        "total_time_seconds",
        "llm_inference_time_seconds",
    ]

    def __init__(self, csv_path: Optional[Path] = None):
        self.csv_path = csv_path or (Path(__file__).resolve().parent / "query_llm_stats.csv")
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

    def log_query(
        self,
        *,
        query: str,
        context: str,
        response: str,
        use_llm: bool,
        matches_found: int,
        rag_distance_score: Optional[float],
        rag_confidence: Optional[float],
        total_time_seconds: float,
        llm_inference_time_seconds: Optional[float],
    ) -> None:
        """Append one row to the CSV log."""
        row = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "context": context,
            "response": response,
            "use_llm": use_llm,
            "matches_found": matches_found,
            "rag_distance_score": rag_distance_score,
            "rag_confidence": rag_confidence,
            "total_time_seconds": total_time_seconds,
            "llm_inference_time_seconds": llm_inference_time_seconds,
        }

        file_exists = self.csv_path.exists()
        write_header = not file_exists or self.csv_path.stat().st_size == 0

        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    @staticmethod
    def distance_to_confidence(distance_score: Any) -> Optional[float]:
        """
        Convert a Chroma distance score into a simple bounded confidence proxy.

        Chroma returns distance, where lower is better. This maps it to (0, 1]
        using 1 / (1 + distance).
        """
        try:
            distance = float(distance_score)
        except (TypeError, ValueError):
            return None

        if distance < 0:
            distance = 0.0

        return 1.0 / (1.0 + distance)
