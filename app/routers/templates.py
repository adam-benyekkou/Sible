from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import HTMLResponse
from app.templates import templates
from typing import Any
from app.services.template import TemplateService
from app.models import User
from app.core.security import get_current_user
from app.dependencies import requires_role

router = APIRouter(
    tags=["templates"],
    dependencies=[Depends(get_current_user)]
)

from app.schemas.template import TemplateCreate, TemplateUpdate

@router.get("/templates", response_class=HTMLResponse)
async def templates_index(request: Request) -> Response:
    """Renders the Template Library management page.

    Args:
        request: Request object.

    Returns:
        TemplateResponse for the templates index.
    """
    return templates.TemplateResponse("templates_index.html", {"request": request})

@router.get("/api/templates")
def list_templates(page: int = 1) -> dict[str, Any]:
    """Lists templates with pagination support.

    Args:
        page: Current page number.

    Returns:
        JSON with template list and pagination metadata.
    """
    limit = 20
    offset = (page - 1) * limit
    templates_list, total_count = TemplateService.list_templates(limit=limit, offset=offset)
    
    import math
    total_pages = math.ceil(total_count / limit)
    
    return {
        "templates": templates_list,
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }

@router.get("/api/templates/{name_id:path}/content")
def get_template_content(name_id: str) -> dict[str, str]:
    """Retrieves the raw content of a specific template.

    Args:
        name_id: Template filename/path.

    Returns:
        JSON with template content.
    """
    content = TemplateService.get_template_content(name_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"content": content}

@router.post("/api/templates")
def create_template(
    template: TemplateCreate,
    current_user: User = Depends(requires_role(["admin"]))
) -> dict[str, str]:
    """Creates a new template record.

    Args:
        template: Pydantic model for creation.
        current_user: Admin access required.

    Returns:
        JSON confirmation message.
    """
    if TemplateService.get_template_content(template.name) is not None:
         raise HTTPException(status_code=400, detail="Template already exists")
         
    success = TemplateService.save_template(template.name, template.content)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save template")
    return {"message": "Template created"}

@router.put("/api/templates/{name_id:path}")
def update_template(
    name_id: str, 
    template: TemplateUpdate,
    current_user: User = Depends(requires_role(["admin"]))
) -> dict[str, str]:
    """Updates an existing template's content.

    Args:
        name_id: Target template name.
        template: Pydantic model for update.
        current_user: Admin access required.

    Returns:
        JSON confirmation message.
    """
    # Verify existence
    if TemplateService.get_template_content(name_id) is None:
         raise HTTPException(status_code=404, detail="Template not found")
         
    success = TemplateService.save_template(name_id, template.content)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save template")
    return {"message": "Template updated"}

@router.delete("/api/templates/{name_id:path}")
def delete_template(
    name_id: str,
    current_user: User = Depends(requires_role(["admin"]))
) -> dict[str, str]:
    """Deletes a template from the library.

    Args:
        name_id: Target template name.
        current_user: Admin access required.

    Returns:
        JSON confirmation message.
    """
    if TemplateService.get_template_content(name_id) is None:
         raise HTTPException(status_code=404, detail="Template not found")
         
    success = TemplateService.delete_template(name_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete template")
    return {"message": "Template deleted"}
