import asyncio
import sys

async def test_subprocess():
    print(f"Platform: {sys.platform}")
    print(f"Python version: {sys.version}")
    loop = asyncio.get_event_loop()
    print(f"Current loop: {type(loop).__name__}")
    
    try:
        print("Attempting to run 'hostname' via create_subprocess_exec...")
        process = await asyncio.create_subprocess_exec(
            "hostname",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        print(f"Success! Output: {stdout.decode().strip()}")
    except NotImplementedError:
        print("FAILED: NotImplementedError")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        # Try both policies if needed, but let's test the current one first
        # asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        pass
    asyncio.run(test_subprocess())
