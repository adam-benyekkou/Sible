from sqlmodel import SQLModel, create_engine
from app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

def create_db_and_tables():
    # Import models here to ensure they are registered with SQLModel metadata
    from app.models import JobRun, AppSettings, PlaybookConfig, EnvVar, Host, User
    SQLModel.metadata.create_all(engine)
