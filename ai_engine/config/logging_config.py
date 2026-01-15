"""
Centralized logging configuration for the entire project.
Call setup_logging() once at application startup.
"""

import logging
import os
from datetime import datetime
from config.settings import settings


def setup_logging(module_name: str = "AI_Engine", log_to_file: bool = True):
    """
    Setup centralized logging configuration.
    
    Args:
        module_name: Name for the log file (e.g., "sync_mysql", "indexer")
        log_to_file: Whether to log to file (True) or console only (False)
    
    Returns:
        Logger instance
    """
    # Create logs directory if not exists
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    
    # Clear existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    
    # Configure format
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (always active)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_to_file:
        log_filename = os.path.join(
            settings.LOG_DIR,
            f"{module_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Set log level
    root_logger.setLevel(logging.INFO)
    
    return root_logger


def get_logger(name: str):
    """
    Get a logger instance with the given name.
    Must call setup_logging() first!
    
    Args:
        name: Logger name (usually __name__ or module name)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
