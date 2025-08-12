"""
Logging utilities for the SEC downloader.
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional
from .config import Config


def setup_logger(name: str = "sec_downloader", config: Optional[Config] = None) -> logging.Logger:
    """Set up and configure logger."""
    logger = logging.getLogger(name)
    
    if logger.handlers:  # Already configured
        return logger
    
    if config is None:
        config = Config()
    
    log_config = config.get('logging', {})
    paths_config = config.get_paths_config()
    
    # Create logs directory
    log_dir = Path(paths_config.get('logs', 'data/logs'))
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure logger
    logger.setLevel(getattr(logging, log_config.get('level', 'INFO')))
    
    # Create formatters
    formatter = logging.Formatter(
        log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    log_file = log_dir / "sec_downloader.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=7
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "sec_downloader") -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)
