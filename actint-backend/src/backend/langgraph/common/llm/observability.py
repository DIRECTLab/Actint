# observability.py

import socket
import time

from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor


_tracing_enabled = False


def _check_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """Quick check if Phoenix server is reachable."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def setup_observability(debug: bool) -> None:
    global _tracing_enabled

    if not debug:
        return

    if _tracing_enabled:
        print("[observability] already enabled")
        return

    print("[observability] enabling Phoenix instrumentation...")

    # --- pre-check: is Phoenix server running? ---
    phoenix_host = "localhost"
    phoenix_port = 6006

    print(f"[observability] checking Phoenix at {phoenix_host}:{phoenix_port}...")

    if _check_port_open(phoenix_host, phoenix_port):
        print("[observability] Phoenix server detected ✔")
    else:
        print("[observability] WARNING: Phoenix server NOT reachable ❌")
        print("[observability] Make sure you ran: phoenix serve")

    # --- register OTEL exporter ---
    start = time.time()

    try:
        tracer_provider = register()
        print("[observability] OTEL tracer registered")

        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        print("[observability] LangChain/LangGraph instrumentation enabled")

        _tracing_enabled = True

    except Exception as e:
        print("[observability] FAILED to initialize tracing:")
        print(f"[observability] {type(e).__name__}: {e}")
        return

    print(f"[observability] setup complete in {time.time() - start:.2f}s")