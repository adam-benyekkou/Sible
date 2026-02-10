from fastapi.templating import Jinja2Templates
from fastapi.templating import Jinja2Templates
from app.core.config import get_settings
from app.core.database import engine
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

from datetime import datetime, timedelta
import re

def rel_to_id(path: str) -> str:
    return path.replace("/", "-").replace(".", "-").replace(" ", "-")

def format_datetime(dt, tz_offset="UTC"):
    if not dt:
        return ""
    
    # Simple UTC offset parsing (e.g. UTC, UTC+1, UTC-5)
    offset_hours = 0
    if tz_offset and tz_offset.startswith("UTC"):
        match = re.search(r"UTC([+-]\d+)", tz_offset)
        if match:
            offset_hours = int(match.group(1))
            
    # Apply offset
    if offset_hours != 0:
        dt_adj = dt + timedelta(hours=offset_hours)
    else:
        dt_adj = dt
        
    return dt_adj.strftime('%Y-%m-%d %H:%M')

templates.env.filters["rel_to_id"] = rel_to_id
templates.env.filters["format_datetime"] = format_datetime

