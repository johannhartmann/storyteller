"""Logging configuration for StoryCraft Agent.

This module provides centralized logging configuration and utilities.
"""

# Standard library imports
import logging
import sys
from pathlib import Path
from typing import Optional


# Define log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """Set up logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        format_string: Optional custom format string
        
    Returns:
        Configured logger instance
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Create logger
    logger = logging.getLogger("storyteller")
    logger.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(format_string)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        try:
            # Create log directory if it doesn't exist
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Failed to create log file {log_file}: {e}")
    
    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("langchain_core").setLevel(logging.WARNING)
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name (defaults to module name)
        
    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"storyteller.{name}")
    return logging.getLogger("storyteller")


# Module-level logger instances for common modules
config_logger = get_logger("config")
graph_logger = get_logger("graph")
scene_logger = get_logger("scenes")
character_logger = get_logger("characters")
memory_logger = get_logger("memory")
progress_logger = get_logger("progress")


class LoggingContext:
    """Context manager for temporary logging level changes."""
    
    def __init__(self, logger: logging.Logger, level: str):
        """Initialize logging context.
        
        Args:
            logger: Logger to modify
            level: Temporary logging level
        """
        self.logger = logger
        self.original_level = logger.level
        self.new_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    
    def __enter__(self):
        """Enter context and set new level."""
        self.logger.setLevel(self.new_level)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and restore original level."""
        self.logger.setLevel(self.original_level)


def log_function_call(logger: logging.Logger):
    """Decorator to log function calls and results.
    
    Args:
        logger: Logger instance to use
        
    Returns:
        Decorator function
    """
    def decorator(func):
        """Decorator that logs function calls.
        
        Args:
            func: The function to wrap.
            
        Returns:
            Wrapped function.
        """
        def wrapper(*args, **kwargs):
            """Wrapper that logs function execution.
            
            Args:
                *args: Positional arguments for the function.
                **kwargs: Keyword arguments for the function.
                
            Returns:
                The function's return value.
                
            Raises:
                Any exception raised by the wrapped function.
            """
            func_name = func.__name__
            logger.debug(f"Calling {func_name} with args={args}, kwargs={kwargs}")
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"{func_name} completed successfully")
                return result
            except Exception as e:
                logger.error(f"{func_name} failed with error: {e}", exc_info=True)
                raise
        
        return wrapper
    return decorator