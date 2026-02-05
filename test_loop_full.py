import asyncio
import sys

async def test_subprocess():
    print(f"Platform: {sys.platform}")
    print(f"Python: {sys.version}")
    
    loop = asyncio.get_event_loop()
    print(f"Loop type: {type(loop).__name__}")
    
    try:
        print("Running 'echo hello'...")
        proc = await asyncio.create_subprocess_exec(
            "cmd.exe", "/c", "echo hello",
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        print(f"Output: {stdout.decode().strip()}")
    except NotImplementedError:
        print("RESULT: NotImplementedError")
    except Exception as e:
        print(f"RESULT: {type(e).__name__}: {e}")

if __name__ == "__main__":
    print("--- Testing default policy ---")
    try:
        asyncio.run(test_subprocess())
    except Exception as e:
        print(f"Default policy crash: {e}")

    print("\n--- Testing Proactor policy ---")
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(test_subprocess())
    except Exception as e:
        print(f"Proactor policy crash: {e}")

    print("\n--- Testing Selector policy ---")
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(test_subprocess())
    except Exception as e:
        print(f"Selector policy crash: {e}")
