"""
Utility functions and custom exceptions for Win Sayver POC.

This module provides common utilities, custom exception classes, and helper functions
used throughout the Win Sayver POC implementation.
"""

import functools
import json
import logging
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar, Union


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


# Enhanced Error Handling Utilities

T = TypeVar("T")


def retry_on_exception(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    logger: Optional[logging.Logger] = None,
) -> Callable:
    """
    Decorator for retrying function calls with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each retry
        exceptions: Tuple of exception types to catch and retry on
        logger: Optional logger for retry attempts

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        if logger:
                            logger.error(f"Function {func.__name__} failed after {max_retries} retries: {e}")
                        raise RetryExhaustedError(f"Function {func.__name__} failed after {max_retries} retries: {e}")

                    if logger:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {current_delay:.1f}s"
                        )

                    time.sleep(current_delay)
                    current_delay *= backoff_factor

            # This should never be reached, but just in case
            raise last_exception or Exception("Unknown error in retry logic")

        return wrapper

    return decorator


class ErrorHandler:
    """
    Context manager for handling errors with customizable behavior.
    """

    def __init__(
        self,
        operation_name: str,
        logger: Optional[logging.Logger] = None,
        suppress_exceptions: bool = False,
        default_return: Any = None,
        error_callback: Optional[Callable[[Exception], Any]] = None,
    ):
        """
        Initialize error handler.

        Args:
            operation_name: Name of the operation for logging
            logger: Optional logger instance
            suppress_exceptions: Whether to suppress exceptions and return default
            default_return: Default value to return if exception is suppressed
            error_callback: Optional callback function to call on error
        """
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger(__name__)
        self.suppress_exceptions = suppress_exceptions
        self.default_return = default_return
        self.error_callback = error_callback
        self.exception_occurred = False
        self.exception = None

    def __enter__(self):
        """Enter the context manager."""
        self.logger.debug(f"Starting {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and handle any exceptions."""
        if exc_type is not None:
            self.exception_occurred = True
            self.exception = exc_val

            self.logger.error(f"{self.operation_name} failed: {exc_val}")

            if self.error_callback:
                try:
                    self.error_callback(exc_val)
                except Exception as callback_error:
                    self.logger.error(f"Error callback failed: {callback_error}")

            if self.suppress_exceptions:
                self.logger.info(f"Suppressing exception for {self.operation_name}, returning default value")
                return True  # Suppress the exception
        else:
            self.logger.debug(f"{self.operation_name} completed successfully")

        return False  # Don't suppress exceptions by default

    def get_result(self, success_value: Any = None) -> Any:
        """
        Get the result based on whether an exception occurred.

        Args:
            success_value: Value to return if no exception occurred

        Returns:
            Success value if no exception, default_return if exception was suppressed
        """
        if self.exception_occurred and self.suppress_exceptions:
            return self.default_return
        return success_value


def safe_execute(
    func: Callable[..., T],
    *args,
    default: Any = None,
    logger: Optional[logging.Logger] = None,
    operation_name: Optional[str] = None,
    **kwargs,
) -> Union[T, Any]:
    """
    Safely execute a function with error handling.

    Args:
        func: Function to execute
        *args: Arguments to pass to the function
        default: Default value to return on error
        logger: Optional logger instance
        operation_name: Optional operation name for logging
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Function result or default value on error
    """
    op_name = operation_name or f"execution of {func.__name__}"
    log = logger or logging.getLogger(__name__)

    try:
        return func(*args, **kwargs)
    except Exception as e:
        log.error(f"Safe execution failed for {op_name}: {e}")
        return default


# System Environment Detection Utilities


def is_windows() -> bool:
    """Check if running on Windows."""
    return platform.system().lower() == "windows"


def is_admin() -> bool:
    """
    Check if the script is running with administrator privileges.

    Returns:
        True if running with admin privileges, False otherwise
    """
    if not is_windows():
        return os.geteuid() == 0  # Unix-like systems

    try:
        import ctypes

        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def check_wmi_availability() -> bool:
    """
    Check if WMI is available and accessible.

    Returns:
        True if WMI is available, False otherwise
    """
    if not is_windows():
        return False

    try:
        import wmi  # type: ignore

        c = wmi.WMI()
        # Try a simple query to test connectivity
        list(c.Win32_ComputerSystem())
        return True
    except Exception:
        return False


def check_psutil_availability() -> bool:
    """
    Check if psutil is available and working.

    Returns:
        True if psutil is available, False otherwise
    """
    try:
        import psutil

        # Test basic functionality
        psutil.cpu_count()
        return True
    except Exception:
        return False


def check_service_status(service_name: str) -> bool:
    """
    Check if a Windows service is running.

    Args:
        service_name: Name of the service to check

    Returns:
        True if service is running, False otherwise
    """
    if not is_windows():
        return False

    try:
        result = subprocess.run(["sc", "query", service_name], capture_output=True, text=True, timeout=5)
        return "RUNNING" in result.stdout
    except Exception:
        return False


def get_windows_version() -> Dict[str, Any]:
    """
    Get detailed Windows version information.

    Returns:
        Dictionary with version details
    """
    if not is_windows():
        return {}

    try:
        version_info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }

        # Try to get more detailed Windows info
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                try:
                    version_info["product_name"] = winreg.QueryValueEx(key, "ProductName")[0]
                except Exception:
                    pass
                try:
                    version_info["build_number"] = winreg.QueryValueEx(key, "CurrentBuildNumber")[0]
                except Exception:
                    pass
                try:
                    version_info["display_version"] = winreg.QueryValueEx(key, "DisplayVersion")[0]
                except Exception:
                    pass
        except Exception:
            pass

        return version_info
    except Exception:
        return {"error": "Unable to detect Windows version"}


def check_system_capabilities() -> Dict[str, bool]:
    """
    Check various system capabilities and dependencies.

    Returns:
        Dictionary mapping capability names to availability
    """
    capabilities = {
        "is_windows": is_windows(),
        "is_admin": is_admin(),
        "is_interactive": is_interactive(),
        "wmi_available": check_wmi_availability(),
        "psutil_available": check_psutil_availability(),
        "winmgmt_service": check_service_status("Winmgmt"),  # WMI service
        "bits_service": check_service_status("BITS"),  # Background transfer service
        "windows_update_service": check_service_status("wuauserv"),
    }

    return capabilities


def get_python_environment() -> Dict[str, Any]:
    """
    Get information about the Python environment.

    Returns:
        Dictionary with Python environment details
    """
    env_info = {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "architecture": platform.architecture(),
        "working_directory": os.getcwd(),
        "script_path": os.path.abspath(__file__) if "__file__" in globals() else "Unknown",
    }

    # Check for virtual environment
    if hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix):
        env_info["virtual_env"] = True
        env_info["virtual_env_path"] = sys.prefix
    else:
        env_info["virtual_env"] = False

    return env_info


# Enhanced Data Processing & Validation Utilities


def normalize_system_value(value: Any) -> Any:
    """
    Normalize system values for consistent processing.

    Args:
        value: Raw system value

    Returns:
        Normalized value
    """
    if value is None:
        return "N/A"

    if isinstance(value, str):
        # Clean up common system string issues
        cleaned = clean_string(value)
        if not cleaned or cleaned.lower() in ["none", "null", "unknown", ""]:
            return "N/A"
        return cleaned

    if isinstance(value, (int, float)):
        return value

    # Try to convert to string
    try:
        return str(value).strip()
    except Exception:
        return "N/A"


def validate_system_data(data: Dict[str, Any], schema: Dict[str, type]) -> Dict[str, Any]:
    """
    Validate and clean system data against a schema.

    Args:
        data: Raw system data
        schema: Expected data types for each key

    Returns:
        Validated and cleaned data
    """
    validated = {}

    for key, expected_type in schema.items():
        if key in data:
            value = data[key]
            try:
                if expected_type == str:
                    validated[key] = normalize_system_value(value)
                elif expected_type == int:
                    validated[key] = int(value) if value is not None else 0
                elif expected_type == float:
                    validated[key] = float(value) if value is not None else 0.0
                elif expected_type == bool:
                    validated[key] = bool(value)
                else:
                    validated[key] = value
            except (ValueError, TypeError):
                validated[key] = "N/A" if expected_type == str else None
        else:
            validated[key] = "N/A" if expected_type == str else None

    return validated


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize an object to be JSON-serializable.

    Args:
        obj: Object to sanitize

    Returns:
        JSON-serializable version of the object
    """
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]

    # Handle other types
    try:
        # Try to convert to string
        return str(obj)
    except Exception:
        return "<non-serializable>"


def merge_system_data(*data_dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple system data dictionaries with conflict resolution.

    Args:
        *data_dicts: Variable number of dictionaries to merge

    Returns:
        Merged dictionary
    """
    merged = {}

    for data_dict in data_dicts:
        if not isinstance(data_dict, dict):
            continue

        for key, value in data_dict.items():
            if key not in merged:
                merged[key] = value
            elif value is not None and merged[key] is None:
                # Prefer non-None values
                merged[key] = value
            elif isinstance(value, dict) and isinstance(merged[key], dict):
                # Recursively merge dictionaries
                merged[key] = merge_system_data(merged[key], value)
            elif isinstance(value, list) and isinstance(merged[key], list):
                # Combine lists, removing duplicates
                combined = merged[key] + value
                merged[key] = list(dict.fromkeys(combined))  # Remove duplicates while preserving order

    return merged


# Interactive/Non-Interactive Execution Utilities


def is_interactive() -> bool:
    """
    Check if the script is running in an interactive environment.

    Returns:
        True if running interactively, False otherwise
    """
    return sys.stdin.isatty() and sys.stdout.isatty()


def safe_input(prompt: str, default: str = "", timeout: Optional[float] = None) -> str:
    """
    Safely get user input with fallback for non-interactive environments.

    Args:
        prompt: The prompt to display to the user
        default: Default value to return if not interactive or on timeout
        timeout: Optional timeout in seconds

    Returns:
        User input or default value
    """
    if not is_interactive():
        print(f"{prompt}[auto: {default}]")
        return default

    try:
        if timeout:
            # For timeout functionality, we'd need additional imports
            # For now, just use regular input
            return input(prompt).strip() or default
        else:
            return input(prompt).strip() or default
    except (EOFError, KeyboardInterrupt):
        print(f"\n[Using default: {default}]")
        return default


def confirm_action(message: str, default: bool = False, auto_confirm: bool = False) -> bool:
    """
    Ask user for confirmation with safe fallback.

    Args:
        message: Confirmation message
        default: Default response if not interactive
        auto_confirm: If True, automatically confirm in non-interactive mode

    Returns:
        True if confirmed, False otherwise
    """
    if not is_interactive():
        if auto_confirm:
            print(f"{message} [auto-confirmed]")
            return True
        else:
            print(f"{message} [auto: {'yes' if default else 'no'}]")
            return default

    default_text = " [Y/n]" if default else " [y/N]"
    try:
        response = input(f"{message}{default_text}: ").strip().lower()
        if not response:
            return default
        return response in ["y", "yes", "true", "1"]
    except (EOFError, KeyboardInterrupt):
        print(f"\n[Using default: {'yes' if default else 'no'}]")
        return default


def get_choice(prompt: str, choices: list, default: str) -> str:
    """
    Get user choice from a list of options with safe fallback.

    Args:
        prompt: The prompt to display
        choices: List of valid choices
        default: Default choice if not interactive or invalid input

    Returns:
        Selected choice
    """
    if not choices:
        raise ValueError("Choices list cannot be empty")

    if default not in choices:
        default = choices[0]

    if not is_interactive():
        print(f"{prompt} [auto: {default}]")
        return default

    choices_str = "/".join(choices)
    full_prompt = f"{prompt} ({choices_str}): "

    try:
        while True:
            response = input(full_prompt).strip().lower()
            if not response:
                return default
            if response in [choice.lower() for choice in choices]:
                # Return the original case choice
                for choice in choices:
                    if choice.lower() == response:
                        return choice
            print(f"Invalid choice. Please select from: {choices_str}")
    except (EOFError, KeyboardInterrupt):
        print(f"\n[Using default: {default}]")
        return default


# Utility Functions
def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Set up logging configuration for Win Sayver POC.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


def safe_get_attribute(obj: Any, attribute: str, default: Any = "Unknown") -> Any:
    """
    Safely get an attribute from an object with a default fallback.

    Args:
        obj: Object to get attribute from
        attribute: Attribute name to retrieve
        default: Default value if attribute doesn't exist

    Returns:
        Attribute value or default
    """
    try:
        return getattr(obj, attribute, default)
    except Exception:
        return default


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes into human-readable format.

    Args:
        bytes_value: Number of bytes

    Returns:
        Formatted string (e.g., "1.5 GB", "512 MB")
    """
    if bytes_value == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    value = float(bytes_value)

    while value >= 1024.0 and i < len(size_names) - 1:
        value /= 1024.0
        i += 1

    return f"{value:.1f} {size_names[i]}"


def clean_string(value: str) -> str:
    """
    Clean and normalize string values.

    Args:
        value: String to clean

    Returns:
        Cleaned string
    """
    if not isinstance(value, str):
        return str(value)

    return value.strip().replace("\x00", "").replace("\n", " ").replace("\r", "")


def validate_json_structure(data: Dict[str, Any], required_keys: list) -> bool:
    """
    Validate that a dictionary contains all required keys.

    Args:
        data: Dictionary to validate
        required_keys: List of required keys

    Returns:
        True if all required keys are present, False otherwise

    Raises:
        DataValidationError: If validation fails
    """
    missing_keys = [key for key in required_keys if key not in data]

    if missing_keys:
        raise DataValidationError(f"Missing required keys: {missing_keys}")

    return True


def safe_json_export(data: Dict[str, Any], file_path: str) -> bool:
    """
    Safely export data to JSON file with error handling.

    Args:
        data: Data to export
        file_path: Path to save JSON file

    Returns:
        True if successful, False otherwise

    Raises:
        FileOperationError: If file operations fail
    """
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        return True

    except Exception as e:
        raise FileOperationError(f"Failed to export JSON to {file_path}: {e}")


def get_safe_filename(filename: str) -> str:
    """
    Create a safe filename by removing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Safe filename
    """
    invalid_chars = '<>:"/\\|?*'
    safe_name = filename

    for char in invalid_chars:
        safe_name = safe_name.replace(char, "_")

    return safe_name.strip()


class PerformanceTimer:
    """Context manager for measuring execution time."""

    def __init__(self, operation_name: str):
        """
        Initialize performance timer.

        Args:
            operation_name: Name of the operation being timed
        """
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
        self.thinking_tokens_used = 0
        self.thinking_budget_used = 0
        self.total_tokens_used = 0
        self.logger = logging.getLogger(__name__)
        # Initialize usage tracking
        self.usage = None

    def __enter__(self):
        """Start timing."""
        import time

        self.start_time = time.time()
        self.logger.debug(f"Starting {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and log result with thinking metrics."""
        import time

        self.end_time = time.time()

        if self.start_time is not None:
            duration = self.end_time - self.start_time

            # Base log message
            log_message = f"{self.operation_name} completed in {duration:.2f} seconds"

            # Add thinking metrics if available
            if self.usage is not None:
                usage = self.usage
                # Use getattr with default values to handle missing attributes
                self.total_tokens_used += getattr(usage, "total_tokens", 0)
                self.thinking_tokens_used += getattr(usage, "thinking_tokens", 0)

                # Calculate budget usage if available
                budget = getattr(usage, "thinking_budget", 0)
                if budget > 0:
                    self.thinking_budget_used = (usage.thinking_tokens / budget) * 100
                    log_message += (
                        f", {self.thinking_tokens_used} thinking tokens ({self.thinking_budget_used:.1f}% of budget)"
                    )
                else:
                    log_message += f", {self.thinking_tokens_used} thinking tokens"

            if exc_type is None:
                self.logger.info(log_message)
            else:
                self.logger.error(log_message)

        return False

    def record_thinking_metrics(self, thinking_tokens: int, budget_used: float) -> None:
        """
        Record thinking-related metrics.

        Args:
            thinking_tokens: Number of thinking tokens used
            budget_used: Percentage of thinking budget used (0-100)
        """
        self.thinking_tokens_used = thinking_tokens
        self.thinking_budget_used = budget_used

    @property
    def duration(self) -> Optional[float]:
        """Get the duration in seconds."""
        if self.start_time is not None:
            if self.end_time is not None:
                return self.end_time - self.start_time
            else:
                # If timer is still running, return current elapsed time
                import time

                return time.time() - self.start_time
        return 0.0  # Return 0.0 instead of None to prevent format errors


# Constants
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
JSON_INDENT = 2

# Required keys for system specification validation
REQUIRED_SYSTEM_KEYS = [
    "os_information",
    "hardware_specs",
    "software_inventory",
    "driver_information",
    "collection_timestamp",
]
