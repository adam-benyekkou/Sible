from fastapi import APIRouter, Request, Response, Form, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templates import templates
from app.config import get_settings
from app.dependencies import get_settings_service, get_playbook_service
from app.services import SettingsService, PlaybookService
from app.auth import verify_password

settings_conf = get_settings()
router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "app_name": "Sible"})

@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request, 
    username: str = Form(...), 
    password: str = Form(...),
    service: SettingsService = Depends(get_settings_service)
):
    settings = service.get_settings()
    if settings.auth_enabled and username == settings.auth_username and verify_password(password, settings.auth_password):
        request.session["user"] = username
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("login.html", {"request": request, "app_name": "Sible", "error": "Invalid login"})

@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

@router.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/partials/sidebar")
async def get_sidebar(
    request: Request,
    service: PlaybookService = Depends(get_playbook_service)
):
    playbooks = service.list_playbooks()
    return templates.TemplateResponse("partials/sidebar.html", {"request": request, "playbooks": playbooks})
