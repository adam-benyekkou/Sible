import logging
import sys
from app.core.config import get_settings

settings = get_settings()

def setup_logging():
    """
    Configures the standard Python logging module for the application.
    """
    log_level = logging.INFO
    if hasattr(settings, "DEBUG") and settings.DEBUG:
        log_level = logging.DEBUG

    # Formatter for console output
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Avoid duplicate handlers if setup is called multiple times
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)

    # Set levels for some noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.info(f"Logging initialized with level: {logging.getLevelName(log_level)}")
