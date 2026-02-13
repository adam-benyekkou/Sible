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
async def ssh_websocket_endpoint(websocket: WebSocket, host_id: int) -> None:
    """Provides a bi-directional WebSocket-to-SSH terminal bridge.

    Why: Uses asyncssh and binary WebSocket messages to provide a low-latency
    interactive terminal in the browser. Handles terminal resizing and
    supports both file-based and secret-stored (database) SSH keys.

    Args:
        websocket: The inbound WebSocket connection.
        host_id: The ID of the host to connect to.
    """
    logger.info(f"DEBUG: SSH WebSocket endpoint hit for host_id: {host_id}")
    # 1. Accept the WebSocket handshake immediately
    await websocket.accept()
    
    try:
        # 2. Authenticate
        logger.info(f"DEBUG: WebSocket cookies: {websocket.cookies}")
        username = await get_current_user_ws(websocket)
        if not username:
            logger.warning(f"DEBUG: WebSocket Auth failed for host_id: {host_id}")
            await websocket.send_text("\r\n\x1b[31mAuthentication failed. Please refresh and log in again.\x1b[0m\r\n")
            await websocket.close(code=4001)
            return

        with Session(engine) as db:
            from app.models import User, EnvVar
            statement = select(User).where(User.username == username)
            user = db.exec(statement).first()
            
            if not user or user.role not in ["admin", "operator"]:
                logger.warning(f"DEBUG: Forbidden access for user {username} (role: {user.role if user else 'N/A'})")
                await websocket.send_text("\r\n\x1b[31mForbidden: Admin or Operator access required for terminal.\x1b[0m\r\n")
                await websocket.close(code=4003)
                return

            host = db.get(Host, host_id)
            if not host:
                await websocket.send_text(f"\r\n\x1b[31mServer ID {host_id} not found in inventory.\x1b[0m\r\n")
                await websocket.close(code=4001)
                return

            # Resolved secrets (Key)
            ssh_key_data = None
            ssh_key_path = host.ssh_key_path

            # Fix hardcoded paths from old inventory.ini if they exist
            if ssh_key_path and "/ansible/" in ssh_key_path:
                from app.core.config import get_settings
                app_conf = get_settings()
                # Translate /ansible/keys/foo.pem -> /sible/playbooks/keys/foo.pem
                filename = ssh_key_path.split("/")[-1]
                ssh_key_path = str(app_conf.PLAYBOOKS_DIR / "keys" / filename)
                logger.info(f"DEBUG: Translated SSH Key path to {ssh_key_path}")

            if host.ssh_key_secret:
                env_var = db.exec(select(EnvVar).where(EnvVar.key == host.ssh_key_secret)).first()
                if env_var:
                    from app.core.security import decrypt_secret
                    raw_key = decrypt_secret(env_var.value) if env_var.is_secret else env_var.value
                    if raw_key:
                        # Normalize newlines and remove any accidental whitespace around the block
                        ssh_key_data = raw_key.replace("\\n", "\n").replace("\\r", "").replace("\r\n", "\n").strip()
                        ssh_key_data += "\n"
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
            # Start interactive session in binary mode
            async with conn.create_process(term_type='xterm', term_size=(80, 24), encoding=None) as process:
                
                # Bi-directional forwarding tasks
                async def forward_stdout():
                    try:
                        while True:
                            msg = await process.stdout.read(4096)
                            if not msg:
                                break
                            # logger.info(f"STDOUT (bin): {len(msg)} bytes") 
                            await websocket.send_bytes(msg)
                    except Exception as e:
                        logger.error(f"Error forwarding stdout: {e}")
                        
                async def forward_stderr():
                     try:
                        while True:
                            msg = await process.stderr.read(4096)
                            if not msg:
                                break
                            await websocket.send_bytes(msg)
                     except Exception:
                        pass

                stdout_task = asyncio.create_task(forward_stdout())
                stderr_task = asyncio.create_task(forward_stderr())

                try:
                    import json
                    while True:
                        try:
                            msg_data = await websocket.receive_text()
                            try:
                                payload = json.loads(msg_data)
                                msg_type = payload.get("type")
                                if msg_type == "input":
                                    input_data = payload.get("data", "")
                                    if isinstance(input_data, str):
                                        input_data = input_data.encode("utf-8")
                                    process.stdin.write(input_data)
                                    await process.stdin.drain()
                                elif msg_type == "resize":
                                    process.set_terminal_size(payload.get("cols"), payload.get("rows"))
                            except json.JSONDecodeError:
                                process.stdin.write(msg_data.encode("utf-8"))
                                await process.stdin.drain()
                        except WebSocketDisconnect:
                            break
                        except Exception as e:
                            logger.error(f"SSH WS Input Error: {e}")
                            break
                        
                finally:
                    stdout_task.cancel()
                    stderr_task.cancel()
                    try:
                        await stdout_task
                        await stderr_task
                    except asyncio.CancelledError:
                        pass
                    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"SSH WS Error: {error_msg}")
        try:
             clean_reason = "".join(ch for ch in error_msg if ch.isprintable())
             await websocket.send_text(f"\r\n\x1b[31mSSH Error: {clean_reason}\x1b[0m\r\n")
             await asyncio.sleep(0.5)
             await websocket.close(code=1011, reason=clean_reason[:120])
        except:
             pass
    finally:
        try:
            await websocket.close()
        except:
            pass
