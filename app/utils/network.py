import asyncio
import time
import logging

logger = logging.getLogger("uvicorn.error")

async def check_ssh(ip: str, port: int, timeout: float = 3.0) -> tuple[bool, float]:
    """
    Checks if an SSH port is open and responding.
    Returns (is_online, latency_ms).
    """
    start_time = time.perf_counter()
    try:
        # We use a short timeout as this is a heartbeat check
        conn = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(conn, timeout=timeout)
        
        latency = (time.perf_counter() - start_time) * 1000
        writer.close()
        await writer.wait_closed()
        return True, round(latency, 2)
    except Exception:
        latency = (time.perf_counter() - start_time) * 1000
        return False, round(latency, 2)
