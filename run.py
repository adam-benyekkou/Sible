import asyncio
import sys
import os
import uvicorn

def main():
    if sys.platform == 'win32':
        # Force ProactorEventLoop for subprocess support
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print("Sible Wrapper: Windows Proactor Event Loop Policy established.")

    # Ensure necessary directories exist
    os.makedirs("playbooks", exist_ok=True)
    os.makedirs("inventory", exist_ok=True)
    
    # Run uvicorn
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
