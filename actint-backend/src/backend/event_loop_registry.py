"""
This module provides a simple registry for the main asyncio event loop used by the application. 
It allows different components, such as tools and agents, to access the same event loop without needing to pass it around explicitly. 
This is particularly useful for ensuring that all async operations are coordinated on the same loop, 
especially when using threads or when the loop is created in a different part of the application.
"""

# backend/loop_registry.py
import asyncio

_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Registers the main event loop for the application, allowing tools and other components to access it."""
    global _loop
    _loop = loop


def get_loop() -> asyncio.AbstractEventLoop:
    """Retrieves the registered event loop for async operations. Raises an error if not set."""
    if _loop is None:
        raise RuntimeError("Event loop not registered yet.")
    return _loop