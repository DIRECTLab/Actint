"""ACTINT - Maritime Intelligence Package."""
from actint.tools.lat_lon_context import (
    get_location_context,
    get_location_context_string,
    get_distance_between,
    LocationContext,
)

# Optional, heavier imports.
# These pull in dependencies (e.g. vector DB clients) that are not required for
# using low-level tools or running the MCP/LLM servers.
try:
    from actint.query_llm import VesselQueryLLM, create_query_llm, get_vessel_context
except Exception:  # pragma: no cover
    VesselQueryLLM = None  # type: ignore[assignment]
    create_query_llm = None  # type: ignore[assignment]
    get_vessel_context = None  # type: ignore[assignment]

try:
    from actint.data_processing.rag import RAGPipeline, create_rag_pipeline
except Exception:  # pragma: no cover
    RAGPipeline = None  # type: ignore[assignment]
    create_rag_pipeline = None  # type: ignore[assignment]

__all__ = [
    "get_location_context",
    "get_location_context_string",
    "get_distance_between",
    "LocationContext",
]

if VesselQueryLLM is not None:
    __all__ += ["VesselQueryLLM", "create_query_llm", "get_vessel_context"]

if RAGPipeline is not None:
    __all__ += ["RAGPipeline", "create_rag_pipeline"]
