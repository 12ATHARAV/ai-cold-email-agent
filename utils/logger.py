import logging
import sys
from pathlib import Path

# Create logs directory if it doesn't exist
log_dir = Path(__file__).resolve().parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "app.log"

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    # If logger is already configured, return it
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger
