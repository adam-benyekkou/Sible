from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from typing import Any, Optional
from app.dependencies import get_runner_service, requires_role
from app.services import RunnerService

router = APIRouter()

@router.get("/stream/{name:path}")
async def stream_playbook_endpoint(
    name: str, 
    mode: str = "run", 
    limit: Optional[str] = None,
    tags: Optional[str] = None,
    verbosity: int = 0,
    extra_vars: Optional[str] = None,
    service: RunnerService = Depends(get_runner_service),
    current_user: Any = Depends(requires_role(["admin", "operator"]))
) -> StreamingResponse:
    """Streams Ansible playbook execution logs in real-time.

    Why: Uses Server-Sent Events (SSE) to provide "live" feedback to the UI
    during long-running playbook executions. This avoids polling and
    provides a premium terminal-like experience for the user.

    Args:
        name: Relative path to the playbook file.
        mode: Execution flavor ('run', 'check', or 'galaxy').
        limit: Optional Ansible host limit string.
        tags: Optional Ansible tags to filter tasks.
        verbosity: Verbosity depth (0-4).
        extra_vars: JSON string of variables for the playbook.
        service: Injected RunnerService.
        current_user: Authenticated operator or admin.

    Returns:
        A StreamingResponse yielding 'data:' lines for SSE.
    """
    check_mode = (mode == "check")
    
    # Parse extra_vars if JSON
    ev_dict = None
    if extra_vars:
        try:
            import json
            ev_dict = json.loads(extra_vars)
        except Exception:
             pass

    async def event_generator():
        yield "data: Connected\n\n"
        if mode == "galaxy":
             async for line in service.install_requirements(name):
                yield f"data: {line}\n\n"
        else:
            async for line in service.run_playbook(
                name, 
                check_mode=check_mode,
                limit=limit,
                tags=tags,
                verbosity=verbosity,
                extra_vars=ev_dict,
                username=current_user.username
            ):
                yield f"data: {line}\n\n"
        yield "event: end\ndata: Execution finished\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
