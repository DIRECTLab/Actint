# backend/loop_registry.py
import asyncio

_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def get_loop() -> asyncio.AbstractEventLoop:
    if _loop is None:
        raise RuntimeError("Event loop not registered yet.")
    return _loop