from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session, select
from app.core.database import engine
from app.models import Host
from app.core.security import get_current_user_ws
import asyncssh
import asyncio
import logging

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

@router.websocket("/ws/ssh/{host_id}")
async def ssh_websocket_endpoint(websocket: WebSocket, host_id: int):
    logger.info(f"DEBUG: SSH WebSocket endpoint hit for host_id: {host_id}")
    # 1. Accept the WebSocket handshake immediately
    await websocket.accept()
    
    try:
        # 2. Authenticate
        username = await get_current_user_ws(websocket)
        if not username:
            await websocket.send_text("\r\n\x1b[31mAuthentication failed. Please refresh and log in again.\x1b[0m\r\n")
            await websocket.close(code=4001)
            return

        with Session(engine) as db:
            from app.models import User, EnvVar
            statement = select(User).where(User.username == username)
            user = db.exec(statement).first()
            
            if not user or user.role != "admin":
                await websocket.send_text("\r\n\x1b[31mForbidden: Admin access required for terminal.\x1b[0m\r\n")
                await websocket.close(code=4003)
                return

            host = db.get(Host, host_id)
            if not host:
                await websocket.send_text(f"\r\n\x1b[31mServer ID {host_id} not found in inventory.\x1b[0m\r\n")
                await websocket.close(code=4001)
                return

            # Resolve secrets (Password or Key)
            ssh_password = None
            ssh_key_data = None
            ssh_key_path = host.ssh_key_path

            if host.ssh_password_secret:
                env_var = db.exec(select(EnvVar).where(EnvVar.key == host.ssh_password_secret)).first()
                if env_var:
                    ssh_password = env_var.value
                    logger.info(f"DEBUG: Using SSH Password Secret '{host.ssh_password_secret}'")

            if host.ssh_key_secret:
                env_var = db.exec(select(EnvVar).where(EnvVar.key == host.ssh_key_secret)).first()
                if env_var:
                    ssh_key_data = env_var.value
                    logger.info(f"DEBUG: Using SSH Key Secret '{host.ssh_key_secret}' (length: {len(ssh_key_data)})")

        # 3. Inform user of progress
        await websocket.send_text(f"\x1b[36mConnecting to {host.alias} ({host.hostname})...\x1b[0m\r\n")

        # 4. Prepare SSH connection options
        connect_kwargs = {
            "host": host.hostname,
            "port": host.ssh_port,
            "username": host.ssh_user,
            "known_hosts": None, # Dev simplicity
            "connect_timeout": 15
        }
        
        if ssh_password:
            connect_kwargs["password"] = ssh_password
        
        if ssh_key_data:
            try:
                # Basic check for key format
                if "BEGIN" not in ssh_key_data and "ssh-" not in ssh_key_data:
                     logger.warning(f"DEBUG: SSH Key for host {host_id} seems to have invalid format")
                
                connect_kwargs["client_keys"] = [asyncssh.import_private_key(ssh_key_data)]
                logger.info(f"DEBUG: Private key imported successfully for host {host_id}")
            except Exception as e:
                logger.error(f"DEBUG: Error importing Private Key Secret for host {host_id}: {e}")
                await websocket.send_text(f"\x1b[31mError importing Private Key Secret: {str(e)}\x1b[0m\r\n")
                # Fallback to path if provided
                if ssh_key_path:
                    connect_kwargs["client_keys"] = [ssh_key_path]
        elif ssh_key_path:
            connect_kwargs["client_keys"] = [ssh_key_path]

        # 5. Establish SSH Connection
        async with asyncssh.connect(**connect_kwargs) as conn:
            logger.info(f"SSH Connected to {host.hostname} for host_id: {host_id}")
            # Start interactive session
            async with conn.create_process(term_type='xterm', term_size=(80, 24)) as process:
                
                # Bi-directional forwarding tasks
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

                try:
                    while True:
                        data = await websocket.receive_text()
                        process.stdin.write(data)
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected for host_id: {host_id}")
                finally:
                    stdout_task.cancel()
                    stderr_task.cancel()
                    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"SSH WS Error for host {host_id}: {error_msg}")
        try:
             clean_reason = "".join(ch for ch in error_msg if ch.isprintable())
             await websocket.send_text(f"\r\n\x1b[31mSSH Error: {clean_reason}\x1b[0m\r\n")
             # Small delay to allow message to arrive
             await asyncio.sleep(1)
             await websocket.close(code=4001, reason=clean_reason[:120])
        except Exception as close_err:
             logger.error(f"Error during socket closure for host {host_id}: {close_err}")
    finally:
        try:
            # Check if socket is already closed to avoid double-close errors
            await websocket.close()
        except:
            pass
