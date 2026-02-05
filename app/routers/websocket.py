from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.dependencies import get_runner_service
from app.services import RunnerService

router = APIRouter()

@router.get("/stream/{name:path}")
async def stream_playbook_endpoint(
    name: str, 
    mode: str = "run", 
    limit: str = None,
    tags: str = None,
    verbosity: int = 0,
    extra_vars: str = None,
    service: RunnerService = Depends(get_runner_service)
):
    check_mode = (mode == "check")
    
    # Parse extra_vars if JSON
    ev_dict = None
    if extra_vars:
        try:
            import json
            ev_dict = json.loads(extra_vars)
        except:
             pass

    async def event_generator():
        yield "event: start\ndata: Connected\n\n"
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
                extra_vars=ev_dict
            ):
                yield f"data: {line}\n\n"
        yield "event: end\ndata: Execution finished\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
