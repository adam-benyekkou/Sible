from fastapi import APIRouter, Request, Response, Form, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates import templates
from app.core.config import get_settings
from app.dependencies import get_settings_service, get_playbook_service, requires_role
from app.services import SettingsService, PlaybookService


settings_conf = get_settings()
router = APIRouter()



@router.get("/")
async def root(
    request: Request,
    current_user: object = Depends(requires_role(["admin", "operator", "watcher"]))
):
    from app.models.host import Host
    from app.core.database import engine
    from sqlmodel import Session, select
    with Session(engine) as session:
        hosts = session.exec(select(Host)).all()
    return templates.TemplateResponse("index.html", {"request": request, "hosts": hosts})

@router.get("/partials/sidebar")
async def get_sidebar(
    request: Request,
    service: PlaybookService = Depends(get_playbook_service),
    current_user: object = Depends(requires_role(["admin", "operator", "watcher"]))
):
    playbooks = service.list_playbooks()
    return templates.TemplateResponse("partials/sidebar.html", {"request": request, "playbooks": playbooks})
