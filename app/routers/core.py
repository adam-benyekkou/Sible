from fastapi import APIRouter, Request, Response, Form, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates import templates
from app.core.config import get_settings
from app.dependencies import get_settings_service, get_playbook_service, requires_role
from app.services import SettingsService, PlaybookService
from app.models import User, Host, FavoriteServer


settings_conf = get_settings()
router = APIRouter()



@router.get("/health")
async def health_check():
    """Health check endpoint for Docker and monitoring.
    
    Returns:
        Status and version information.
    """
    return {"status": "ok", "version": settings_conf.VERSION}

@router.get("/")
async def root(
    request: Request,
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Renders the main landing page (Dashboard).

    Why: Shows a filtered list of favorite hosts for a personalized
    entry point into the infrastructure management UI.

    Args:
        request: Request object.
        current_user: Authenticated user.

    Returns:
        TemplateResponse for the index page.
    """
    from app.core.database import engine
    from sqlmodel import Session, select
    with Session(engine) as session:
        # Get user favorites
        fav_ids = set()
        if current_user:
            favs = session.exec(select(FavoriteServer).where(FavoriteServer.user_id == current_user.id)).all()
            fav_ids = {f.host_id for f in favs}
        
        # If user has favorites, show only those on dashboard
        if fav_ids:
            hosts = session.exec(select(Host).where(Host.id.in_(list(fav_ids)))).all()
        else:
            hosts = session.exec(select(Host)).all()
            
    return templates.TemplateResponse("index.html", {"request": request, "hosts": hosts, "fav_ids": fav_ids})

@router.get("/partials/sidebar")
async def get_sidebar(
    request: Request,
    service: PlaybookService = Depends(get_playbook_service),
    current_user: User = Depends(requires_role(["admin", "operator", "watcher"]))
) -> Response:
    """Renders the global sidebar partial with dynamic favorites and playbooks.

    Args:
        request: Request object.
        service: Playbook service for listing files.
        current_user: Authenticated user.

    Returns:
        HTML partial for the sidebar.
    """
    # Get user favorites for sidebar
    from app.core.database import engine
    from sqlmodel import Session, select
    from app.models import FavoriteServer, Host
    
    with Session(engine) as session:
        favs = session.exec(select(FavoriteServer).where(FavoriteServer.user_id == current_user.id)).all()
        fav_ids = {f.host_id for f in favs}
        favorites = []
        if fav_ids:
            favorites = session.exec(select(Host).where(Host.id.in_(list(fav_ids)))).all()
            
    playbooks = service.list_playbooks()
    return templates.TemplateResponse("partials/sidebar.html", {
        "request": request, 
        "playbooks": playbooks,
        "favorites": favorites,
        "fav_ids": fav_ids
    })
