from fastapi.templating import Jinja2Templates
from app.config import get_settings
from app.database import engine
from sqlmodel import Session
from app.services import SettingsService

settings = get_settings()
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))

def get_global_app_name():
    with Session(engine) as session:
        try: return SettingsService(session).get_settings().app_name
        except: return "Sible"

def get_settings_global():
    with Session(engine) as session:
        return SettingsService(session).get_settings()

templates.env.globals["app_name"] = get_global_app_name
templates.env.globals["get_settings"] = get_settings_global
