from pydantic import BaseModel
from typing import Optional

class CreatePlaybookRequest(BaseModel):
    name: str
    folder: Optional[str] = None
    template_id: Optional[str] = None
