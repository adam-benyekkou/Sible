from typing import Optional
from pydantic import BaseModel

class HostBase(BaseModel):
    alias: str
    hostname: str
    ssh_user: str = "root"
    ssh_port: int = 22
    ssh_key_path: Optional[str] = None
    ssh_key_secret: Optional[str] = None
    ssh_password_secret: Optional[str] = None
    group_name: str = "all"

class HostCreate(HostBase):
    pass

class HostUpdate(BaseModel):
    alias: Optional[str] = None
    hostname: Optional[str] = None
    ssh_user: Optional[str] = None
    ssh_port: Optional[int] = None
    ssh_key_path: Optional[str] = None
    ssh_key_secret: Optional[str] = None
    ssh_password_secret: Optional[str] = None
    group_name: Optional[str] = None

class HostRead(HostBase):
    id: int
