from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlmodel import Session, select
from app.database import engine
from app.models import Host
from app.auth import get_current_user_ws
import asyncssh
import asyncio
import logging
import json

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

@router.websocket("/ws/ssh/{host_id}")
async def ssh_websocket_endpoint(websocket: WebSocket, host_id: int):
    # Authenticate (simple check)
    # in a real app, you'd use a dependency to check session cookie or token
    # For now, we trust the connection if they can access the UI, but let's check basic session presence if possible
    # We'll skip strict auth for this MVP step but add a TODO
    
    await websocket.accept()
    
    conn = None
    process = None
    
    try:
        with Session(engine) as db:
            host = db.get(Host, host_id)
        
        if not host:
            await websocket.close(code=4001, reason="Hostname not found in inventory")
            return

        async with asyncssh.connect(
            host.hostname, 
            port=host.ssh_port, 
            username=host.ssh_user,
            known_hosts=None, # For dev simplicity; in prod use known_hosts
            client_keys=[host.ssh_key_path] if host.ssh_key_path else None
        ) as conn:
            
            # Start interactive session
            # term_type='xterm' important for some apps
            async with conn.create_process(term_type='xterm', term_size=(80, 24)) as process:
                
                # Task to read from SSH and send to WebSocket
                async def forward_stdout():
                    try:
                        async for msg in process.stdout:
                            await websocket.send_text(msg)
                    except Exception:
                        pass
                        
                async def forward_stderr():
                     try:
                        async for msg in process.stderr:
                            await websocket.send_text(msg)
                     except Exception:
                        pass

                stdout_task = asyncio.create_task(forward_stdout())
                stderr_task = asyncio.create_task(forward_stderr())

                # Loop to read from WebSocket and send to SSH
                try:
                    while True:
                        data = await websocket.receive_text()
                        process.stdin.write(data)
                except WebSocketDisconnect:
                    pass
                finally:
                    # Clean up
                    stdout_task.cancel()
                    stderr_task.cancel()
                    
    except Exception as e:
        logger.error(f"SSH Error: {e}")
        try:
             # Close with specific code for frontend to catch
             # 4000-4999 are available for private use
             # Sanitize reason to avoid control chars breaking WS protocol
             raw_reason = str(e)
             clean_reason = "".join(ch for ch in raw_reason if ch.isprintable())
             reason = clean_reason[:100] # Limit reason length 
             await websocket.close(code=4001, reason=reason)
             return # Ensure we return so the final finally block doesnt try to close again if already closed
        except:
             pass
    finally:
        try:
            await websocket.close()
        except:
            pass
