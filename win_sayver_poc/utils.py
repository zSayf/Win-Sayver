"""
Utility functions and custom exceptions for Win Sayver POC.

This module provides common utilities, custom exception classes, and helper functions
used throughout the Win Sayver POC implementation.
"""

import logging
import json
import sys
import os
import time
import functools
import platform
import subprocess
from typing import Dict, Any, Optional, Callable, TypeVar, Union
from pathlib import Path


# Custom Exception Classes
class WinSayverError(Exception):
    """Base exception for Win Sayver application."""
    pass


class SystemProfilingError(WinSayverError):
    """Raised when system profiling fails."""
    pass


class WMIConnectionError(SystemProfilingError):
    """Raised when WMI connection fails."""
    pass


class DataValidationError(WinSayverError):
    """Raised when data validation fails."""
    pass


class FileOperationError(WinSayverError):
    """Raised when file operations fail."""
    pass


class RetryExhaustedError(WinSayverError):
    """Raised when retry attempts are exhausted."""
    pass


class TimeoutError(WinSayverError):
    """Raised when operation times out."""
    pass


# Required system keys for validation
REQUIRED_SYSTEM_KEYS = {
    'computer_system', 'operating_system', 'processor', 'physical_memory',
    'storage_devices', 'network_adapters', 'graphics_cards', 'audio_devices',
    'installed_software', 'system_services', 'environment_variables'
}


def safe_get_attribute(obj, attr_name: str, default: Any = None) -> Any:
    """
    Safely get attribute from an object.
    
    Args:
        obj: Object to get attribute from
        attr_name: Name of the attribute
        default: Default value if attribute doesn't exist
        
    Returns:
        Attribute value or default
    """
    try:
        return getattr(obj, attr_name, default)
    except Exception:
        return default


def format_bytes(bytes_value: Union[int, float, str]) -> str:
    """
    Format bytes into human readable format.
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    try:
        bytes_val = float(bytes_value)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} PB"
    except (ValueError, TypeError):
        return str(bytes_value)


def clean_string(value: Any) -> str:
    """
    Clean and format string values.
    
    Args:
        value: Value to clean
        
    Returns:
        Cleaned string
    """
    if value is None:
        return "Unknown"
    
    try:
        # Convert to string and clean
        cleaned = str(value).strip()
        
        # Remove null characters and control characters
        cleaned = ''.join(char for char in cleaned if ord(char) >= 32 or char in '\n\r\t')
        
        # Replace empty or whitespace-only strings
        if not cleaned or cleaned.isspace():
            return "Unknown"
            
        return cleaned
        
    except Exception:
        return "Unknown"


def validate_json_structure(data: Dict[str, Any]) -> bool:
    """
    Validate JSON structure for system specifications.
    
    Args:
        data: Dictionary to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check if data is a dictionary
        if not isinstance(data, dict):
            return False
        
        # Check for required top-level keys
        missing_keys = REQUIRED_SYSTEM_KEYS - set(data.keys())
        if missing_keys:
            logging.getLogger(__name__).warning(f"Missing required keys: {missing_keys}")
            return False
        
        # Basic validation passed
        return True
        
    except Exception as e:
        logging.getLogger(__name__).error(f"JSON validation error: {e}")
        return False


def safe_json_export(data: Dict[str, Any], filepath: Path) -> bool:
    """
    Safely export data to JSON file.
    
    Args:
        data: Data to export
        filepath: Path to save file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return True
    except Exception as e:
        logging.getLogger(__name__).error(f"JSON export error: {e}")
        return False


class PerformanceTimer:
    """
    Context manager for timing operations.
    """
    
    def __init__(self, operation_name: str = "Operation"):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
        self.duration = None
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        
        logger = logging.getLogger(__name__)
        if exc_type is None:
            logger.debug(f"{self.operation_name} completed in {self.duration:.3f}s")
        else:
            logger.warning(f"{self.operation_name} failed after {self.duration:.3f}s: {exc_val}")


class ErrorHandler:
    """
    Context manager for handling errors with customizable behavior.
    """
    
    def __init__(
        self,
        operation_name: str,
        logger: Optional[logging.Logger] = None,
        suppress_exceptions: bool = False,
        default_return: Any = None
    ):
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger(__name__)
        self.suppress_exceptions = suppress_exceptions
        self.default_return = default_return
        self.exception_occurred = False
        self.exception = None
    
    def __enter__(self):
        self.logger.debug(f"Starting {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.exception_occurred = True
            self.exception = exc_val
            self.logger.error(f"{self.operation_name} failed: {exc_val}")
            
            if self.suppress_exceptions:
                return True  # Suppress the exception
        else:
            self.logger.debug(f"{self.operation_name} completed successfully")
        
        return False


def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    logger: Optional[logging.Logger] = None,
    **kwargs
) -> Any:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        *args: Arguments to pass to the function
        default: Default value to return on error
        logger: Optional logger instance
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Function result or default value on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if logger:
            logger.error(f"Error executing {func.__name__}: {e}")
        return default