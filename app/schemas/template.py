from pydantic import BaseModel
from typing import Optional

class TemplateCreate(BaseModel):
    name: str # Filename or path ID
    content: str

class TemplateUpdate(BaseModel):
    content: str
