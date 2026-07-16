import logging
import sys
import os
import structlog
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Configures structured JSON logging for AWS CloudWatch and Local Disk."""
    os.makedirs("logs", exist_ok=True)
    
    console_handler = logging.StreamHandler(sys.stdout)
    file_handler = RotatingFileHandler(
        filename="logs/enterprise_cart.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3              # Keep last 3 files
    )
    
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
        handlers=[console_handler, file_handler]
    )
    
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )