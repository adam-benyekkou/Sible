from fastapi import APIRouter, Response, HTTPException
from app.services import GitService
from app.core.config import get_settings
from app.utils.htmx import trigger_toast
import logging

logger = logging.getLogger("uvicorn.info")
router = APIRouter()
settings = get_settings()

@router.post("/sync")
async def git_sync():
    """
    Triggers a git pull in the playbooks directory.
    """
    response = Response(status_code=200)
    try:
        success, message = GitService.pull_playbooks(settings.playbooks_dir)
        level = "success" if success else "error"
        logger.info(f"Git Sync: {message}")
        
        trigger_toast(response, message, level)
        
        # Trigger Sidebar refresh if successful
        if success:
            # We need to append to the existing trigger if trigger_toast set one
            # trigger_toast sets "show-toast" in HX-Trigger
            # using htmx.py logic, it handles merging if we set header BEFORE calling it? 
            # No, trigger_toast reads current header. 
            # Let's import json and do it manually or rely on trigger_toast to not overwrite if I set it first?
            # trigger_toast implementation:
            # current_trigger = response.headers.get("HX-Trigger")
            # ... merges ...
            
            # So if I set sidebar-refresh first, then call trigger_toast, it should work?
            # Let's check htmx.py again. It loads current_trigger.
            # If current_trigger is string "sidebar-refresh", json.loads fails (unless it's json string).
            # standard HX-Trigger can be comma separated? No, usually JSON for multiple events.
            
            # Safest is to let trigger_toast run, then append/merge manually or helper.
            # But trigger_toast replaces the header with JSON.
            
            import json
            current_trigger = response.headers.get("HX-Trigger")
            trigger_dict = json.loads(current_trigger) if current_trigger else {}
            trigger_dict["sidebar-refresh"] = True
            response.headers["HX-Trigger"] = json.dumps(trigger_dict)

        return response
        
    except Exception as e:
        logger.error(f"Git Sync Unexpected Error: {e}")
        trigger_toast(response, "Internal Server Error during Sync", "error")
        return response
