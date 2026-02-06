from typing import Optional
from sqlmodel import Field, SQLModel

class Host(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    alias: str = Field(index=True)  # Friendly name
    hostname: str = Field(index=True)  # IP or FQDN
    ssh_user: str = Field(default="root")
    ssh_port: int = Field(default=22)
    ssh_key_path: Optional[str] = Field(default=None)  # Path to key (legacy/manual)
    ssh_key_secret: Optional[str] = Field(default=None) # Name of EnvVar secret for key
    ssh_password_secret: Optional[str] = Field(default=None) # Name of EnvVar secret for password
    group_name: str = Field(default="all")
