from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from app.templates import templates
from typing import List, Optional
from pydantic import BaseModel
from app.services.template import TemplateService
from app.core.security import get_current_user

router = APIRouter(
    tags=["templates"],
    dependencies=[Depends(get_current_user)]
)

from app.schemas.template import TemplateCreate, TemplateUpdate

@router.get("/templates", response_class=HTMLResponse)
async def templates_index(request: Request):
    return templates.TemplateResponse("templates_index.html", {"request": request})

@router.get("/api/templates", response_model=List[dict])
def list_templates():
    return TemplateService.list_templates()

@router.get("/api/templates/{name_id:path}/content")
def get_template_content(name_id: str):
    content = TemplateService.get_template_content(name_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"content": content}

@router.post("/api/templates")
def create_template(template: TemplateCreate):
    if TemplateService.get_template_content(template.name) is not None:
         raise HTTPException(status_code=400, detail="Template already exists")
         
    success = TemplateService.save_template(template.name, template.content)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save template")
    return {"message": "Template created"}

@router.put("/api/templates/{name_id:path}")
def update_template(name_id: str, template: TemplateUpdate):
    # Verify existence
    if TemplateService.get_template_content(name_id) is None:
         raise HTTPException(status_code=404, detail="Template not found")
         
    success = TemplateService.save_template(name_id, template.content)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save template")
    return {"message": "Template updated"}

@router.delete("/api/templates/{name_id:path}")
def delete_template(name_id: str):
    if TemplateService.get_template_content(name_id) is None:
         raise HTTPException(status_code=404, detail="Template not found")
         
    success = TemplateService.delete_template(name_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete template")
    return {"message": "Template deleted"}
