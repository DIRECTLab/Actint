import asyncio

class GPUQueue:
    def __init__(self):
        self._lock = asyncio.Lock()

    async def run(self, fn, *args, **kwargs):
        async with self._lock:
            return await fn(*args, **kwargs)


gpu_queue = GPUQueue()