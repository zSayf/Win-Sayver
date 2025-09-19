"""
System Specifications Collector for Win Sayver POC.

This module provides comprehensive Windows system profiling capabilities using WMI,
platform, and psutil libraries. It collects hardware, software, and system information
needed for AI-powered error analysis.

Main Features:
- Complete hardware specifications (CPU, memory, storage, GPU, motherboard)
- Software inventory (installed programs, services, drivers)
- System health monitoring and performance metrics
- Network configuration and connectivity info
- Security features and capabilities detection
- Command-line interface for standalone usage
- Integration with Win Sayver GUI application

Usage:
    # As a module
    from specs_collector import SystemSpecsCollector
    collector = SystemSpecsCollector()
    specs = collector.collect_all_specs()

    # Standalone execution
    python specs_collector.py --output specs.json --format json
"""

import argparse
import concurrent.futures
import json
import logging
import os
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Third-party imports
try:
    import psutil
except ImportError:
    print("Error: psutil library is required. Install with: pip install psutil")
    sys.exit(1)

# Windows-specific imports
try:
    import pythoncom
except ImportError:
    pythoncom = None
    print("Warning: pythoncom not available. Some WMI features may be limited.")

try:
    import wmi  # type: ignore
except ImportError:
    wmi = None
    print("Warning: WMI library not available. Install with: pip install WMI")

# Local imports - use direct imports to avoid type conflicts
from utils import (
    REQUIRED_SYSTEM_KEYS,
    PerformanceTimer,
    SystemProfilingError,
    WinSayverError,
    WMIConnectionError,
    clean_string,
    format_bytes,
    safe_get_attribute,
    safe_json_export,
    validate_json_structure,
)


class SystemSpecsCollector:
    """
    Collects comprehensive Windows system specifications.

    This class provides methods to gather detailed system information including
    OS details, hardware specifications, software inventory, and driver information
    using WMI, platform, and psutil libraries.
    """

    def __init__(self):
        """Initialize the system specs collector."""
        self.logger = logging.getLogger(__name__)
        self.wmi_connection = None
        self._initialize_wmi()

    def _initialize_wmi(self) -> None:
        """
        Initialize WMI connection with enhanced error handling and connection options.

        Raises:
            WMIConnectionError: If WMI initialization fails
        """
        try:
            import wmi  # type: ignore

            # Enhanced WMI connection with timeout and error handling
            self.wmi_connection = self._create_robust_wmi_connection()

            if self.wmi_connection:
                self.logger.debug("WMI connection initialized successfully")
            else:
                self.logger.warning("WMI connection created but may be unreliable")

        except ImportError:
            self.logger.error("WMI library not available")
            self.wmi_connection = None
            # Don't raise error, allow fallback methods
        except Exception as e:
            self.logger.error(f"Failed to initialize WMI connection: {e}")
            self.wmi_connection = None
            # Don't raise error, allow fallback methods

    def _create_robust_wmi_connection(self):
        """
        Create a robust WMI connection with proper COM threading and error handling.

        Returns:
            WMI connection object or None if failed
        """
        try:
            import wmi

            # Initialize COM for this thread with apartment threading
            if pythoncom:
                try:
                    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                except Exception:
                    try:
                        pythoncom.CoInitialize()
                    except Exception:
                        # COM already initialized or failed
                        pass

            # Create WMI connection with basic error handling
            connection = wmi.WMI()

            # Test the connection with a simple query
            try:
                list(connection.Win32_ComputerSystem())
                self.logger.debug("WMI connection test successful")
                return connection
            except Exception as e:
                self.logger.warning(f"WMI connection test failed: {e}")
                return None

        except Exception as e:
            self.logger.error(f"Failed to create robust WMI connection: {e}")
            return None

    def _create_thread_safe_wmi_connection(self):
        """
        Create a thread-safe WMI connection for use in worker threads.
        Each thread needs its own WMI connection to avoid COM marshaling issues.

        Returns:
            WMI connection object or None if failed
        """
        try:
            import wmi

            # Initialize COM with apartment threading for this specific thread
            if pythoncom:
                try:
                    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                except Exception:
                    try:
                        pythoncom.CoInitialize()
                    except Exception:
                        # COM already initialized
                        pass

            # Create a new WMI connection for this thread
            connection = wmi.WMI()

            # Quick test to ensure connection works
            try:
                list(connection.Win32_ComputerSystem())[:1]  # Limit to first result for speed
                self.logger.debug("Thread-safe WMI connection created successfully")
                return connection
            except Exception as e:
                self.logger.warning(f"Thread-safe WMI connection test failed: {e}")
                return None

        except Exception as e:
            self.logger.warning(f"Failed to create thread-safe WMI connection: {e}")
            return None

    def _safe_wmi_query(self, query_func, *args, max_retries=2, retry_delay=0.5, **kwargs):
        """
        Execute WMI query safely with error handling and thread-safe COM initialization.

        Args:
            query_func: WMI query function to execute
            *args: Arguments for the query function
            max_retries: Maximum number of retry attempts (default: 2)
            retry_delay: Delay between retries in seconds (default: 0.5)
            **kwargs: Keyword arguments for the query function

        Returns:
            Query result or None if failed
        """
        # Initialize COM for this thread with apartment threading
        if pythoncom:
            try:
                pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
            except Exception:
                try:
                    pythoncom.CoInitialize()
                except Exception:
                    # COM already initialized or failed
                    pass

        for attempt in range(max_retries):
            try:
                if not self.wmi_connection:
                    self.logger.warning("No WMI connection available")
                    return None

                # Execute the query with timeout
                result = query_func(*args, **kwargs)
                return list(result)  # Convert to list to catch errors early

            except Exception as e:
                # Check if this is a COM threading error
                if "marshalled for a different thread" in str(e):
                    self.logger.warning(f"COM threading error detected on attempt {attempt + 1}: {e}")
                    # Try to create a new connection for this thread
                    if attempt == 0:
                        try:
                            self.wmi_connection = self._create_thread_safe_wmi_connection()
                            if self.wmi_connection:
                                continue  # Retry with new connection
                        except Exception:
                            pass

                if attempt < max_retries - 1:
                    self.logger.debug(f"WMI query attempt {attempt + 1} failed: {e}, retrying...")
                    time.sleep(retry_delay)
                    # Try to reinitialize connection on first retry
                    if attempt == 0:
                        try:
                            self.wmi_connection = self._create_robust_wmi_connection()
                        except Exception:
                            pass
                else:
                    self.logger.warning(f"WMI query failed after {max_retries} attempts: {e}")
                    return None

        return None

    def collect_all_specs(self) -> Dict[str, Any]:
        """
        Collect all system specifications with performance optimizations and proper timer tracking.

        Returns:
            Dictionary containing complete system specifications

        Raises:
            SystemProfilingError: If system profiling fails
        """
        collection_timer = PerformanceTimer("Complete system profiling")
        collection_timer.__enter__()

        try:
            # Use concurrent collection for independent operations
            import concurrent.futures

            specs_data = {"collection_timestamp": datetime.now().isoformat(), "collection_duration_seconds": None}

            # Define collection tasks with optimized timeouts for performance
            # Tasks are now categorized by their threading requirements

            # Group collection tasks by their WMI dependency to optimize performance
            # WMI-heavy operations should be executed sequentially to avoid COM issues
            # Non-WMI operations can be executed concurrently

            wmi_intensive_tasks = [
                ("hardware_specs", self.get_hardware_specs, 8),  # Heavy WMI usage
            ]

            lightweight_tasks = [
                ("os_information", self.get_os_information, 8),  # Minimal WMI
                ("software_inventory", self.get_software_inventory, 12),  # No WMI
                ("driver_information", self.get_driver_information, 6),  # Registry-based
                ("system_health", self.get_system_health, 2),  # psutil only
                ("network_information", self.get_network_information, 2),  # psutil only
            ]

            # Execute lightweight tasks concurrently (safe since they don't heavily use WMI)
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_to_key = {}

                for key, func, timeout in lightweight_tasks:
                    future = executor.submit(self._execute_with_improved_timeout, func, timeout, key)
                    future_to_key[future] = key

                # Collect lightweight results as they complete
                for future in concurrent.futures.as_completed(future_to_key, timeout=15):
                    key = future_to_key[future]
                    try:
                        result = future.result()
                        specs_data[key] = result
                        self.logger.debug(f"Collected {key} successfully")
                    except Exception as e:
                        self.logger.warning(f"Failed to collect {key}: {e}")
                        specs_data[key] = {"error": f"Collection failed: {e}"}

            # Execute WMI-intensive tasks sequentially to avoid COM threading issues
            for key, func, timeout in wmi_intensive_tasks:
                try:
                    self.logger.debug(f"Starting {key} collection (WMI-intensive)...")
                    # Use direct execution for WMI-heavy operations to avoid thread overhead
                    with PerformanceTimer(f"{key} execution") as timer:
                        result = func()
                    specs_data[key] = result
                    self.logger.debug(f"Collected {key} successfully in {timer.duration:.2f}s")
                except Exception as e:
                    self.logger.warning(f"Failed to collect {key}: {e}")
                    specs_data[key] = {"error": f"Collection failed: {e}"}

            # Stop timer and record duration
            collection_timer.__exit__(None, None, None)
            specs_data["collection_duration_seconds"] = collection_timer.duration

            # Validate the collected data
            try:
                validate_json_structure(specs_data, REQUIRED_SYSTEM_KEYS)
            except Exception as e:
                self.logger.warning(f"Data validation failed: {e}")
                # Don't fail collection due to validation issues

            self.logger.info(f"System specifications collected successfully in {collection_timer.duration:.2f}s")
            return specs_data

        except Exception as e:
            collection_timer.__exit__(None, None, None)
            self.logger.error(f"System profiling failed: {e}")

            # Return partial data with error information instead of raising
            return {
                "collection_timestamp": datetime.now().isoformat(),
                "collection_duration_seconds": collection_timer.duration,
                "error": f"System profiling failed: {e}",
                "partial_data": True,
            }

    def _execute_with_improved_timeout(self, func, timeout_seconds, operation_name):
        """
        Execute a function with improved timeout protection and thread-safe COM initialization.

        Args:
            func: Function to execute
            timeout_seconds: Maximum execution time
            operation_name: Name of the operation for logging

        Returns:
            Function result or error information
        """
        import queue
        import threading

        result_queue = queue.Queue()

        def target():
            original_connection = None
            try:
                # Initialize COM with proper apartment threading for this thread
                if pythoncom:
                    try:
                        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                    except Exception:
                        try:
                            pythoncom.CoInitialize()
                        except Exception:
                            # COM already initialized or failed
                            pass

                # Create a new WMI connection for this thread to avoid COM marshaling issues
                if hasattr(self, "wmi_connection") and self.wmi_connection:
                    original_connection = self.wmi_connection
                    self.wmi_connection = self._create_thread_safe_wmi_connection()

                with PerformanceTimer(f"{operation_name} execution") as timer:
                    result = func()
                    result_queue.put(("success", result, timer.duration))

            except Exception as e:
                result_queue.put(("error", e, None))
            finally:
                # Restore original connection
                if original_connection:
                    self.wmi_connection = original_connection

                # Cleanup COM for this thread
                if pythoncom:
                    try:
                        pythoncom.CoUninitialize()
                    except Exception:
                        pass

        thread = threading.Thread(target=target, name=f"{operation_name}_thread")
        thread.daemon = True
        thread.start()
        thread.join(timeout_seconds)

        if thread.is_alive():
            self.logger.warning(f"Operation {operation_name} timed out after {timeout_seconds}s")
            return {"error": f"Operation timed out after {timeout_seconds}s"}

        try:
            status, data, duration = result_queue.get_nowait()
            if status == "success":
                self.logger.debug(f"{operation_name} completed in {duration:.2f}s")
                return data
            else:
                self.logger.warning(f"{operation_name} failed: {data}")
                return {"error": str(data)}
        except queue.Empty:
            self.logger.warning(f"{operation_name} completed but no result available")
            return {"error": "No result returned"}

    def get_os_information(self) -> Dict[str, str]:
        """
        Get detailed OS information using robust fallback methods with improved threading.

        Returns:
            Dictionary containing comprehensive OS information
        """
        try:
            with PerformanceTimer("OS information collection"):
                # Primary method: Platform library (fast and reliable)
                os_info = self._get_basic_os_info()

                # Enhanced Windows information with multiple fallback strategies
                if platform.system().lower() == "windows":
                    try:
                        # Strategy 1: Try registry-based information first (fastest)
                        registry_info = self._get_windows_registry_info_robust()
                        os_info.update(registry_info)

                        # Strategy 2: Try WMI with short timeout if registry data is incomplete
                        if len(registry_info) < 5:  # If registry didn't get enough data
                            wmi_info = self._get_windows_wmi_info_robust()
                            os_info.update(wmi_info)

                        # Strategy 3: PowerShell fallback for critical missing data
                        if not os_info.get("windows_edition"):
                            ps_info = self._get_windows_powershell_info()
                            os_info.update(ps_info)

                    except Exception as e:
                        self.logger.warning(f"Enhanced Windows info collection failed: {e}")
                        # Continue with basic info - don't let this fail completely

                return os_info

        except Exception as e:
            self.logger.warning(f"OS information collection failed: {e}")
            # Return minimal fallback data instead of failing completely
            return self._get_minimal_os_fallback()

    def _get_basic_os_info(self) -> Dict[str, str]:
        """
        Get basic OS information using platform library (fast and reliable).

        Returns:
            Dictionary containing basic OS information
        """
        os_info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "architecture": platform.architecture()[0],
            "platform": platform.platform(),
            "node": platform.node(),
            "python_version": platform.python_version(),
        }

        # Add Windows-specific information if available
        if hasattr(platform, "win32_ver"):
            try:
                win32_info = platform.win32_ver()
                os_info.update(
                    {
                        "windows_release": win32_info[0],
                        "windows_version": win32_info[1],
                        "windows_csd": win32_info[2],
                        "windows_type": win32_info[3],
                    }
                )
            except Exception as e:
                self.logger.warning(f"Failed to get win32_ver info: {e}")

        return os_info

    def _get_enhanced_windows_info_safe(self) -> Dict[str, Any]:
        """
        Get enhanced Windows-specific information with timeout protection.

        Returns:
            Dictionary containing enhanced Windows information
        """
        enhanced_info = {}

        # Registry-based information (fast and reliable)
        try:
            registry_info = self._get_windows_registry_info()
            enhanced_info.update(registry_info)
        except Exception as e:
            self.logger.warning(f"Failed to get Windows registry info: {e}")

        # WMI-based information with timeout protection
        try:
            wmi_info = self._get_windows_wmi_info_safe()
            enhanced_info.update(wmi_info)
        except Exception as e:
            self.logger.warning(f"Failed to get Windows WMI info: {e}")

        # System feature detection (lightweight)
        try:
            features_info = self._get_windows_features_safe()
            enhanced_info.update(features_info)
        except Exception as e:
            self.logger.warning(f"Failed to get Windows features: {e}")

        return enhanced_info

    def _get_windows_registry_info_robust(self) -> Dict[str, Any]:
        """
        Get Windows information from registry with enhanced error handling.

        Returns:
            Dictionary containing registry-based Windows information
        """
        registry_info = {}

        try:
            import winreg

            # Current Version information - most reliable source
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                    # Essential OS information
                    try:
                        registry_info["windows_edition"] = winreg.QueryValueEx(key, "ProductName")[0]
                    except FileNotFoundError:
                        pass

                    try:
                        build_number = winreg.QueryValueEx(key, "CurrentBuildNumber")[0]
                        registry_info["build_number"] = build_number

                        # Enhanced Windows 11 detection with edition correction
                        if int(build_number) >= 22000:
                            registry_info["windows_major_version"] = "11"
                            registry_info["release"] = "11"

                            # Fix Windows 11 edition name if registry shows Windows 10
                            edition_name = registry_info.get("windows_edition", "")
                            if edition_name and "Windows 10" in edition_name:
                                registry_info["windows_edition"] = edition_name.replace("Windows 10", "Windows 11")
                                self.logger.info(
                                    f"Corrected Windows edition from '{edition_name}' to '{registry_info['windows_edition']}' based on build {build_number}"
                                )
                        else:
                            registry_info["windows_major_version"] = "10"

                        # Full build number with UBR
                        try:
                            ubr = winreg.QueryValueEx(key, "UBR")[0]
                            registry_info["full_build_number"] = f"{build_number}.{ubr}"
                        except FileNotFoundError:
                            registry_info["full_build_number"] = build_number

                    except (FileNotFoundError, ValueError):
                        pass

                    # Display version (24H2, 23H2, etc.)
                    try:
                        registry_info["display_version"] = winreg.QueryValueEx(key, "DisplayVersion")[0]
                    except FileNotFoundError:
                        try:
                            registry_info["display_version"] = winreg.QueryValueEx(key, "ReleaseId")[0]
                        except FileNotFoundError:
                            pass

                    # Installation date
                    try:
                        install_date = winreg.QueryValueEx(key, "InstallDate")[0]
                        registry_info["install_date"] = str(install_date)
                    except FileNotFoundError:
                        pass

                    # Registered owner and organization
                    try:
                        registry_info["registered_owner"] = winreg.QueryValueEx(key, "RegisteredOwner")[0]
                    except FileNotFoundError:
                        pass

                    try:
                        registry_info["registered_organization"] = winreg.QueryValueEx(key, "RegisteredOrganization")[0]
                    except FileNotFoundError:
                        pass

            except Exception as e:
                self.logger.debug(f"Failed to access CurrentVersion registry key: {e}")

            # System locale information
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\International") as key:
                    registry_info["system_locale"] = winreg.QueryValueEx(key, "LocaleName")[0]
            except Exception:
                pass

            self.logger.debug(f"Registry OS info collected: {len(registry_info)} fields")

        except Exception as e:
            self.logger.warning(f"Registry OS access failed: {e}")

        return registry_info

    def _get_windows_wmi_info_robust(self) -> Dict[str, Any]:
        """
        Get Windows information from WMI with improved timeout and error handling.

        Returns:
            Dictionary containing WMI-based Windows information
        """
        wmi_info = {}

        try:
            # Initialize COM properly for this thread
            try:
                import pythoncom

                pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            except Exception:
                pass

            # Quick WMI queries with short timeout
            try:
                # Operating System details with safe query - very focused
                os_objects = self._safe_wmi_query(
                    lambda: self.wmi_connection.Win32_OperatingSystem() if self.wmi_connection else []
                )

                if os_objects:
                    for os_obj in os_objects[:1]:  # Only take first result
                        try:
                            wmi_info.update(
                                {
                                    "wmi_os_name": safe_get_attribute(os_obj, "Name"),
                                    "wmi_version": safe_get_attribute(os_obj, "Version"),
                                    "wmi_build_number": safe_get_attribute(os_obj, "BuildNumber"),
                                    "wmi_service_pack": safe_get_attribute(os_obj, "ServicePackMajorVersion"),
                                    "wmi_architecture": safe_get_attribute(os_obj, "OSArchitecture"),
                                    "source": "WMI",
                                }
                            )
                            break  # Only process first OS object
                        except Exception as e:
                            self.logger.debug(f"Failed to process WMI OS object: {e}")
                            continue

            except Exception as e:
                self.logger.debug(f"WMI OS query failed: {e}")

            self.logger.debug(f"WMI OS info collected: {len(wmi_info)} fields")

        except Exception as e:
            self.logger.warning(f"WMI OS query failed: {e}")

        return wmi_info

    def _get_windows_powershell_info(self) -> Dict[str, Any]:
        """
        Get Windows information using PowerShell as final fallback.

        Returns:
            Dictionary containing PowerShell-based Windows information
        """
        ps_info = {}

        try:
            import subprocess

            # Fast PowerShell command for essential OS info
            ps_command = "Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, WindowsBuildLabEx | ConvertTo-Json"

            result = subprocess.run(
                ["powershell", "-Command", ps_command], capture_output=True, text=True, timeout=3  # Very short timeout
            )

            if result.returncode == 0 and result.stdout:
                import json

                try:
                    ps_data = json.loads(result.stdout)

                    if isinstance(ps_data, dict):
                        ps_info.update(
                            {
                                "ps_product_name": ps_data.get("WindowsProductName", ""),
                                "ps_version": ps_data.get("WindowsVersion", ""),
                                "ps_build_lab": ps_data.get("WindowsBuildLabEx", ""),
                                "source": "PowerShell",
                            }
                        )

                    self.logger.debug(f"PowerShell OS info collected: {len(ps_info)} fields")

                except json.JSONDecodeError:
                    pass

        except Exception as e:
            self.logger.debug(f"PowerShell OS info collection failed: {e}")

        return ps_info

    def _get_minimal_os_fallback(self) -> Dict[str, Any]:
        """
        Get minimal OS information as absolute fallback when all other methods fail.

        Returns:
            Dictionary containing minimal OS information
        """
        try:
            import platform

            return {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "source": "platform_fallback",
                "note": "Minimal fallback data - some methods failed",
            }
        except Exception:
            return {"system": "Windows", "source": "emergency_fallback", "error": "All OS detection methods failed"}

    def _get_windows_wmi_info_safe(self) -> Dict[str, Any]:
        """
        Get Windows information from WMI with timeout protection.

        Returns:
            Dictionary containing WMI-based Windows information
        """
        wmi_info = {}

        try:
            # Operating System details with safe query
            os_objects = self._safe_wmi_query(
                lambda: self.wmi_connection.Win32_OperatingSystem() if self.wmi_connection else []
            )

            if os_objects:
                for os_obj in os_objects:
                    try:
                        wmi_info.update(
                            {
                                "os_caption": safe_get_attribute(os_obj, "Caption"),
                                "os_version": safe_get_attribute(os_obj, "Version"),
                                "os_build_number": safe_get_attribute(os_obj, "BuildNumber"),
                                "os_serial_number": safe_get_attribute(os_obj, "SerialNumber"),
                                "os_install_date": safe_get_attribute(os_obj, "InstallDate"),
                                "os_last_boot_time": safe_get_attribute(os_obj, "LastBootUpTime"),
                                "system_directory": safe_get_attribute(os_obj, "SystemDirectory"),
                                "windows_directory": safe_get_attribute(os_obj, "WindowsDirectory"),
                                "system_drive": safe_get_attribute(os_obj, "SystemDrive"),
                                "total_virtual_memory": safe_get_attribute(os_obj, "TotalVirtualMemorySize"),
                                "available_virtual_memory": safe_get_attribute(os_obj, "TotalVisibleMemorySize"),
                                "os_language": safe_get_attribute(os_obj, "OSLanguage"),
                                "os_architecture": safe_get_attribute(os_obj, "OSArchitecture"),
                                "service_pack_major": safe_get_attribute(os_obj, "ServicePackMajorVersion"),
                                "service_pack_minor": safe_get_attribute(os_obj, "ServicePackMinorVersion"),
                            }
                        )
                        break  # Take first OS object
                    except Exception as e:
                        self.logger.warning(f"Failed to process OS object: {e}")
                        continue

            # Computer System details with safe query
            cs_objects = self._safe_wmi_query(
                lambda: self.wmi_connection.Win32_ComputerSystem() if self.wmi_connection else []
            )

            if cs_objects:
                for cs in cs_objects:
                    try:
                        wmi_info.update(
                            {
                                "computer_name": safe_get_attribute(cs, "Name"),
                                "domain": safe_get_attribute(cs, "Domain"),
                                "workgroup": safe_get_attribute(cs, "Workgroup"),
                                "system_type": safe_get_attribute(cs, "SystemType"),
                                "total_physical_memory": safe_get_attribute(cs, "TotalPhysicalMemory"),
                                "manufacturer": safe_get_attribute(cs, "Manufacturer"),
                                "model": safe_get_attribute(cs, "Model"),
                                "system_family": safe_get_attribute(cs, "SystemFamily"),
                                "system_sku_number": safe_get_attribute(cs, "SystemSKUNumber"),
                            }
                        )
                        break
                    except Exception as e:
                        self.logger.warning(f"Failed to process ComputerSystem object: {e}")
                        continue

        except Exception as e:
            self.logger.warning(f"WMI OS query failed: {e}")

        return wmi_info

    def _get_windows_features_safe(self) -> Dict[str, Any]:
        """
        Detect Windows features and capabilities with timeout protection.

        Returns:
            Dictionary containing Windows feature information
        """
        features = {}

        try:
            # Check for TPM availability (safe WMI query)
            try:
                tpm_objects = self._safe_wmi_query(
                    lambda: self.wmi_connection.Win32_Tpm() if self.wmi_connection else []
                )
                if tpm_objects:
                    features["tpm_present"] = len(tpm_objects) > 0
                    if tpm_objects:
                        features["tpm_version"] = safe_get_attribute(tpm_objects[0], "SpecVersion")
                else:
                    features["tpm_present"] = False
            except Exception:
                features["tpm_present"] = False

            # Check for Secure Boot (quick check)
            try:
                import subprocess

                result = subprocess.run(
                    ["powershell", "-Command", "Confirm-SecureBootUEFI"], capture_output=True, text=True, timeout=3
                )
                features["secure_boot_enabled"] = "True" in result.stdout
            except Exception:
                features["secure_boot_enabled"] = "Unknown"

            # .NET Framework versions (registry based - fast)
            try:
                import winreg

                dotnet_versions = []
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\NET Framework Setup\NDP") as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            version_key = winreg.EnumKey(key, i)
                            if version_key.startswith("v"):
                                dotnet_versions.append(version_key)
                        except Exception:
                            continue
                features["dotnet_versions"] = dotnet_versions
            except Exception:
                features["dotnet_versions"] = []

        except Exception as e:
            self.logger.warning(f"Feature detection failed: {e}")

        return features

    def _get_enhanced_windows_info(self) -> Dict[str, Any]:
        """
        Get enhanced Windows-specific information from multiple sources with timeout protection.

        Returns:
            Dictionary containing enhanced Windows information
        """
        return self._get_enhanced_windows_info_safe()

    def _get_windows_registry_info(self) -> Dict[str, Any]:
        """
        Get Windows information from registry.

        Returns:
            Dictionary containing registry-based Windows information
        """
        registry_info = {}

        try:
            import winreg

            # Current Version information
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
                # Basic version info
                try:
                    registry_info["windows_edition"] = winreg.QueryValueEx(key, "ProductName")[0]
                except Exception:
                    pass

                try:
                    build_number = winreg.QueryValueEx(key, "CurrentBuildNumber")[0]
                    registry_info["build_number"] = build_number

                    # Enhanced Windows 11 detection with edition correction
                    if int(build_number) >= 22000:
                        registry_info["windows_major_version"] = "11"
                        registry_info["release"] = "11"

                        # Fix Windows 11 edition name if registry shows Windows 10
                        edition_name = registry_info.get("windows_edition", "")
                        if edition_name and "Windows 10" in edition_name:
                            registry_info["windows_edition"] = edition_name.replace("Windows 10", "Windows 11")
                            self.logger.info(
                                f"Corrected Windows edition from '{edition_name}' to '{registry_info['windows_edition']}' based on build {build_number}"
                            )
                    else:
                        registry_info["windows_major_version"] = "10"

                    # Full build number with UBR
                    try:
                        ubr = winreg.QueryValueEx(key, "UBR")[0]
                        registry_info["full_build_number"] = f"{build_number}.{ubr}"
                    except Exception:
                        registry_info["full_build_number"] = build_number

                except Exception:
                    pass

                # Display version (24H2, 23H2, etc.)
                try:
                    registry_info["display_version"] = winreg.QueryValueEx(key, "DisplayVersion")[0]
                except Exception:
                    try:
                        registry_info["display_version"] = winreg.QueryValueEx(key, "ReleaseId")[0]
                    except Exception:
                        pass

                # Installation date
                try:
                    install_date = winreg.QueryValueEx(key, "InstallDate")[0]
                    registry_info["install_date"] = str(install_date)
                except Exception:
                    pass

                # Registered owner and organization
                try:
                    registry_info["registered_owner"] = winreg.QueryValueEx(key, "RegisteredOwner")[0]
                except Exception:
                    pass

                try:
                    registry_info["registered_organization"] = winreg.QueryValueEx(key, "RegisteredOrganization")[0]
                except Exception:
                    pass

            # System locale and language information
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\International") as key:
                    registry_info["system_locale"] = winreg.QueryValueEx(key, "LocaleName")[0]
            except Exception:
                pass

            # Windows edition details
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\EditionID"
                ) as key:
                    registry_info["edition_id"] = winreg.QueryValueEx(key, "")[0]
            except Exception:
                pass

        except Exception as e:
            self.logger.warning(f"Registry access failed: {e}")

        return registry_info

    def _get_windows_wmi_info(self) -> Dict[str, Any]:
        """
        Get Windows information from WMI (legacy method, calls safe version).

        Returns:
            Dictionary containing WMI-based Windows information
        """
        return self._get_windows_wmi_info_safe()

    def _get_windows_features(self) -> Dict[str, Any]:
        """
        Detect Windows features and capabilities.

        Returns:
            Dictionary containing Windows feature information
        """
        features = {}

        try:
            # Check for TPM availability
            try:
                if self.wmi_connection:
                    tpm_info = list(self.wmi_connection.Win32_Tpm())
                    features["tpm_present"] = len(tpm_info) > 0
                    if tpm_info:
                        features["tpm_version"] = safe_get_attribute(tpm_info[0], "SpecVersion")
            except Exception:
                features["tpm_present"] = False

            # Check for Secure Boot (requires elevated permissions)
            try:
                import subprocess

                result = subprocess.run(
                    ["powershell", "-Command", "Confirm-SecureBootUEFI"], capture_output=True, text=True, timeout=5
                )
                features["secure_boot_enabled"] = "True" in result.stdout
            except Exception:
                features["secure_boot_enabled"] = "Unknown"

            # Check for Hyper-V capability
            try:
                import subprocess

                result = subprocess.run(["systeminfo"], capture_output=True, text=True, timeout=10)
                if result.stdout:
                    features["hyperv_requirements"] = "Hyper-V Requirements" in result.stdout
                    features["virtualization_enabled"] = "Virtualization Enabled In Firmware: Yes" in result.stdout
            except Exception:
                features["hyperv_requirements"] = "Unknown"

            # Windows Subsystem for Linux detection
            try:
                import subprocess

                result = subprocess.run(["wsl", "--status"], capture_output=True, text=True, timeout=5)
                features["wsl_available"] = result.returncode == 0
            except Exception:
                features["wsl_available"] = False

            # .NET Framework versions
            try:
                import winreg

                dotnet_versions = []
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\NET Framework Setup\NDP") as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            version_key = winreg.EnumKey(key, i)
                            if version_key.startswith("v"):
                                dotnet_versions.append(version_key)
                        except Exception:
                            continue
                features["dotnet_versions"] = dotnet_versions
            except Exception:
                features["dotnet_versions"] = []

        except Exception as e:
            self.logger.warning(f"Feature detection failed: {e}")

        return features

    def get_hardware_specs(self) -> Dict[str, Any]:
        """
        Get hardware specifications using optimized concurrent collection where safe.

        Returns:
            Dictionary containing hardware specifications
        """
        hardware_specs = {}

        try:
            with PerformanceTimer("Hardware specifications collection"):
                # Group operations by their independence and WMI usage
                # Operations that can run concurrently (different WMI objects)
                concurrent_operations = [
                    ("cpu", self._get_cpu_info),
                    ("memory", self._get_memory_info),
                    ("gpu", self._get_gpu_info),
                    ("motherboard", self._get_motherboard_info),
                ]

                # Execute concurrent operations
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    future_to_key = {}

                    for key, func in concurrent_operations:
                        future = executor.submit(self._safe_hardware_operation, func, key)
                        future_to_key[future] = key

                    # Collect results
                    for future in concurrent.futures.as_completed(future_to_key, timeout=6):
                        key = future_to_key[future]
                        try:
                            result = future.result()
                            hardware_specs[key] = result
                        except Exception as e:
                            self.logger.warning(f"Failed to collect {key}: {e}")
                            hardware_specs[key] = {"error": str(e)}

                # Storage operation separately (can be slow)
                try:
                    hardware_specs["storage"] = self._get_storage_info()
                except Exception as e:
                    self.logger.warning(f"Failed to collect storage info: {e}")
                    hardware_specs["storage"] = {"error": str(e), "physical_drives": [], "partitions": []}

                return hardware_specs

        except Exception as e:
            self.logger.warning(f"Failed to collect hardware specifications: {e}")
            return {"error": f"Hardware specifications collection failed: {e}"}

    def _safe_hardware_operation(self, func, operation_name):
        """
        Execute a hardware operation with proper COM initialization for this thread.

        Args:
            func: Function to execute
            operation_name: Name of the operation for logging

        Returns:
            Function result
        """
        original_connection = None
        try:
            # Initialize COM for this thread if needed
            if pythoncom:
                try:
                    pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                except Exception:
                    try:
                        pythoncom.CoInitialize()
                    except Exception:
                        pass

            # Create thread-local WMI connection for this operation
            original_connection = self.wmi_connection
            if original_connection:
                self.wmi_connection = self._create_thread_safe_wmi_connection()

            result = func()

            # Restore original connection
            if original_connection:
                self.wmi_connection = original_connection

            return result

        except Exception as e:
            # Restore original connection on error
            if original_connection:
                self.wmi_connection = original_connection
            raise e
        finally:
            # Cleanup COM
            if pythoncom:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def _get_cpu_info(self) -> Dict[str, Any]:
        """Get comprehensive CPU information from multiple sources."""
        cpu_info = {}

        try:
            # Using psutil for basic CPU info
            cpu_info["logical_cores"] = psutil.cpu_count(logical=True)
            cpu_info["physical_cores"] = psutil.cpu_count(logical=False)

            # CPU frequency information
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                cpu_info["current_frequency"] = cpu_freq.current
                cpu_info["max_frequency"] = cpu_freq.max
                cpu_info["min_frequency"] = cpu_freq.min
            else:
                cpu_info["current_frequency"] = "Unknown"
                cpu_info["max_frequency"] = "Unknown"
                cpu_info["min_frequency"] = "Unknown"

            # Per-core CPU usage
            try:
                cpu_percent_per_core = psutil.cpu_percent(percpu=True, interval=0.1)
                cpu_info["per_core_usage"] = cpu_percent_per_core
            except Exception:
                pass

            # Using WMI for detailed processor information with optimized safe query
            wmi_processors = self._safe_wmi_query(
                lambda: self.wmi_connection.Win32_Processor() if self.wmi_connection else [],
                max_retries=1,  # Reduce retries for faster response
            )

            if wmi_processors:
                try:
                    for processor in wmi_processors:
                        cpu_info.update(
                            {
                                "name": clean_string(safe_get_attribute(processor, "Name")),
                                "manufacturer": clean_string(safe_get_attribute(processor, "Manufacturer")),
                                "family": safe_get_attribute(processor, "Family"),
                                "model": self._get_cpu_model_enhanced(processor),
                                "stepping": safe_get_attribute(processor, "Stepping"),
                                "max_clock_speed": safe_get_attribute(processor, "MaxClockSpeed"),
                                "architecture": safe_get_attribute(processor, "Architecture"),
                                "processor_id": safe_get_attribute(processor, "ProcessorId"),
                                "socket_designation": safe_get_attribute(processor, "SocketDesignation"),
                                "voltage": safe_get_attribute(processor, "CurrentVoltage"),
                                "external_clock": safe_get_attribute(processor, "ExtClock"),
                                "l2_cache_size": safe_get_attribute(processor, "L2CacheSize"),
                                "l3_cache_size": safe_get_attribute(processor, "L3CacheSize"),
                                "address_width": safe_get_attribute(processor, "AddressWidth"),
                                "data_width": safe_get_attribute(processor, "DataWidth"),
                                "instruction_set": safe_get_attribute(processor, "Description"),
                                "thread_count": safe_get_attribute(processor, "ThreadCount"),
                                "core_count": safe_get_attribute(processor, "NumberOfCores"),
                                "enabled_core_count": safe_get_attribute(processor, "NumberOfEnabledCore"),
                            }
                        )
                        break  # Take first processor info
                except Exception as e:
                    self.logger.warning(f"Failed to process CPU info from WMI: {e}")

            # If WMI failed to get CPU name, try registry fallback
            if not cpu_info.get("name") or cpu_info.get("name") == "Unknown":
                try:
                    cpu_info.update(self._get_cpu_info_registry_fallback())
                except Exception as e:
                    self.logger.warning(f"CPU registry fallback failed: {e}")

            # Additional CPU features detection
            try:
                cpu_info.update(self._get_cpu_features())
            except Exception as e:
                self.logger.warning(f"Failed to get CPU features: {e}")

        except Exception as e:
            self.logger.warning(f"Failed to get CPU info: {e}")
            cpu_info["error"] = str(e)

        return cpu_info

    def _get_cpu_model_enhanced(self, processor) -> str:
        """
        Get enhanced CPU model information using multiple detection methods.

        Args:
            processor: WMI processor object

        Returns:
            CPU model string with enhanced detection
        """
        try:
            # First try WMI Model property
            model = safe_get_attribute(processor, "Model")

            # If WMI returns valid numeric model, return it
            if model and str(model).isdigit():
                return str(model)

            # If WMI fails, extract from Name or Identifier
            name = safe_get_attribute(processor, "Name")
            if name and "Model" in name:
                # Extract model number from processor name
                import re

                model_match = re.search(r"Model (\d+)", name)
                if model_match:
                    return model_match.group(1)

            # Try to extract from instruction set description
            instruction_set = safe_get_attribute(processor, "Description")
            if instruction_set:
                # For AMD: "AMD64 Family 25 Model 33 Stepping 0"
                import re

                model_match = re.search(r"Model (\d+)", instruction_set)
                if model_match:
                    return model_match.group(1)

            # Fallback to registry-based detection
            try:
                import winreg

                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
                ) as key:
                    identifier = winreg.QueryValueEx(key, "Identifier")[0]
                    # Extract model from identifier string
                    import re

                    model_match = re.search(r"Model (\d+)", identifier)
                    if model_match:
                        return model_match.group(1)
            except Exception:
                pass

            # If all methods fail, return "Unknown"
            return "Unknown"

        except Exception as e:
            self.logger.warning(f"CPU model enhanced detection failed: {e}")
            return "Unknown"

    def _get_memory_type_enhanced(self, memory) -> str:
        """
        Get enhanced memory type detection using speed analysis.

        Args:
            memory: WMI memory object

        Returns:
            Memory type name with enhanced detection
        """
        try:
            # First try WMI memory type
            memory_type = safe_get_attribute(memory, "MemoryType")

            # Standard memory type mapping
            memory_type_map = {
                0: "Unknown",
                1: "Other",
                2: "DRAM",
                3: "Synchronous DRAM",
                4: "Cache DRAM",
                5: "EDO",
                6: "EDRAM",
                7: "VRAM",
                8: "SRAM",
                9: "RAM",
                10: "ROM",
                11: "Flash",
                12: "EEPROM",
                13: "FEPROM",
                14: "EPROM",
                15: "CDRAM",
                16: "3DRAM",
                17: "SDRAM",
                18: "SGRAM",
                19: "RDRAM",
                20: "DDR",
                21: "DDR2",
                22: "DDR2 FB-DIMM",
                24: "DDR3",
                25: "FBD2",
                26: "DDR4",
                27: "LPDDR",
                28: "LPDDR2",
                29: "LPDDR3",
                30: "LPDDR4",
                34: "DDR5",
            }

            if (
                isinstance(memory_type, int)
                and memory_type in memory_type_map
                and memory_type_map[memory_type] != "Unknown"
            ):
                return memory_type_map[memory_type]

            # If WMI type is Unknown, use speed-based detection
            speed = safe_get_attribute(memory, "Speed")
            configured_speed = safe_get_attribute(memory, "ConfiguredClockSpeed")

            # Use the available speed value
            actual_speed = speed if speed else configured_speed

            if actual_speed and isinstance(actual_speed, int):
                # Speed-based DDR type detection
                if actual_speed >= 4800:  # DDR5 starts around 4800 MHz
                    return "DDR5"
                elif actual_speed >= 2133:  # DDR4 range: 2133-3200+ MHz
                    return "DDR4"
                elif actual_speed >= 800:  # DDR3 range: 800-2133 MHz
                    return "DDR3"
                elif actual_speed >= 400:  # DDR2 range: 400-800 MHz
                    return "DDR2"
                elif actual_speed >= 200:  # DDR range: 200-400 MHz
                    return "DDR"

            # If all detection methods fail
            return "Unknown"

        except Exception as e:
            self.logger.warning(f"Memory type enhanced detection failed: {e}")
            return "Unknown"

    def _get_cpu_features(self) -> Dict[str, Any]:
        """Detect CPU features and capabilities."""
        features = {}

        try:
            # Check for virtualization support using optimized WMI query
            wmi_processors = self._safe_wmi_query(
                lambda: self.wmi_connection.Win32_Processor() if self.wmi_connection else [],
                max_retries=1,  # Reduce retries for faster response
            )

            if wmi_processors:
                try:
                    for processor in wmi_processors:
                        features["virtualization_firmware_enabled"] = safe_get_attribute(
                            processor, "VirtualizationFirmwareEnabled"
                        )
                        features["vmm_enabled"] = safe_get_attribute(processor, "VMMonitorModeExtensions")
                        break
                except Exception:
                    pass

            # Temperature information with enhanced fallback methods
            try:
                # Use safer WMI query with better error handling
                temp_sensors = self._safe_wmi_query(
                    lambda: (
                        getattr(self.wmi_connection, "MSAcpi_ThermalZoneTemperature", lambda: [])()
                        if self.wmi_connection
                        else []
                    )
                )

                if temp_sensors and hasattr(temp_sensors[0], "CurrentTemperature"):
                    try:
                        # Convert from tenths of Kelvin to Celsius
                        temp_kelvin = temp_sensors[0].CurrentTemperature
                        if temp_kelvin and temp_kelvin > 0:
                            temp_celsius = (temp_kelvin / 10) - 273.15
                            if 0 <= temp_celsius <= 150:  # Sanity check for reasonable CPU temps
                                features["temperature_celsius"] = round(temp_celsius, 1)
                                features["temperature_source"] = "WMI_ThermalZone"
                            else:
                                self.logger.debug(f"Temperature out of range: {temp_celsius}°C")
                                alt_temp = self._get_temperature_fallback()
                                if alt_temp:
                                    features.update(alt_temp)
                        else:
                            # Invalid temperature data, use fallback
                            alt_temp = self._get_temperature_fallback()
                            if alt_temp:
                                features.update(alt_temp)
                    except (ValueError, TypeError, AttributeError) as e:
                        self.logger.debug(f"Temperature conversion failed: {e}")
                        alt_temp = self._get_temperature_fallback()
                        if alt_temp:
                            features.update(alt_temp)
                else:
                    # No thermal sensors found or accessible, use fallback
                    alt_temp = self._get_temperature_fallback()
                    if alt_temp:
                        features.update(alt_temp)
            except Exception as e:
                # Thermal zone query failed entirely, use fallback silently
                self.logger.debug(f"WMI thermal zone query failed: {e}")
                alt_temp = self._get_temperature_fallback()
                if alt_temp:
                    features.update(alt_temp)

        except Exception as e:
            self.logger.warning(f"CPU feature detection failed: {e}")

        return features

    def _get_temperature_fallback(self) -> Dict[str, Any]:
        """
        Get temperature information using alternative methods when WMI thermal zone fails.

        Returns:
            Dictionary with temperature information or empty dict if unavailable
        """
        temp_info = {}

        try:
            # Method 1: Try Open Hardware Monitor WMI namespace
            try:
                import wmi

                ohm_connection = wmi.WMI(namespace="root\\OpenHardwareMonitor")
                temp_sensors = ohm_connection.Sensor()

                for sensor in temp_sensors:
                    if sensor.SensorType == "Temperature" and "CPU" in sensor.Name:
                        temp_info["temperature_celsius"] = round(float(sensor.Value), 1)
                        temp_info["temperature_source"] = "OpenHardwareMonitor"
                        temp_info["temperature_sensor"] = sensor.Name
                        break

                if temp_info:
                    return temp_info
            except Exception:
                pass

            # Method 2: Try LibreHardwareMonitor WMI namespace
            try:
                import wmi

                lhm_connection = wmi.WMI(namespace="root\\LibreHardwareMonitor")
                temp_sensors = lhm_connection.Sensor()

                for sensor in temp_sensors:
                    if sensor.SensorType == "Temperature" and "CPU" in sensor.Name:
                        temp_info["temperature_celsius"] = round(float(sensor.Value), 1)
                        temp_info["temperature_source"] = "LibreHardwareMonitor"
                        temp_info["temperature_sensor"] = sensor.Name
                        break

                if temp_info:
                    return temp_info
            except Exception:
                pass

            # Method 3: Try psutil thermal sensors (Linux-style, may work on some Windows systems)
            try:
                import psutil

                if hasattr(psutil, "sensors_temperatures"):
                    temps = psutil.sensors_temperatures()
                    if temps:
                        for name, entries in temps.items():
                            for entry in entries:
                                if entry.current:
                                    temp_info["temperature_celsius"] = round(entry.current, 1)
                                    temp_info["temperature_source"] = "psutil"
                                    temp_info["temperature_sensor"] = f"{name}_{entry.label}"
                                    return temp_info
            except Exception:
                pass

            # Method 4: Try registry-based detection for some systems
            try:
                import winreg

                # Some systems store thermal info in registry
                registry_paths = [r"SYSTEM\CurrentControlSet\Control\ThermalZone", r"HARDWARE\DESCRIPTION\System\BIOS"]

                for path in registry_paths:
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
                            # This is a placeholder - actual thermal registry paths vary by manufacturer
                            # Most modern systems don't expose temperature via registry
                            pass
                    except Exception:
                        continue
            except Exception:
                pass

            # If no temperature detected, add enhanced informational guidance
            if not temp_info:
                temp_info = {
                    "temperature_celsius": None,
                    "temperature_source": "unavailable",
                    "temperature_note": "Temperature monitoring requires specialized software like HWiNFO64, OpenHardwareMonitor, or AIDA64. Windows does not expose CPU temperatures through standard APIs.",
                    "temperature_alternatives": [
                        "Install HWiNFO64 for comprehensive hardware monitoring",
                        "Use Core Temp for CPU temperature monitoring",
                        "Try OpenHardwareMonitor for open-source monitoring",
                        "Check BIOS/UEFI for hardware temperatures",
                    ],
                }

        except Exception as e:
            self.logger.warning(f"Temperature fallback detection failed: {e}")
            temp_info = {"temperature_celsius": None, "temperature_source": "error", "temperature_error": str(e)}

        return temp_info

    def _get_cpu_info_registry_fallback(self) -> Dict[str, Any]:
        """Get CPU information from Windows registry as fallback."""
        cpu_info = {}

        try:
            import winreg

            # Get CPU info from registry
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                try:
                    cpu_info["name"] = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
                except Exception:
                    pass

                try:
                    cpu_info["identifier"] = winreg.QueryValueEx(key, "Identifier")[0]
                except Exception:
                    pass

                try:
                    cpu_info["vendor_identifier"] = winreg.QueryValueEx(key, "VendorIdentifier")[0]
                except Exception:
                    pass

            self.logger.debug(f"CPU registry fallback collected: {len(cpu_info)} fields")

        except Exception as e:
            self.logger.warning(f"CPU registry fallback failed: {e}")

        return cpu_info

    def _get_memory_info(self) -> Dict[str, Any]:
        """Get comprehensive memory information."""
        memory_info = {}

        try:
            # Using psutil for current memory usage
            virtual_memory = psutil.virtual_memory()
            memory_info.update(
                {
                    "total": virtual_memory.total,
                    "total_formatted": format_bytes(virtual_memory.total),
                    "available": virtual_memory.available,
                    "available_formatted": format_bytes(virtual_memory.available),
                    "used": virtual_memory.used,
                    "used_formatted": format_bytes(virtual_memory.used),
                    "percentage": virtual_memory.percent,
                    "free": virtual_memory.free,
                    "free_formatted": format_bytes(virtual_memory.free),
                }
            )

            # Swap memory information
            try:
                swap_memory = psutil.swap_memory()
                memory_info["swap"] = {
                    "total": swap_memory.total,
                    "total_formatted": format_bytes(swap_memory.total),
                    "used": swap_memory.used,
                    "used_formatted": format_bytes(swap_memory.used),
                    "free": swap_memory.free,
                    "free_formatted": format_bytes(swap_memory.free),
                    "percentage": swap_memory.percent,
                }
            except Exception as e:
                self.logger.warning(f"Failed to get swap memory info: {e}")

            # Using WMI for detailed memory modules info
            memory_modules = self._safe_wmi_query(
                lambda: self.wmi_connection.Win32_PhysicalMemory() if self.wmi_connection else []
            )
            memory_module_list = []

            if memory_modules:
                try:
                    for memory in memory_modules:
                        module_info = {
                            "capacity": safe_get_attribute(memory, "Capacity"),
                            "capacity_formatted": format_bytes(int(safe_get_attribute(memory, "Capacity", "0"))),
                            "speed": safe_get_attribute(memory, "Speed"),
                            "configured_clock_speed": safe_get_attribute(memory, "ConfiguredClockSpeed"),
                            "manufacturer": self._get_memory_manufacturer_enhanced(memory),
                            "part_number": clean_string(safe_get_attribute(memory, "PartNumber")),
                            "serial_number": safe_get_attribute(memory, "SerialNumber"),
                            "memory_type": safe_get_attribute(memory, "MemoryType"),
                            "form_factor": safe_get_attribute(memory, "FormFactor"),
                            "device_locator": safe_get_attribute(memory, "DeviceLocator"),
                            "bank_label": safe_get_attribute(memory, "BankLabel"),
                            "data_width": safe_get_attribute(memory, "DataWidth"),
                            "total_width": safe_get_attribute(memory, "TotalWidth"),
                            "voltage": safe_get_attribute(memory, "ConfiguredVoltage"),
                        }

                        # Enhanced memory type detection using speed analysis
                        module_info["memory_type_name"] = self._get_memory_type_enhanced(memory)

                        memory_module_list.append(module_info)

                    memory_info["modules"] = memory_module_list

                    # Calculate total installed memory from modules
                    total_from_modules = sum(
                        int(module.get("capacity", 0)) for module in memory_module_list if module.get("capacity")
                    )
                    if total_from_modules > 0:
                        memory_info["total_from_modules"] = total_from_modules
                        memory_info["total_from_modules_formatted"] = format_bytes(total_from_modules)

                except Exception as e:
                    self.logger.warning(f"Failed to get memory modules info: {e}")

                # Memory array information (slots, maximum capacity)
                memory_arrays = self._safe_wmi_query(
                    lambda: self.wmi_connection.Win32_PhysicalMemoryArray() if self.wmi_connection else []
                )

                if memory_arrays:
                    try:
                        for array in memory_arrays:
                            memory_info["array_info"] = {
                                "max_capacity": safe_get_attribute(array, "MaxCapacity"),
                                "max_capacity_formatted": (
                                    format_bytes(int(safe_get_attribute(array, "MaxCapacity", "0")) * 1024)
                                    if safe_get_attribute(array, "MaxCapacity")
                                    else "Unknown"
                                ),
                                "memory_devices": safe_get_attribute(array, "MemoryDevices"),
                                "memory_error_correction": safe_get_attribute(array, "MemoryErrorCorrection"),
                            }
                            break
                    except Exception as e:
                        self.logger.warning(f"Failed to get memory array info: {e}")

        except Exception as e:
            self.logger.warning(f"Failed to get memory info: {e}")
            memory_info["error"] = str(e)

        return memory_info

    def _get_gpu_info(self) -> List[Dict[str, Any]]:
        """Get GPU information with robust error handling and fallbacks."""
        gpu_list = []

        try:
            # Primary method: WMI query with robust error handling
            wmi_gpus = self._safe_wmi_query(
                lambda: self.wmi_connection.Win32_VideoController() if self.wmi_connection else []
            )

            if wmi_gpus:
                for gpu in wmi_gpus:
                    try:
                        # Enhanced video memory detection with multiple methods
                        adapter_ram = safe_get_attribute(gpu, "AdapterRAM")
                        video_memory = 0
                        video_memory_formatted = "Unknown"

                        if adapter_ram and adapter_ram != "Unknown":
                            try:
                                video_memory = int(adapter_ram)
                                # Handle negative values (common WMI issue)
                                if video_memory < 0:
                                    # Convert from signed to unsigned 32-bit integer
                                    video_memory = video_memory + (2**32)

                                # WMI AdapterRAM is often inaccurate for modern GPUs
                                # Try to get accurate memory from registry for known GPUs
                                gpu_name = safe_get_attribute(gpu, "Name")
                                if gpu_name and "RX 6600 XT" in gpu_name:
                                    # AMD RX 6600 XT has 8GB VRAM, not what WMI reports
                                    video_memory = 8 * 1024 * 1024 * 1024  # 8GB in bytes
                                elif gpu_name and "RTX" in gpu_name:
                                    # Try to get accurate NVIDIA GPU memory
                                    registry_memory = self._get_gpu_memory_from_registry(gpu_name)
                                    if registry_memory > video_memory:
                                        video_memory = registry_memory

                                video_memory_formatted = format_bytes(video_memory)
                            except (ValueError, TypeError):
                                video_memory = 0
                                video_memory_formatted = "Unknown"

                        gpu_info = {
                            "name": clean_string(safe_get_attribute(gpu, "Name")),
                            "description": clean_string(safe_get_attribute(gpu, "Description")),
                            "driver_version": safe_get_attribute(gpu, "DriverVersion"),
                            "driver_date": safe_get_attribute(gpu, "DriverDate"),
                            "video_memory": video_memory,
                            "video_memory_formatted": video_memory_formatted,
                            "status": safe_get_attribute(gpu, "Status"),
                            "availability": safe_get_attribute(gpu, "Availability"),
                            "source": "WMI",
                        }
                        gpu_list.append(gpu_info)
                    except Exception as e:
                        self.logger.warning(f"Failed to process GPU info from WMI: {e}")
                        continue

            # Fallback method: Registry-based GPU detection
            if not gpu_list:
                self.logger.info("WMI GPU query failed, trying registry fallback")
                gpu_list = self._get_gpu_info_registry_fallback()

            # If still no GPU info, add a default entry indicating detection failed
            if not gpu_list:
                gpu_list.append(
                    {
                        "name": "GPU Detection Failed",
                        "description": "Unable to detect GPU through WMI or registry",
                        "error": "All detection methods failed",
                        "source": "Fallback",
                    }
                )

        except Exception as e:
            self.logger.warning(f"Failed to get GPU info: {e}")
            gpu_list.append({"error": str(e)})

        return gpu_list

    def _get_gpu_memory_from_registry(self, gpu_name: str) -> int:
        """
        Try to get accurate GPU memory information from Windows registry.

        Args:
            gpu_name: Name of the GPU

        Returns:
            GPU memory in bytes, 0 if not found
        """
        try:
            import winreg

            # Common DirectX registry paths for GPU information
            registry_paths = [
                r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}",
                r"SOFTWARE\Microsoft\DirectX",
                r"SYSTEM\CurrentControlSet\Control\Video",
            ]

            for registry_path in registry_paths:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                        # Enumerate subkeys to find GPU-specific entries
                        for i in range(10):  # Check first 10 subkeys
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    try:
                                        device_desc = winreg.QueryValueEx(subkey, "DriverDesc")[0]
                                        if gpu_name.lower() in device_desc.lower():
                                            # Try to get memory size
                                            try:
                                                memory_size = winreg.QueryValueEx(
                                                    subkey, "HardwareInformation.MemorySize"
                                                )[0]
                                                return int(memory_size)
                                            except FileNotFoundError:
                                                try:
                                                    memory_size = winreg.QueryValueEx(subkey, "VideoMemorySize")[0]
                                                    return int(memory_size)
                                                except FileNotFoundError:
                                                    pass
                                    except FileNotFoundError:
                                        pass
                            except OSError:
                                break
                except FileNotFoundError:
                    continue

        except Exception as e:
            self.logger.debug(f"GPU memory registry detection failed: {e}")

        return 0

    def _get_memory_manufacturer_enhanced(self, memory) -> str:
        """
        Get memory manufacturer using enhanced detection methods.

        Args:
            memory: WMI memory object

        Returns:
            Memory manufacturer name
        """
        try:
            # First try WMI manufacturer
            manufacturer = clean_string(safe_get_attribute(memory, "Manufacturer"))

            # If WMI returns Unknown or empty, try to identify from part number
            if not manufacturer or manufacturer.lower() in ["unknown", "", "undefined"]:
                part_number = safe_get_attribute(memory, "PartNumber", "")
                if part_number:
                    part_number = clean_string(str(part_number))

                    # Identify manufacturer from part number patterns
                    if part_number.startswith(("BL", "CMK", "CMH", "CMW", "CMY", "CMZ")):
                        return "Corsair"
                    elif part_number.startswith(("F4-", "F3-", "F2-")):
                        return "G.Skill"
                    elif part_number.startswith(("KHX", "HX", "KF")):
                        return "Kingston"
                    elif part_number.startswith(("CT", "BLS", "BLT")):
                        return "Crucial"
                    elif part_number.startswith(("CMN", "CMU", "CMD")):
                        return "Corsair"
                    elif part_number.startswith(("M378", "M393", "M471")):
                        return "Samsung"
                    elif part_number.startswith(("HMA", "HMT")):
                        return "SK Hynix"
                    elif part_number.startswith(("MT", "MTA")):
                        return "Micron"
                    elif "crucial" in part_number.lower():
                        return "Crucial"
                    elif "corsair" in part_number.lower():
                        return "Corsair"
                    elif "gskill" in part_number.lower() or "g.skill" in part_number.lower():
                        return "G.Skill"
                    elif "kingston" in part_number.lower():
                        return "Kingston"

            return manufacturer if manufacturer else "Unknown"

        except Exception as e:
            self.logger.debug(f"Memory manufacturer detection failed: {e}")
            return "Unknown"

    def _get_gpu_info_registry_fallback(self) -> List[Dict[str, Any]]:
        """
        Fallback method to get GPU information from Windows registry.

        Returns:
            List of GPU information dictionaries
        """
        gpu_list = []

        try:
            import winreg

            # Check DirectX registry entries for GPU information
            registry_paths = [
                r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}",  # Display adapters
                r"SOFTWARE\Microsoft\DirectX",
            ]

            for registry_path in registry_paths:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                        num_subkeys = winreg.QueryInfoKey(key)[0]

                        for i in range(num_subkeys):
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                if subkey_name.startswith("0"):
                                    with winreg.OpenKey(key, subkey_name) as subkey:
                                        gpu_info = {
                                            "source": "Registry",
                                            "name": "Unknown GPU",
                                            "description": "Detected via registry",
                                        }

                                        try:
                                            desc = winreg.QueryValueEx(subkey, "DriverDesc")[0]
                                            gpu_info["name"] = clean_string(desc)
                                            gpu_info["description"] = clean_string(desc)
                                        except FileNotFoundError:
                                            pass

                                        try:
                                            driver_version = winreg.QueryValueEx(subkey, "DriverVersion")[0]
                                            gpu_info["driver_version"] = driver_version
                                        except FileNotFoundError:
                                            pass

                                        try:
                                            driver_date = winreg.QueryValueEx(subkey, "DriverDate")[0]
                                            gpu_info["driver_date"] = driver_date
                                        except FileNotFoundError:
                                            pass

                                        if gpu_info["name"] != "Unknown GPU":
                                            gpu_list.append(gpu_info)

                            except Exception:
                                continue

                except Exception as e:
                    self.logger.debug(f"Registry GPU detection failed for path {registry_path}: {e}")
                    continue

        except Exception as e:
            self.logger.warning(f"Registry GPU fallback failed: {e}")

        return gpu_list

    def _get_motherboard_info(self) -> Dict[str, Any]:
        """Get motherboard information with robust error handling and fallbacks."""
        motherboard_info = {}

        try:
            # Primary method: WMI query with robust error handling
            wmi_boards = self._safe_wmi_query(
                lambda: self.wmi_connection.Win32_BaseBoard() if self.wmi_connection else []
            )

            if wmi_boards:
                for board in wmi_boards:
                    try:
                        motherboard_info.update(
                            {
                                "manufacturer": clean_string(safe_get_attribute(board, "Manufacturer")),
                                "product": clean_string(safe_get_attribute(board, "Product")),
                                "version": safe_get_attribute(board, "Version"),
                                "serial_number": safe_get_attribute(board, "SerialNumber"),
                                "source": "WMI",
                            }
                        )
                        break  # Take first motherboard info
                    except Exception as e:
                        self.logger.warning(f"Failed to process motherboard info from WMI: {e}")
                        continue

            # Fallback method: Computer System info
            if not motherboard_info or motherboard_info.get("manufacturer") in [None, "Unknown", ""]:
                self.logger.info("WMI BaseBoard query failed, trying ComputerSystem fallback")
                computer_system_info = self._get_motherboard_info_fallback()
                if computer_system_info:
                    motherboard_info.update(computer_system_info)

            # If still no motherboard info, try registry fallback
            if not motherboard_info or not any(motherboard_info.get(key) for key in ["manufacturer", "product"]):
                self.logger.info("Trying registry fallback for motherboard info")
                registry_info = self._get_motherboard_info_registry_fallback()
                if registry_info:
                    motherboard_info.update(registry_info)

            # If still no info, provide default error info
            if not motherboard_info or not any(motherboard_info.get(key) for key in ["manufacturer", "product"]):
                motherboard_info = {
                    "manufacturer": "Unknown",
                    "product": "Motherboard Detection Failed",
                    "error": "Unable to detect motherboard through WMI or registry",
                    "source": "Fallback",
                }

        except Exception as e:
            self.logger.warning(f"Failed to get motherboard info: {e}")
            motherboard_info["error"] = str(e)

        return motherboard_info

    def _get_motherboard_info_fallback(self) -> Dict[str, Any]:
        """
        Fallback method to get motherboard info from ComputerSystem.

        Returns:
            Dictionary with motherboard information
        """
        fallback_info = {}

        try:
            computer_systems = self._safe_wmi_query(
                lambda: self.wmi_connection.Win32_ComputerSystem() if self.wmi_connection else []
            )

            if computer_systems:
                for cs in computer_systems:
                    try:
                        fallback_info = {
                            "manufacturer": clean_string(safe_get_attribute(cs, "Manufacturer")),
                            "product": clean_string(safe_get_attribute(cs, "Model")),
                            "system_family": safe_get_attribute(cs, "SystemFamily"),
                            "system_sku": safe_get_attribute(cs, "SystemSKUNumber"),
                            "source": "WMI-ComputerSystem",
                        }
                        break
                    except Exception as e:
                        self.logger.warning(f"Failed to get ComputerSystem info: {e}")
                        continue

        except Exception as e:
            self.logger.warning(f"ComputerSystem fallback failed: {e}")

        return fallback_info

    def _get_motherboard_info_registry_fallback(self) -> Dict[str, Any]:
        """
        Fallback method to get motherboard info from Windows registry.

        Returns:
            Dictionary with motherboard information
        """
        registry_info = {}

        try:
            import winreg

            # BIOS/Motherboard registry entries
            registry_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS"),
                (winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"),
            ]

            for hkey, registry_path in registry_paths:
                try:
                    with winreg.OpenKey(hkey, registry_path) as key:
                        try:
                            vendor = winreg.QueryValueEx(key, "SystemManufacturer")[0]
                            registry_info["manufacturer"] = clean_string(vendor)
                        except FileNotFoundError:
                            try:
                                vendor = winreg.QueryValueEx(key, "VendorIdentifier")[0]
                                registry_info["manufacturer"] = clean_string(vendor)
                            except FileNotFoundError:
                                pass

                        try:
                            product = winreg.QueryValueEx(key, "SystemProductName")[0]
                            registry_info["product"] = clean_string(product)
                        except FileNotFoundError:
                            try:
                                product = winreg.QueryValueEx(key, "SystemFamily")[0]
                                registry_info["product"] = clean_string(product)
                            except FileNotFoundError:
                                pass

                        try:
                            version = winreg.QueryValueEx(key, "SystemVersion")[0]
                            registry_info["version"] = version
                        except FileNotFoundError:
                            pass

                        if registry_info:
                            registry_info["source"] = "Registry"
                            break

                except Exception as e:
                    self.logger.debug(f"Registry motherboard detection failed for path {registry_path}: {e}")
                    continue

        except Exception as e:
            self.logger.warning(f"Registry motherboard fallback failed: {e}")

        return registry_info

    def _get_storage_info(self) -> Dict[str, Any]:
        """
        Get comprehensive storage information including both physical drives and partitions.

        Returns:
            Dictionary containing physical drives and partition information
        """
        storage_data = {"physical_drives": [], "partitions": [], "drive_mapping": {}, "summary": {}}

        try:
            # Step 1: Collect partition information using psutil
            self.logger.debug("Collecting partition information...")
            disk_partitions = psutil.disk_partitions()
            partition_list = []

            for partition in disk_partitions:
                try:
                    disk_usage = psutil.disk_usage(partition.mountpoint)
                    partition_data = {
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "filesystem": partition.fstype,
                        "total_bytes": disk_usage.total,
                        "total_formatted": format_bytes(disk_usage.total),
                        "used_bytes": disk_usage.used,
                        "used_formatted": format_bytes(disk_usage.used),
                        "free_bytes": disk_usage.free,
                        "free_formatted": format_bytes(disk_usage.free),
                        "usage_percent": round((disk_usage.used / disk_usage.total) * 100, 1),
                        "mount_options": getattr(partition, "opts", ""),
                        "drive_letter": (
                            partition.device.rstrip("\\") if partition.device.endswith("\\") else partition.device
                        ),
                    }
                    partition_list.append(partition_data)

                except PermissionError:
                    self.logger.debug(f"Permission denied accessing {partition.device}")
                    continue
                except Exception as e:
                    self.logger.warning(f"Failed to get usage for {partition.device}: {e}")
                    continue

            storage_data["partitions"] = partition_list

            # Step 2: Collect physical drive information using WMI
            physical_drives = []
            drive_mapping = {}

            if self.wmi_connection:
                try:
                    self.logger.debug("Collecting physical drive information via WMI...")

                    # Get physical disk drives
                    wmi_disks = self._safe_wmi_query(
                        lambda: self.wmi_connection.Win32_DiskDrive() if self.wmi_connection else []
                    )

                    if wmi_disks:
                        for disk_index, disk in enumerate(wmi_disks):
                            try:
                                device_id = safe_get_attribute(disk, "DeviceID")
                                model = clean_string(safe_get_attribute(disk, "Model"))
                                size_bytes = safe_get_attribute(disk, "Size")

                                # Create comprehensive physical drive info
                                disk_info = {
                                    "index": disk_index,
                                    "device_id": device_id,
                                    "model": model,
                                    "manufacturer": clean_string(safe_get_attribute(disk, "Manufacturer")),
                                    "serial_number": safe_get_attribute(disk, "SerialNumber"),
                                    "size_bytes": int(size_bytes) if size_bytes else 0,
                                    "size_formatted": format_bytes(int(size_bytes)) if size_bytes else "Unknown",
                                    "interface_type": safe_get_attribute(disk, "InterfaceType"),
                                    "media_type": safe_get_attribute(disk, "MediaType"),
                                    "status": safe_get_attribute(disk, "Status"),
                                    "partition_count": safe_get_attribute(disk, "Partitions"),
                                    "bytes_per_sector": safe_get_attribute(disk, "BytesPerSector"),
                                    "sectors_per_track": safe_get_attribute(disk, "SectorsPerTrack"),
                                    "tracks_per_cylinder": safe_get_attribute(disk, "TracksPerCylinder"),
                                    "total_cylinders": safe_get_attribute(disk, "TotalCylinders"),
                                    "total_heads": safe_get_attribute(disk, "TotalHeads"),
                                    "total_sectors": safe_get_attribute(disk, "TotalSectors"),
                                    "total_tracks": safe_get_attribute(disk, "TotalTracks"),
                                    "partitions": [],  # Will be populated below
                                }

                                # Enhanced drive type detection
                                disk_info["drive_type"] = self._detect_drive_type(disk_info)

                                # Map partitions to this physical drive
                                if device_id:
                                    # Extract physical drive number from device ID
                                    drive_number = device_id.replace("\\\\.\\PHYSICALDRIVE", "")

                                    # Find partitions belonging to this physical drive
                                    drive_partitions = self._map_partitions_to_drive(
                                        drive_number, partition_list, disk_info
                                    )
                                    disk_info["partitions"] = drive_partitions

                                    # Create drive mapping for quick lookup
                                    drive_mapping[drive_number] = {
                                        "physical_drive": disk_info,
                                        "partitions": drive_partitions,
                                    }

                                physical_drives.append(disk_info)

                            except Exception as e:
                                self.logger.warning(f"Failed to process physical drive {disk_index}: {e}")
                                continue

                        self.logger.info(f"Successfully collected {len(physical_drives)} physical drives")
                    else:
                        self.logger.warning("No physical drives found via WMI")

                except Exception as e:
                    self.logger.error(f"Failed to collect physical drive info via WMI: {e}")

            # Step 3: Add disk I/O performance statistics
            try:
                disk_io = psutil.disk_io_counters(perdisk=True)
                for drive in physical_drives:
                    device_id = drive.get("device_id", "")
                    if device_id:
                        # Try to match disk IO stats
                        physical_disk_num = device_id.replace("\\\\.\\PHYSICALDRIVE", "")
                        io_key = f"PhysicalDrive{physical_disk_num}"

                        if io_key in disk_io:
                            io_stats = disk_io[io_key]
                            drive["io_stats"] = {
                                "read_count": io_stats.read_count,
                                "write_count": io_stats.write_count,
                                "read_bytes": io_stats.read_bytes,
                                "read_bytes_formatted": format_bytes(io_stats.read_bytes),
                                "write_bytes": io_stats.write_bytes,
                                "write_bytes_formatted": format_bytes(io_stats.write_bytes),
                                "read_time_ms": io_stats.read_time,
                                "write_time_ms": io_stats.write_time,
                            }
            except Exception as e:
                self.logger.warning(f"Failed to get disk I/O stats: {e}")

            # Step 4: Store results and create summary
            storage_data["physical_drives"] = physical_drives
            storage_data["drive_mapping"] = drive_mapping

            # Create storage summary
            summary = self._create_storage_summary(physical_drives, partition_list)
            storage_data["summary"] = summary

            self.logger.info(
                f"Storage collection complete: {len(physical_drives)} physical drives, "
                f"{len(partition_list)} partitions"
            )

        except Exception as e:
            self.logger.error(f"Failed to collect storage information: {e}")
            storage_data["error"] = str(e)

        return storage_data

    def _detect_drive_type(self, disk_info: Dict[str, Any]) -> str:
        """
        Enhanced drive type detection using multiple indicators.

        Args:
            disk_info: Dictionary containing disk information

        Returns:
            String indicating drive type (NVMe SSD, SSD, HDD, etc.)
        """
        try:
            media_type = str(disk_info.get("media_type", "")).lower()
            model = str(disk_info.get("model", "")).lower()
            interface_type = str(disk_info.get("interface_type", "")).lower()

            # Detect NVMe SSDs (highest priority)
            if (
                "nvme" in model
                or "m.2" in model
                or "pcie" in interface_type
                or "patriot m.2" in model
                or "p300" in model
            ):
                return "NVMe SSD"

            # Detect regular SSDs
            elif "ssd" in model or "solid state" in media_type or "sata ssd" in interface_type:
                return "SSD"

            # Detect HDDs
            elif (
                "hdd" in model
                or "hard disk" in media_type
                or "mechanical" in media_type
                or "ide" in interface_type
                or "sata" in interface_type
                and "ssd" not in model
            ):
                return "HDD"

            # Size-based heuristic as last resort
            else:
                size_bytes = disk_info.get("size_bytes", 0)
                if size_bytes > 0:
                    size_gb = size_bytes / (1024**3)
                    # Very small drives (< 64GB) are likely SSDs
                    if size_gb < 64:
                        return "SSD"
                    # Very large drives (> 4TB) are likely HDDs
                    elif size_gb > 4000:
                        return "HDD"

                return "Unknown"

        except Exception as e:
            self.logger.debug(f"Drive type detection failed: {e}")
            return "Unknown"

    def _map_partitions_to_drive(
        self, drive_number: str, partition_list: List[Dict[str, Any]], disk_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Map partitions to their physical drive using various methods.

        Args:
            drive_number: Physical drive number (e.g., "0", "1")
            partition_list: List of all partitions
            disk_info: Physical disk information

        Returns:
            List of partitions belonging to this drive
        """
        drive_partitions = []

        try:
            # Method 1: Try WMI Win32_LogicalDiskToPartition association
            if self.wmi_connection:
                try:
                    # Get all disk-to-partition associations
                    associations = self._safe_wmi_query(
                        lambda: self.wmi_connection.Win32_LogicalDiskToPartition() if self.wmi_connection else []
                    )

                    if associations:
                        for assoc in associations:
                            try:
                                antecedent = safe_get_attribute(assoc, "Antecedent")
                                dependent = safe_get_attribute(assoc, "Dependent")

                                if antecedent and dependent:
                                    # Extract disk number from antecedent
                                    if f"Disk #{drive_number}" in antecedent:
                                        # Extract drive letter from dependent
                                        if "LogicalDisk.DeviceID=" in dependent:
                                            drive_letter = dependent.split('DeviceID="')[1].split('"')[0]

                                            # Find matching partition
                                            for partition in partition_list:
                                                if partition["drive_letter"].startswith(drive_letter):
                                                    partition_copy = partition.copy()
                                                    partition_copy["physical_drive_number"] = drive_number
                                                    drive_partitions.append(partition_copy)

                            except Exception as e:
                                self.logger.debug(f"Failed to process partition association: {e}")
                                continue

                except Exception as e:
                    self.logger.debug(f"WMI partition mapping failed: {e}")

            # Method 2: Fallback - Simple heuristic mapping
            if not drive_partitions:
                # For drive 0, include C: and other early letters
                # For drive 1, include later letters
                # This is a simplified approach

                drive_num = int(drive_number) if drive_number.isdigit() else 0

                for partition in partition_list:
                    drive_letter = partition["drive_letter"].rstrip(":\\")

                    # Simple heuristic: first drive gets first few letters
                    if drive_num == 0 and drive_letter.upper() in ["C", "D", "E"]:
                        partition_copy = partition.copy()
                        partition_copy["physical_drive_number"] = drive_number
                        partition_copy["mapping_method"] = "heuristic"
                        drive_partitions.append(partition_copy)
                    elif drive_num > 0 and drive_letter.upper() not in ["C", "D", "E"]:
                        partition_copy = partition.copy()
                        partition_copy["physical_drive_number"] = drive_number
                        partition_copy["mapping_method"] = "heuristic"
                        drive_partitions.append(partition_copy)

        except Exception as e:
            self.logger.warning(f"Failed to map partitions to drive {drive_number}: {e}")

        return drive_partitions

    def _create_storage_summary(
        self, physical_drives: List[Dict[str, Any]], partitions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create a summary of storage information.

        Args:
            physical_drives: List of physical drive information
            partitions: List of partition information

        Returns:
            Dictionary containing storage summary
        """
        summary = {
            "physical_drive_count": len(physical_drives),
            "partition_count": len(partitions),
            "drive_types": {},
            "total_capacity": 0,
            "total_capacity_formatted": "0 B",
            "largest_drive": None,
            "system_drive": None,
        }

        try:
            # Count drive types
            drive_type_counts = {}
            total_bytes = 0
            largest_drive = None
            largest_size = 0

            for drive in physical_drives:
                drive_type = drive.get("drive_type", "Unknown")
                drive_type_counts[drive_type] = drive_type_counts.get(drive_type, 0) + 1

                size_bytes = drive.get("size_bytes", 0)
                if size_bytes > 0:
                    total_bytes += size_bytes

                    if size_bytes > largest_size:
                        largest_size = size_bytes
                        largest_drive = {
                            "model": drive.get("model", "Unknown"),
                            "size_formatted": drive.get("size_formatted", "Unknown"),
                            "drive_type": drive_type,
                        }

            summary["drive_types"] = drive_type_counts
            summary["total_capacity"] = total_bytes
            summary["total_capacity_formatted"] = format_bytes(total_bytes)
            summary["largest_drive"] = largest_drive

            # Find system drive (C:)
            for partition in partitions:
                if partition.get("drive_letter", "").upper().startswith("C"):
                    summary["system_drive"] = {
                        "drive_letter": partition.get("drive_letter", "C:"),
                        "total_formatted": partition.get("total_formatted", "Unknown"),
                        "usage_percent": partition.get("usage_percent", 0),
                        "filesystem": partition.get("filesystem", "Unknown"),
                    }
                    break

        except Exception as e:
            self.logger.warning(f"Failed to create storage summary: {e}")
            summary["error"] = str(e)

        return summary

    def get_software_inventory(self) -> Dict[str, Any]:
        """
        Get essential software inventory with aggressive performance optimization.

        Returns:
            Dictionary containing software inventory with categorized applications
        """
        software_inventory = {
            "installed_programs": [],
            "windows_store_apps": [],
            "browser_info": {},
            "system_services": [],
            "startup_programs": [],
            "running_processes": [],
        }

        try:
            with PerformanceTimer("Software inventory collection"):
                # ULTRA-FAST MODE: Only essential operations

                # 1. Browser info (fastest - registry only)
                software_inventory["browser_info"] = self._get_browser_info_fast()

                # 2. Installed programs (limited to 30 for speed)
                software_inventory["installed_programs"] = self._get_installed_programs_ultra_fast()

                # 3. Essential system services only (limited to 5)
                software_inventory["system_services"] = self._get_essential_services_fast()

                # 4. Startup programs (registry-based, fast)
                software_inventory["startup_programs"] = self._get_startup_programs_fast()

                # SKIP: Windows Store apps (too slow)
                software_inventory["windows_store_apps"] = []

                # SKIP: Running processes (psutil can be slow with many processes)
                software_inventory["running_processes"] = []

        except Exception as e:
            self.logger.warning(f"Failed to collect software inventory: {e}")
            software_inventory["error"] = f"Software inventory collection failed: {e}"

        return software_inventory

    def _get_browser_info_fast(self) -> Dict[str, Any]:
        """
        Get browser information using fastest possible method (registry only).

        Returns:
            Dictionary with essential browser information
        """
        browser_info = {"installed_browsers": [], "default_browser": ""}

        try:
            import winreg

            # Ultra-fast detection - only check AppPaths registry
            app_paths_browsers = {
                "Microsoft Edge": "msedge.exe",
                "Google Chrome": "chrome.exe",
                "Mozilla Firefox": "firefox.exe",
                "Opera": "opera.exe",
            }

            for browser_name, exe_name in app_paths_browsers.items():
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe_name}",
                    ) as key:
                        install_path = winreg.QueryValueEx(key, "")[0]
                        browser_info["installed_browsers"].append(
                            {
                                "name": browser_name,
                                "version": "Detected",
                                "install_path": install_path,
                                "source": "AppPaths",
                            }
                        )
                except FileNotFoundError:
                    pass

            # Get default browser quickly
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"SOFTWARE\\Microsoft\\Windows\\Shell\\Associations\\UrlAssociations\\http\\UserChoice",
                ) as key:
                    browser_info["default_browser"] = winreg.QueryValueEx(key, "ProgId")[0]
            except (FileNotFoundError, OSError):
                pass

            self.logger.info(f"Browser detection completed: {len(browser_info['installed_browsers'])} browsers found")

        except Exception as e:
            self.logger.warning(f"Fast browser detection failed: {e}")

        return browser_info

    def _get_installed_programs_ultra_fast(self) -> List[Dict[str, Any]]:
        """
        Get installed programs with ultra-fast collection (30 programs max).

        Returns:
            List of installed programs with essential information
        """
        programs_list = []

        try:
            import winreg

            # Only check main uninstall registry - skip WOW64 for speed
            registry_path = r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"

            seen_programs = set()
            max_programs = 30  # Ultra-reduced for speed

            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                    num_subkeys = winreg.QueryInfoKey(key)[0]

                    # Process only every 3rd program for maximum speed
                    step = max(3, num_subkeys // max_programs)

                    for i in range(0, min(num_subkeys, max_programs * step), step):
                        if len(programs_list) >= max_programs:
                            break

                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                program_info = self._extract_program_info_minimal(subkey)

                                if program_info and program_info.get("name"):
                                    unique_id = program_info["name"]
                                    if unique_id not in seen_programs:
                                        seen_programs.add(unique_id)
                                        programs_list.append(program_info)

                        except (OSError, FileNotFoundError):
                            continue
            except (OSError, FileNotFoundError):
                pass

        except Exception as e:
            self.logger.warning(f"Failed to get installed programs ultra-fast: {e}")

        return programs_list

    def _extract_program_info_minimal(self, subkey) -> Optional[Dict[str, Any]]:
        """
        Extract minimal program information for maximum speed.

        Args:
            subkey: Registry subkey object

        Returns:
            Dictionary with minimal program information or None if invalid
        """
        try:
            import winreg

            # Get only display name for speed
            try:
                display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
            except FileNotFoundError:
                return None

            # Quick filtering
            if (
                not display_name
                or len(display_name) < 3
                or display_name.startswith(("KB", "Hotfix", "Update for", "Microsoft Visual C++"))
                or "Security Update" in display_name
            ):
                return None

            # Minimal info only
            program_info = {"name": clean_string(display_name), "version": "", "publisher": ""}

            # Try to get version quickly (skip if takes time)
            try:
                version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                program_info["version"] = clean_string(str(version)) if version else ""
            except FileNotFoundError:
                pass

            # Skip publisher for speed

            return program_info

        except Exception:
            return None

    def _get_essential_services_fast(self) -> List[Dict[str, Any]]:
        """
        Get only the most essential system services for maximum speed.

        Returns:
            List of essential system services
        """
        services = []

        try:
            # Use psutil for speed instead of WMI
            import psutil

            # Only get a few critical services
            essential_service_names = [
                "AudioEndpointBuilder",
                "Audiosrv",
                "BITS",
                "Dhcp",
                "EventLog",
                "EventSystem",
                "DispBrokerDesktopSvc",
                "DisplayEnhancementService",
            ]

            service_count = 0
            max_services = 5  # Ultra-limited

            for service_name in essential_service_names:
                if service_count >= max_services:
                    break

                try:
                    service = psutil.win_service_get(service_name)
                    service_info = service.as_dict()

                    services.append(
                        {
                            "name": service_info.get("name", ""),
                            "display_name": service_info.get("display_name", ""),
                            "state": service_info.get("status", ""),
                            "start_mode": service_info.get("start_type", ""),
                            "source": "psutil",
                        }
                    )
                    service_count += 1

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            self.logger.warning(f"Failed to get essential services: {e}")

        return services

    def _get_startup_programs_fast(self) -> List[Dict[str, Any]]:
        """
        Get startup programs using fastest registry-based method.

        Returns:
            List of startup programs
        """
        startup_programs = []

        try:
            import winreg

            # Only check main startup locations for speed
            startup_locations = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"),
            ]

            max_startup = 10  # Limit for speed
            count = 0

            for hkey, path in startup_locations:
                if count >= max_startup:
                    break

                try:
                    with winreg.OpenKey(hkey, path) as key:
                        i = 0
                        while count < max_startup:
                            try:
                                name = winreg.EnumValue(key, i)[0]
                                command = winreg.EnumValue(key, i)[1]

                                startup_programs.append(
                                    {
                                        "name": clean_string(str(name)),
                                        "command": clean_string(str(command)),
                                        "location": "HKLM" if hkey == winreg.HKEY_LOCAL_MACHINE else "HKCU",
                                    }
                                )
                                count += 1
                                i += 1

                            except OSError:
                                break

                except (OSError, FileNotFoundError):
                    continue

        except Exception as e:
            self.logger.warning(f"Failed to get startup programs: {e}")

        return startup_programs

    def _get_installed_programs(self) -> List[Dict[str, Any]]:
        """
        Get installed programs from Windows registry with performance optimizations.

        Returns:
            List of installed programs with detailed information
        """
        programs_list = []

        try:
            import winreg

            registry_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]

            seen_programs = set()  # Avoid duplicates
            count = 0
            max_programs = 50  # Reduced limit for performance

            for hkey, path in registry_paths:
                try:
                    with winreg.OpenKey(hkey, path) as key:
                        num_subkeys = winreg.QueryInfoKey(key)[0]

                        # Process only a subset for speed
                        step = max(1, num_subkeys // max_programs) if num_subkeys > max_programs else 1

                        for i in range(0, min(num_subkeys, max_programs * step), step):
                            if count >= max_programs:
                                break

                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    program_info = self._extract_program_info_fast(subkey)

                                    if program_info and program_info.get("name"):
                                        # Use name as unique identifier
                                        unique_id = program_info["name"]
                                        if unique_id not in seen_programs:
                                            seen_programs.add(unique_id)
                                            programs_list.append(program_info)
                                            count += 1

                            except (OSError, FileNotFoundError):
                                continue
                except (OSError, FileNotFoundError):
                    continue

                if count >= max_programs:
                    break

        except Exception as e:
            self.logger.warning(f"Failed to get installed programs: {e}")

        return programs_list

    def _extract_program_info_fast(self, subkey) -> Optional[Dict[str, Any]]:
        """
        Extract essential program information quickly from a registry subkey.

        Args:
            subkey: Registry subkey object

        Returns:
            Dictionary with essential program information or None if invalid
        """
        try:
            import winreg

            # Get display name first (required)
            try:
                display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
            except FileNotFoundError:
                return None

            # Skip Windows updates and system components
            if (
                not display_name
                or len(display_name) < 3
                or display_name.startswith("KB")
                or display_name.startswith("Hotfix")
                or "Security Update" in display_name
                or "Update for" in display_name
                or display_name.startswith("Microsoft Visual C++")
            ):
                return None

            # Only collect essential information for speed
            program_info = {"name": clean_string(display_name), "version": "", "publisher": ""}

            # Get version and publisher quickly
            try:
                version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                program_info["version"] = clean_string(str(version)) if version else ""
            except FileNotFoundError:
                pass

            try:
                publisher = winreg.QueryValueEx(subkey, "Publisher")[0]
                program_info["publisher"] = clean_string(str(publisher)) if publisher else ""
            except FileNotFoundError:
                pass

            return program_info

        except Exception as e:
            self.logger.warning(f"Failed to extract program info: {e}")
            return None

    def _get_windows_store_apps(self) -> List[Dict[str, Any]]:
        """
        Get Windows Store apps using PowerShell.

        Returns:
            List of Windows Store apps
        """
        store_apps = []

        try:
            import subprocess

            # Use PowerShell to get Windows Store apps
            ps_command = "Get-AppxPackage | Select-Object Name, PackageFullName, Version, Publisher | ConvertTo-Json"
            result = subprocess.run(["powershell", "-Command", ps_command], capture_output=True, text=True, timeout=15)

            if result.returncode == 0 and result.stdout:
                import json

                apps_data = json.loads(result.stdout)

                # Handle both single app and multiple apps responses
                if isinstance(apps_data, dict):
                    apps_data = [apps_data]

                for app in apps_data[:50]:  # Limit to 50 apps
                    if isinstance(app, dict):
                        store_apps.append(
                            {
                                "name": app.get("Name", ""),
                                "full_name": app.get("PackageFullName", ""),
                                "version": app.get("Version", ""),
                                "publisher": app.get("Publisher", ""),
                            }
                        )

        except Exception as e:
            self.logger.warning(f"Failed to get Windows Store apps: {e}")

        return store_apps

    def _get_browser_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about installed browsers using multiple detection methods.

        Returns:
            Dictionary with enhanced browser information
        """
        browser_info = {"installed_browsers": [], "default_browser": ""}

        try:
            import os
            import winreg

            # Method 1: Registry-based detection (comprehensive)
            browsers_registry_paths = {
                "Google Chrome": [
                    r"SOFTWARE\Google\Chrome\BLBeacon",
                    r"SOFTWARE\WOW6432Node\Google\Chrome\BLBeacon",
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                ],
                "Mozilla Firefox": [
                    r"SOFTWARE\Mozilla\Mozilla Firefox",
                    r"SOFTWARE\WOW6432Node\Mozilla\Mozilla Firefox",
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe",
                ],
                "Microsoft Edge": [
                    r"SOFTWARE\Microsoft\Edge\BLBeacon",
                    r"SOFTWARE\WOW6432Node\Microsoft\Edge\BLBeacon",
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
                ],
                "Opera": [
                    r"SOFTWARE\Opera Software",
                    r"SOFTWARE\WOW6432Node\Opera Software",
                    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\opera.exe",
                ],
                "Brave": [
                    r"SOFTWARE\BraveSoftware\Brave-Browser\BLBeacon",
                    r"SOFTWARE\WOW6432Node\BraveSoftware\Brave-Browser\BLBeacon",
                ],
                "Vivaldi": [r"SOFTWARE\Vivaldi", r"SOFTWARE\WOW6432Node\Vivaldi"],
                "Safari": [
                    r"SOFTWARE\Apple Computer, Inc.\Safari",
                    r"SOFTWARE\WOW6432Node\Apple Computer, Inc.\Safari",
                ],
            }

            for browser_name, registry_paths in browsers_registry_paths.items():
                browser_found = False
                browser_version = "Unknown"
                install_path = ""

                for registry_path in registry_paths:
                    if browser_found:
                        break

                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                            # Try various version fields
                            version_fields = ["version", "Version", "pv", "CurrentVersion"]
                            for field in version_fields:
                                try:
                                    browser_version = winreg.QueryValueEx(key, field)[0]
                                    browser_found = True
                                    break
                                except FileNotFoundError:
                                    continue

                            # Try to get install path
                            try:
                                install_path = winreg.QueryValueEx(key, "Path")[0]
                            except FileNotFoundError:
                                try:
                                    install_path = winreg.QueryValueEx(key, "")
                                    if install_path and isinstance(install_path[0], str):
                                        install_path = install_path[0]
                                except FileNotFoundError:
                                    pass

                            if browser_found:
                                break
                    except FileNotFoundError:
                        continue

                if browser_found:
                    browser_data = {"name": browser_name, "version": browser_version, "source": "Registry"}
                    if install_path:
                        browser_data["install_path"] = install_path

                    browser_info["installed_browsers"].append(browser_data)

            # Method 2: App Paths detection (additional coverage)
            try:
                app_paths = [
                    ("chrome.exe", "Google Chrome"),
                    ("firefox.exe", "Mozilla Firefox"),
                    ("msedge.exe", "Microsoft Edge"),
                    ("opera.exe", "Opera"),
                    ("brave.exe", "Brave Browser"),
                    ("vivaldi.exe", "Vivaldi"),
                ]

                for exe_name, browser_name in app_paths:
                    # Skip if already found
                    if any(b["name"] == browser_name for b in browser_info["installed_browsers"]):
                        continue

                    try:
                        with winreg.OpenKey(
                            winreg.HKEY_LOCAL_MACHINE,
                            f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe_name}",
                        ) as key:
                            try:
                                app_path = winreg.QueryValueEx(key, "")[0]
                                if app_path and os.path.exists(app_path):
                                    browser_info["installed_browsers"].append(
                                        {
                                            "name": browser_name,
                                            "version": "Detected",
                                            "install_path": app_path,
                                            "source": "AppPaths",
                                        }
                                    )
                            except FileNotFoundError:
                                continue
                    except FileNotFoundError:
                        continue
            except Exception:
                pass

            # Method 3: Common installation directories (fallback detection)
            common_browser_paths = [
                (r"C:\Program Files\Google\Chrome\Application\chrome.exe", "Google Chrome"),
                (r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", "Google Chrome"),
                (r"C:\Program Files\Mozilla Firefox\firefox.exe", "Mozilla Firefox"),
                (r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe", "Mozilla Firefox"),
                (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "Microsoft Edge"),
                (r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", "Microsoft Edge"),
            ]

            for exe_path, browser_name in common_browser_paths:
                # Skip if already found
                if any(b["name"] == browser_name for b in browser_info["installed_browsers"]):
                    continue

                if os.path.exists(exe_path):
                    browser_info["installed_browsers"].append(
                        {
                            "name": browser_name,
                            "version": "File System Detection",
                            "install_path": exe_path,
                            "source": "FileSystem",
                        }
                    )

            # Get default browser (enhanced detection)
            try:
                # Windows 10/11 method
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"SOFTWARE\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
                ) as key:
                    prog_id = winreg.QueryValueEx(key, "ProgId")[0]
                    browser_info["default_browser"] = prog_id
            except Exception:
                try:
                    # Fallback method
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.html\UserChoice",
                    ) as key:
                        prog_id = winreg.QueryValueEx(key, "ProgId")[0]
                        browser_info["default_browser"] = prog_id
                except Exception:
                    pass

            # Sort browsers by name for consistent output
            browser_info["installed_browsers"].sort(key=lambda x: x["name"])

            self.logger.info(f"Browser detection completed: {len(browser_info['installed_browsers'])} browsers found")

        except Exception as e:
            self.logger.warning(f"Failed to get browser info: {e}")

        return browser_info

    def _get_system_services(self) -> List[Dict[str, Any]]:
        """
        Get critical system services information with enhanced collection methods.

        Returns:
            List of system services
        """
        services = []

        try:
            # Primary method: WMI services
            if self.wmi_connection:
                wmi_services = self._safe_wmi_query(
                    lambda: self.wmi_connection.Win32_Service(State="Running") if self.wmi_connection else []
                )

                if wmi_services:
                    # Get only essential running services for performance
                    service_count = 0
                    max_services = 20  # Increased limit

                    # Focus on important service categories
                    important_patterns = [
                        "windows",
                        "microsoft",
                        "security",
                        "network",
                        "audio",
                        "display",
                        "disk",
                        "system",
                    ]

                    for service in wmi_services:
                        if service_count >= max_services:
                            break

                        try:
                            service_name = safe_get_attribute(service, "Name") or ""
                            display_name = safe_get_attribute(service, "DisplayName") or ""

                            # Only include services that match important patterns or are critical
                            if any(
                                pattern.lower() in service_name.lower() or pattern.lower() in display_name.lower()
                                for pattern in important_patterns
                            ) or service_name.lower() in [
                                "spooler",
                                "themes",
                                "winmgmt",
                                "eventlog",
                                "bits",
                                "dhcp",
                                "dns",
                            ]:

                                service_info = {
                                    "name": service_name,
                                    "display_name": clean_string(display_name),
                                    "state": safe_get_attribute(service, "State"),
                                    "start_mode": safe_get_attribute(service, "StartMode"),
                                    "source": "WMI",
                                }
                                services.append(service_info)
                                service_count += 1
                        except Exception as e:
                            self.logger.warning(f"Failed to process WMI service: {e}")
                            continue

            # Fallback method: psutil services
            if not services:
                self.logger.info("WMI services failed, trying psutil fallback")
                services = self._get_services_psutil_fallback()

            # Additional fallback: PowerShell services
            if not services:
                self.logger.info("psutil services failed, trying PowerShell fallback")
                services = self._get_services_powershell_fallback()

        except Exception as e:
            self.logger.warning(f"Failed to get system services: {e}")

        return services

    def _get_services_psutil_fallback(self) -> List[Dict[str, Any]]:
        """
        Get system services using psutil as fallback with enhanced error handling.

        Returns:
            List of system services
        """
        services = []

        try:
            import psutil

            # Get Windows services via psutil with error handling
            service_count = 0
            max_services = 15

            for service in psutil.win_service_iter():
                if service_count >= max_services:
                    break

                try:
                    # Get service info with timeout protection
                    service_info = service.as_dict()

                    # Filter for important running services only
                    if service_info.get("status") == "running" and service_info.get("name"):

                        # Focus on important services
                        name = service_info.get("name", "").lower()
                        display_name = service_info.get("display_name", "").lower()

                        important_terms = ["windows", "microsoft", "system", "security", "network", "audio"]

                        if any(term in name or term in display_name for term in important_terms):
                            formatted_service = {
                                "name": service_info.get("name", ""),
                                "display_name": clean_string(service_info.get("display_name", "")),
                                "state": service_info.get("status", ""),
                                "start_mode": service_info.get("start_type", ""),
                                "source": "psutil",
                            }
                            services.append(formatted_service)
                            service_count += 1

                except (PermissionError, OSError, FileNotFoundError) as e:
                    # Skip services that can't be accessed due to permissions or missing files
                    # Common errors: WinError 5 (Access denied), WinError 1168 (Element not found), WinError 2 (File not found)
                    error_code = getattr(e, "winerror", None)
                    if error_code in [2, 5, 1168]:
                        self.logger.debug(
                            f"Skipped service due to known error {error_code}: service may be removed or require admin access"
                        )
                    else:
                        self.logger.debug(f"Skipped service due to permissions/access: {e}")
                    continue
                except Exception as e:
                    # Handle any other service-specific errors gracefully
                    self.logger.debug(f"Failed to process psutil service: {e}")
                    continue

        except Exception as e:
            self.logger.warning(f"psutil services fallback failed: {e}")

        return services

    def _get_services_powershell_fallback(self) -> List[Dict[str, Any]]:
        """
        Get system services using PowerShell as final fallback.

        Returns:
            List of system services
        """
        services = []

        try:
            import subprocess

            # PowerShell command to get running services
            ps_command = """Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object Name, DisplayName, Status, StartType | ConvertTo-Json"""

            result = subprocess.run(["powershell", "-Command", ps_command], capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and result.stdout:
                import json

                services_data = json.loads(result.stdout)

                # Handle both single service and multiple services responses
                if isinstance(services_data, dict):
                    services_data = [services_data]

                for service in services_data[:15]:  # Limit to 15 services
                    if isinstance(service, dict) and service.get("Name"):
                        service_info = {
                            "name": service.get("Name", ""),
                            "display_name": clean_string(service.get("DisplayName", "")),
                            "state": service.get("Status", ""),
                            "start_mode": service.get("StartType", ""),
                            "source": "PowerShell",
                        }
                        services.append(service_info)

        except Exception as e:
            self.logger.warning(f"PowerShell services fallback failed: {e}")

        return services

    def _get_startup_programs(self) -> List[Dict[str, Any]]:
        """
        Get startup programs from various locations.

        Returns:
            List of startup programs
        """
        startup_programs = []

        try:
            import winreg

            startup_locations = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce"),
            ]

            for hkey, path in startup_locations:
                try:
                    with winreg.OpenKey(hkey, path) as key:
                        for i in range(winreg.QueryInfoKey(key)[1]):  # Number of values
                            try:
                                name, value, _ = winreg.EnumValue(key, i)
                                startup_programs.append(
                                    {
                                        "name": clean_string(name),
                                        "command": clean_string(str(value)),
                                        "location": "HKLM" if hkey == winreg.HKEY_LOCAL_MACHINE else "HKCU",
                                    }
                                )
                            except Exception:
                                continue
                except FileNotFoundError:
                    continue

        except Exception as e:
            self.logger.warning(f"Failed to get startup programs: {e}")

        return startup_programs

    def _get_running_processes(self) -> List[Dict[str, Any]]:
        """
        Get information about running processes (top CPU/memory consumers).

        Returns:
            List of running processes
        """
        processes = []

        try:
            # Get all processes and sort by CPU/memory usage
            all_processes = []

            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "memory_info"]):
                try:
                    proc_info = proc.info
                    if proc_info["cpu_percent"] is None:
                        proc_info["cpu_percent"] = 0.0
                    if proc_info["memory_percent"] is None:
                        proc_info["memory_percent"] = 0.0
                    all_processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Sort by CPU usage and take top 20
            top_cpu_processes = sorted(all_processes, key=lambda x: x["cpu_percent"], reverse=True)[:20]

            for proc in top_cpu_processes:
                process_info = {
                    "pid": proc["pid"],
                    "name": proc["name"],
                    "cpu_percent": round(proc["cpu_percent"], 1),
                    "memory_percent": round(proc["memory_percent"], 1),
                }

                if proc.get("memory_info"):
                    process_info["memory_rss"] = format_bytes(proc["memory_info"].rss)
                    process_info["memory_vms"] = format_bytes(proc["memory_info"].vms)

                processes.append(process_info)

        except Exception as e:
            self.logger.warning(f"Failed to get running processes: {e}")

        return processes

    def get_driver_information(self) -> Dict[str, Any]:
        """
        Get essential driver information with ultra-fast collection optimized for concurrent execution.

        Returns:
            Dictionary containing driver information from fastest available sources
        """
        driver_info: Dict[str, Any] = {
            "driver_list": [],
            "display_drivers": [],
            "network_drivers": [],
            "audio_drivers": [],
            "storage_drivers": [],
        }

        try:
            with PerformanceTimer("Driver information collection"):
                # Ultra-fast approach: Direct registry access only (no WMI, no PowerShell)
                self._collect_drivers_ultra_fast(driver_info)

                # Only try alternative methods if we got very little data
                if len(driver_info["driver_list"]) < 8:
                    self.logger.info("Registry collection below target, trying limited WMI fallback")
                    self._collect_essential_drivers_fallback(driver_info)

                # Ensure we always have some driver data
                if not driver_info["driver_list"]:
                    driver_info["error"] = "No drivers could be detected with fast methods"
                    driver_info["note"] = "Driver detection optimized for speed over completeness"
                else:
                    self.logger.info(
                        f"Ultra-fast driver collection completed: {len(driver_info['driver_list'])} drivers"
                    )

        except Exception as e:
            self.logger.warning(f"Driver information collection failed: {e}")
            driver_info["error"] = f"Driver collection failed: {e}"

        return driver_info

    def _collect_drivers_wmi(self, driver_info: Dict[str, Any]) -> None:
        """
        Collect driver information using fast registry-based approach instead of slow WMI.

        Args:
            driver_info: Dictionary to populate with driver information
        """
        try:
            # Fast approach: Use registry-based driver collection instead of WMI
            self.logger.info("Using optimized registry-based driver collection for performance")

            # Collection using registry (much faster than WMI)
            self._collect_drivers_registry_fast(driver_info)

            # If registry approach didn't get enough data, try limited PowerShell
            total_drivers = len(driver_info.get("driver_list", []))
            if total_drivers < 5:
                self.logger.info("Registry collection got limited data, supplementing with fast PowerShell query")
                self._collect_drivers_powershell_minimal(driver_info)

            self.logger.info(
                f"Fast driver collection completed: {len(driver_info.get('driver_list', []))} drivers collected"
            )

        except Exception as e:
            self.logger.warning(f"Fast driver collection failed: {e}")
            # Fallback to original slow method only if absolutely necessary
            self._collect_drivers_wmi_original(driver_info)

    def _collect_drivers_powershell(self, driver_info: Dict[str, Any]) -> None:
        """
        Collect driver information using PowerShell as a fast fallback method.

        Args:
            driver_info: Dictionary to populate with driver information
        """
        try:
            import subprocess

            # Fast PowerShell command focusing on essential drivers only
            ps_command = (
                """Get-WmiObject Win32_VideoController | Select-Object Name, DriverVersion, Status | ConvertTo-Json"""
            )

            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=5,  # Reduced timeout for speed
            )

            if result.returncode == 0 and result.stdout:
                import json

                drivers_data = json.loads(result.stdout)

                # Handle both single driver and multiple drivers responses
                if isinstance(drivers_data, dict):
                    drivers_data = [drivers_data]

                for driver in drivers_data[:10]:  # Limit to 10 drivers for speed
                    if isinstance(driver, dict) and driver.get("Name"):
                        driver_data = {
                            "name": clean_string(driver.get("Name", "")),
                            "driver_version": driver.get("DriverVersion", ""),
                            "status": driver.get("Status", ""),
                            "source": "PowerShell",
                            "category": "display",
                        }

                        driver_info["display_drivers"].append(driver_data)
                        driver_info["driver_list"].append(driver_data)

                self.logger.info(f"PowerShell driver collection completed: {len(drivers_data)} drivers collected")

        except Exception as e:
            self.logger.warning(f"PowerShell driver collection failed: {e}")

    def _collect_drivers_registry_fast(self, driver_info: Dict[str, Any]) -> None:
        """
        Fast registry-based driver collection for essential drivers only.

        Args:
            driver_info: Dictionary to populate with driver information
        """
        try:
            import winreg

            # Get display drivers from registry (fastest method)
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}",
                ) as gpu_key:
                    gpu_count = 0
                    for i in range(10):  # Check first 10 subkeys
                        try:
                            subkey_name = winreg.EnumKey(gpu_key, i)
                            if subkey_name.isdigit():  # Only numbered keys
                                with winreg.OpenKey(gpu_key, subkey_name) as driver_key:
                                    try:
                                        driver_desc = winreg.QueryValueEx(driver_key, "DriverDesc")[0]
                                        driver_version = winreg.QueryValueEx(driver_key, "DriverVersion")[0]
                                        driver_data = {
                                            "name": clean_string(driver_desc),
                                            "driver_version": driver_version,
                                            "source": "Registry-GPU",
                                            "category": "display",
                                        }
                                        driver_info["display_drivers"].append(driver_data)
                                        driver_info["driver_list"].append(driver_data)
                                        gpu_count += 1
                                        if gpu_count >= 3:  # Limit to 3 GPUs
                                            break
                                    except FileNotFoundError:
                                        continue
                        except Exception:
                            continue
            except Exception:
                pass

            # Get network drivers from registry
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}",
                ) as net_key:
                    net_count = 0
                    for i in range(10):  # Check first 10 subkeys
                        try:
                            subkey_name = winreg.EnumKey(net_key, i)
                            if subkey_name.isdigit():  # Only numbered keys
                                with winreg.OpenKey(net_key, subkey_name) as driver_key:
                                    try:
                                        driver_desc = winreg.QueryValueEx(driver_key, "DriverDesc")[0]
                                        driver_data = {
                                            "name": clean_string(driver_desc),
                                            "source": "Registry-Network",
                                            "category": "network",
                                        }
                                        driver_info["network_drivers"].append(driver_data)
                                        driver_info["driver_list"].append(driver_data)
                                        net_count += 1
                                        if net_count >= 3:  # Limit to 3 network adapters
                                            break
                                    except FileNotFoundError:
                                        continue
                        except Exception:
                            continue
            except Exception:
                pass

            self.logger.debug(f"Registry driver collection: {len(driver_info['driver_list'])} drivers found")

        except Exception as e:
            self.logger.warning(f"Registry driver collection failed: {e}")

    def _collect_drivers_powershell_minimal(self, driver_info: Dict[str, Any]) -> None:
        """
        Minimal PowerShell driver collection for supplementing registry data.

        Args:
            driver_info: Dictionary to populate with driver information
        """
        try:
            import subprocess

            # Very fast PowerShell command for essential drivers only
            ps_command = (
                "Get-WmiObject Win32_VideoController | Select-Object -First 2 Name, DriverVersion | ConvertTo-Json"
            )

            result = subprocess.run(
                ["powershell", "-Command", ps_command], capture_output=True, text=True, timeout=3  # Very short timeout
            )

            if result.returncode == 0 and result.stdout:
                import json

                try:
                    drivers_data = json.loads(result.stdout)

                    # Handle both single driver and multiple drivers responses
                    if isinstance(drivers_data, dict):
                        drivers_data = [drivers_data]

                    for driver in drivers_data[:3]:  # Limit to 3 drivers for speed
                        if isinstance(driver, dict) and driver.get("Name"):
                            driver_data = {
                                "name": clean_string(driver.get("Name", "")),
                                "driver_version": driver.get("DriverVersion", ""),
                                "source": "PowerShell-Minimal",
                                "category": "display",
                            }

                            driver_info["display_drivers"].append(driver_data)
                            driver_info["driver_list"].append(driver_data)

                    self.logger.debug(f"PowerShell minimal collection: {len(drivers_data)} drivers added")
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            self.logger.warning(f"PowerShell minimal driver collection failed: {e}")

    def _collect_drivers_wmi_original(self, driver_info: Dict[str, Any]) -> None:
        """
        Original slow WMI driver collection as absolute last resort.
        Only use when all other methods fail completely.

        Args:
            driver_info: Dictionary to populate with driver information
        """
        try:
            # Only collect most essential display drivers with severe limits
            display_drivers = self._safe_wmi_query(
                lambda: self.wmi_connection.Win32_VideoController() if self.wmi_connection else []
            )

            if display_drivers:
                for gpu in display_drivers[:1]:  # Only take first GPU
                    try:
                        driver_data = {
                            "name": clean_string(safe_get_attribute(gpu, "Name")),
                            "driver_version": safe_get_attribute(gpu, "DriverVersion"),
                            "source": "WMI-Fallback",
                            "category": "display",
                        }

                        if driver_data["name"]:
                            driver_info["display_drivers"].append(driver_data)
                            driver_info["driver_list"].append(driver_data)
                            break  # Only one driver

                    except Exception as e:
                        self.logger.warning(f"Failed to process fallback driver: {e}")
                        break

            self.logger.debug("WMI fallback driver collection completed")

        except Exception as e:
            self.logger.warning(f"WMI fallback driver collection failed: {e}")

    def _collect_drivers_ultra_fast(self, driver_info: Dict[str, Any]) -> None:
        """
        Enhanced driver collection using comprehensive registry access for better coverage.

        Args:
            driver_info: Dictionary to populate with driver information
        """
        try:
            import winreg

            # Enhanced strategy: Get comprehensive driver information for better analysis
            drivers_collected = 0
            max_drivers = 20  # Increased from 8 to 20 for better coverage

            # 1. GPU/Display drivers (highest priority for troubleshooting)
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}",
                ) as gpu_key:
                    for i in range(6):  # Increased from 3 to 6 for multiple GPUs
                        try:
                            subkey_name = winreg.EnumKey(gpu_key, i)
                            if subkey_name.isdigit() and drivers_collected < max_drivers:
                                with winreg.OpenKey(gpu_key, subkey_name) as driver_key:
                                    try:
                                        driver_desc = winreg.QueryValueEx(driver_key, "DriverDesc")[0]
                                        try:
                                            driver_version = winreg.QueryValueEx(driver_key, "DriverVersion")[0]
                                        except FileNotFoundError:
                                            driver_version = "Unknown"

                                        driver_data = {
                                            "name": clean_string(driver_desc),
                                            "driver_version": driver_version,
                                            "source": "Registry-GPU-Enhanced",
                                            "category": "display",
                                            "type": "essential",
                                        }
                                        driver_info["display_drivers"].append(driver_data)
                                        driver_info["driver_list"].append(driver_data)
                                        drivers_collected += 1
                                    except FileNotFoundError:
                                        continue
                        except Exception:
                            continue
            except Exception:
                pass

            # 2. Network drivers (expanded coverage)
            if drivers_collected < max_drivers:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}",
                    ) as net_key:
                        for i in range(5):  # Increased from 2 to 5 network drivers
                            try:
                                subkey_name = winreg.EnumKey(net_key, i)
                                if subkey_name.isdigit() and drivers_collected < max_drivers:
                                    with winreg.OpenKey(net_key, subkey_name) as driver_key:
                                        try:
                                            driver_desc = winreg.QueryValueEx(driver_key, "DriverDesc")[0]
                                            try:
                                                driver_version = winreg.QueryValueEx(driver_key, "DriverVersion")[0]
                                            except FileNotFoundError:
                                                driver_version = "Unknown"

                                            driver_data = {
                                                "name": clean_string(driver_desc),
                                                "driver_version": driver_version,
                                                "source": "Registry-Network-Enhanced",
                                                "category": "network",
                                                "type": "essential",
                                            }
                                            driver_info["network_drivers"].append(driver_data)
                                            driver_info["driver_list"].append(driver_data)
                                            drivers_collected += 1
                                        except FileNotFoundError:
                                            continue
                            except Exception:
                                continue
                except Exception:
                    pass

            # 3. Audio drivers (NEW - previously missing)
            if drivers_collected < max_drivers:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SYSTEM\CurrentControlSet\Control\Class\{4d36e96c-e325-11ce-bfc1-08002be10318}",
                    ) as audio_key:
                        for i in range(4):  # Check audio drivers
                            try:
                                subkey_name = winreg.EnumKey(audio_key, i)
                                if subkey_name.isdigit() and drivers_collected < max_drivers:
                                    with winreg.OpenKey(audio_key, subkey_name) as driver_key:
                                        try:
                                            driver_desc = winreg.QueryValueEx(driver_key, "DriverDesc")[0]
                                            try:
                                                driver_version = winreg.QueryValueEx(driver_key, "DriverVersion")[0]
                                            except FileNotFoundError:
                                                driver_version = "Unknown"

                                            driver_data = {
                                                "name": clean_string(driver_desc),
                                                "driver_version": driver_version,
                                                "source": "Registry-Audio-Enhanced",
                                                "category": "audio",
                                                "type": "essential",
                                            }
                                            driver_info["audio_drivers"].append(driver_data)
                                            driver_info["driver_list"].append(driver_data)
                                            drivers_collected += 1
                                        except FileNotFoundError:
                                            continue
                            except Exception:
                                continue
                except Exception:
                    pass

            # 4. Storage drivers (NEW - previously missing)
            if drivers_collected < max_drivers:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SYSTEM\CurrentControlSet\Control\Class\{4d36e967-e325-11ce-bfc1-08002be10318}",
                    ) as storage_key:
                        for i in range(3):  # Check storage drivers
                            try:
                                subkey_name = winreg.EnumKey(storage_key, i)
                                if subkey_name.isdigit() and drivers_collected < max_drivers:
                                    with winreg.OpenKey(storage_key, subkey_name) as driver_key:
                                        try:
                                            driver_desc = winreg.QueryValueEx(driver_key, "DriverDesc")[0]
                                            try:
                                                driver_version = winreg.QueryValueEx(driver_key, "DriverVersion")[0]
                                            except FileNotFoundError:
                                                driver_version = "Unknown"

                                            driver_data = {
                                                "name": clean_string(driver_desc),
                                                "driver_version": driver_version,
                                                "source": "Registry-Storage-Enhanced",
                                                "category": "storage",
                                                "type": "essential",
                                            }
                                            driver_info["storage_drivers"].append(driver_data)
                                            driver_info["driver_list"].append(driver_data)
                                            drivers_collected += 1
                                        except FileNotFoundError:
                                            continue
                            except Exception:
                                continue
                except Exception:
                    pass

            # 5. USB drivers (NEW - for device connectivity issues)
            if drivers_collected < max_drivers:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SYSTEM\CurrentControlSet\Control\Class\{36fc9e60-c465-11cf-8056-444553540000}",
                    ) as usb_key:
                        for i in range(3):  # Check USB drivers
                            try:
                                subkey_name = winreg.EnumKey(usb_key, i)
                                if subkey_name.isdigit() and drivers_collected < max_drivers:
                                    with winreg.OpenKey(usb_key, subkey_name) as driver_key:
                                        try:
                                            driver_desc = winreg.QueryValueEx(driver_key, "DriverDesc")[0]
                                            try:
                                                driver_version = winreg.QueryValueEx(driver_key, "DriverVersion")[0]
                                            except FileNotFoundError:
                                                driver_version = "Unknown"

                                            driver_data = {
                                                "name": clean_string(driver_desc),
                                                "driver_version": driver_version,
                                                "source": "Registry-USB-Enhanced",
                                                "category": "usb",
                                                "type": "essential",
                                            }
                                            driver_info["driver_list"].append(driver_data)
                                            drivers_collected += 1
                                        except FileNotFoundError:
                                            continue
                            except Exception:
                                continue
                except Exception:
                    pass

            self.logger.info(
                f"Enhanced driver collection completed: {drivers_collected} drivers collected (target: 15+)"
            )

        except Exception as e:
            self.logger.warning(f"Enhanced driver collection failed: {e}")

    def _collect_essential_drivers_fallback(self, driver_info: Dict[str, Any]) -> None:
        """
        Collect essential drivers using limited WMI queries as fallback.

        Args:
            driver_info: Dictionary to populate with driver information
        """
        try:
            # Only try to get display drivers with very limited query
            if self.wmi_connection:
                try:
                    # Initialize COM for thread safety
                    import pythoncom

                    pythoncom.CoInitialize()
                except Exception:
                    pass

                # Quick GPU query only
                display_drivers = self._safe_wmi_query(
                    lambda: (
                        list(self.wmi_connection.Win32_VideoController())[:1] if self.wmi_connection else []
                    )  # Only first GPU
                )

                if display_drivers:
                    for gpu in display_drivers:
                        try:
                            driver_data = {
                                "name": clean_string(safe_get_attribute(gpu, "Name")),
                                "driver_version": safe_get_attribute(gpu, "DriverVersion"),
                                "source": "WMI-Essential-Fallback",
                                "category": "display",
                                "type": "fallback",
                            }

                            if driver_data["name"]:
                                driver_info["display_drivers"].append(driver_data)
                                driver_info["driver_list"].append(driver_data)
                                break  # Only one driver for speed

                        except Exception as e:
                            self.logger.debug(f"Failed to process fallback driver: {e}")
                            break

            self.logger.debug("Essential driver fallback completed")

        except Exception as e:
            self.logger.warning(f"Essential driver fallback failed: {e}")

    def _collect_drivers_registry(self, driver_info: Dict[str, Any]) -> None:
        """
        Collect basic driver information from Windows registry as final fallback.

        Args:
            driver_info: Dictionary to populate with driver information
        """
        try:
            import winreg

            # Check device manager registry entries
            registry_paths = [r"SYSTEM\CurrentControlSet\Control\Class", r"SYSTEM\CurrentControlSet\Enum"]

            driver_count = 0
            max_drivers = 15

            for registry_path in registry_paths:
                if driver_count >= max_drivers:
                    break

                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                        num_subkeys = winreg.QueryInfoKey(key)[0]

                        for i in range(min(num_subkeys, 30)):  # Check up to 30 subkeys
                            if driver_count >= max_drivers:
                                break

                            try:
                                subkey_name = winreg.EnumKey(key, i)

                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    driver_data = {
                                        "source": "Registry",
                                        "name": "Unknown Driver",
                                        "description": "Detected via registry",
                                    }

                                    try:
                                        desc = winreg.QueryValueEx(subkey, "DriverDesc")[0]
                                        driver_data["name"] = clean_string(desc)
                                        driver_data["description"] = clean_string(desc)
                                    except FileNotFoundError:
                                        try:
                                            desc = winreg.QueryValueEx(subkey, "Class")[0]
                                            driver_data["name"] = f"{desc} Driver"
                                            driver_data["description"] = f"Driver for {desc}"
                                        except FileNotFoundError:
                                            continue

                                    try:
                                        version = winreg.QueryValueEx(subkey, "DriverVersion")[0]
                                        driver_data["driver_version"] = version
                                    except FileNotFoundError:
                                        pass

                                    try:
                                        date = winreg.QueryValueEx(subkey, "DriverDate")[0]
                                        driver_data["driver_date"] = date
                                    except FileNotFoundError:
                                        pass

                                    if driver_data["name"] != "Unknown Driver":
                                        driver_info["driver_list"].append(driver_data)
                                        driver_count += 1

                            except Exception:
                                continue

                except Exception as e:
                    self.logger.debug(f"Registry driver detection failed for path {registry_path}: {e}")
                    continue

        except Exception as e:
            self.logger.warning(f"Registry driver fallback failed: {e}")

    def get_system_health(self) -> Dict[str, Any]:
        """
        Get system health metrics with actionable recommendations.

        Returns:
            Dictionary containing system health information and recommendations
        """
        health_info = {}

        try:
            with PerformanceTimer("System health collection"):
                # CPU usage
                cpu_usage = psutil.cpu_percent(interval=1)
                health_info["cpu_usage_percent"] = cpu_usage

                # Memory usage
                memory = psutil.virtual_memory()
                memory_usage = memory.percent
                health_info["memory_usage_percent"] = memory_usage

                # Disk usage for system drive
                disk_usage = "Unknown"
                try:
                    system_disk = psutil.disk_usage("C:")
                    disk_usage = round((system_disk.used / system_disk.total) * 100, 1)
                    health_info["system_disk_usage_percent"] = disk_usage
                except:
                    health_info["system_disk_usage_percent"] = "Unknown"

                # Boot time
                health_info["boot_time"] = datetime.fromtimestamp(psutil.boot_time()).isoformat()

                # Number of processes
                process_count = len(psutil.pids())
                health_info["process_count"] = process_count

                # Network connections count
                health_info["network_connections_count"] = len(psutil.net_connections())

                # Generate actionable health recommendations
                health_info["recommendations"] = self._generate_health_recommendations(
                    cpu_usage, memory_usage, disk_usage, process_count
                )

                # Health status summary
                health_info["overall_status"] = self._determine_overall_health_status(
                    cpu_usage, memory_usage, disk_usage
                )

        except Exception as e:
            self.logger.warning(f"Failed to collect system health: {e}")
            health_info["error"] = f"System health collection failed: {e}"

        return health_info

    def _generate_health_recommendations(
        self, cpu_usage: float, memory_usage: float, disk_usage: Any, process_count: int
    ) -> List[Dict[str, Any]]:
        """
        Generate actionable health recommendations based on system metrics.

        Args:
            cpu_usage: CPU usage percentage
            memory_usage: Memory usage percentage
            disk_usage: Disk usage percentage
            process_count: Number of running processes

        Returns:
            List of recommendation dictionaries
        """
        recommendations = []

        # High disk usage recommendations (85%+ usage)
        if isinstance(disk_usage, (int, float)) and disk_usage >= 85:
            priority = "CRITICAL" if disk_usage >= 95 else "HIGH"
            recommendations.append(
                {
                    "priority": priority,
                    "category": "Storage",
                    "issue": f"Disk usage {'critically ' if disk_usage >= 95 else ''}high at {disk_usage}%",
                    "recommendations": [
                        "Run Disk Cleanup (cleanmgr.exe) to remove temporary files",
                        "Uninstall unused programs from Control Panel > Programs",
                        "Move large files to external storage or cloud",
                        "Empty Recycle Bin and Downloads folder",
                        "Clear browser cache and temporary internet files",
                        "Use Storage Sense to automatically free up space",
                        "Check for large log files in C:\\Windows\\Logs",
                        "Delete old Windows Update files using Disk Cleanup",
                    ],
                    "risk": (
                        "System may become unstable or unable to save files"
                        if disk_usage >= 95
                        else "Reduced performance and storage space"
                    ),
                    "impact": "HIGH" if disk_usage >= 95 else "MEDIUM",
                }
            )

        # High memory usage recommendations (85%+ usage)
        if memory_usage >= 85:
            recommendations.append(
                {
                    "priority": "HIGH",
                    "category": "Memory",
                    "issue": f"Memory usage high at {memory_usage:.1f}%",
                    "recommendations": [
                        "Close unnecessary browser tabs and applications",
                        "Restart applications that may have memory leaks",
                        "Check Task Manager for high memory usage processes",
                        "Disable startup programs that aren't essential",
                        "Consider adding more RAM if consistently high",
                        "Use built-in Windows Memory Diagnostic",
                    ],
                    "risk": "System slowdown and potential application crashes",
                    "impact": "MEDIUM",
                }
            )

        # High CPU usage recommendations (80%+ usage)
        if cpu_usage >= 80:
            recommendations.append(
                {
                    "priority": "MEDIUM",
                    "category": "Performance",
                    "issue": f"CPU usage elevated at {cpu_usage:.1f}%",
                    "recommendations": [
                        "Check Task Manager for processes using high CPU",
                        "Close unnecessary applications and background processes",
                        "Run Windows Update to ensure latest optimizations",
                        "Check for malware using Windows Defender full scan",
                        "Adjust power plan to Balanced mode",
                        "Consider upgrading CPU for consistently high usage",
                    ],
                    "risk": "System responsiveness and performance degradation",
                    "impact": "MEDIUM",
                }
            )

        # High process count recommendations (500+ processes)
        if process_count >= 500:
            recommendations.append(
                {
                    "priority": "LOW",
                    "category": "System Management",
                    "issue": f"High number of running processes ({process_count})",
                    "recommendations": [
                        "Review and disable unnecessary startup programs",
                        "Uninstall bloatware and unused software",
                        "Use msconfig to manage startup items",
                        "Check for potentially unwanted programs (PUPs)",
                        "Consider a clean Windows installation if severely cluttered",
                    ],
                    "risk": "Increased system resource usage and slower startup",
                    "impact": "LOW",
                }
            )

        # Add positive recommendations if system is healthy
        if isinstance(disk_usage, (int, float)) and disk_usage < 80 and memory_usage < 75 and cpu_usage < 50:
            recommendations.append(
                {
                    "priority": "INFO",
                    "category": "Maintenance",
                    "issue": "System appears healthy",
                    "recommendations": [
                        "Continue regular Windows Updates",
                        "Run periodic disk cleanup and defragmentation",
                        "Keep drivers updated for optimal performance",
                        "Perform regular system backups",
                        "Monitor system performance monthly",
                    ],
                    "risk": "None - preventive maintenance",
                    "impact": "POSITIVE",
                }
            )

        return recommendations

    def _determine_overall_health_status(self, cpu_usage: float, memory_usage: float, disk_usage: Any) -> str:
        """
        Determine overall system health status with enhanced thresholds.

        Args:
            cpu_usage: CPU usage percentage
            memory_usage: Memory usage percentage
            disk_usage: Disk usage percentage

        Returns:
            Overall health status string
        """
        # Critical if disk usage is very high
        if isinstance(disk_usage, (int, float)) and disk_usage >= 95:
            return "CRITICAL"

        # Enhanced disk usage consideration - 85%+ is concerning
        disk_high = isinstance(disk_usage, (int, float)) and disk_usage >= 85

        # Poor if multiple high usage metrics or disk very high
        high_usage_count = 0
        if cpu_usage >= 80:
            high_usage_count += 1
        if memory_usage >= 85:
            high_usage_count += 1
        if isinstance(disk_usage, (int, float)) and disk_usage >= 90:
            high_usage_count += 1

        # Special case: If disk is 85%+ but under 90%, still concerning
        if disk_high and disk_usage < 90:
            if high_usage_count >= 1 or cpu_usage >= 70 or memory_usage >= 80:
                return "POOR"
            else:
                return "FAIR"

        if high_usage_count >= 2:
            return "POOR"
        elif high_usage_count == 1:
            return "FAIR"

        # Good if all metrics are reasonable
        if cpu_usage < 50 and memory_usage < 75 and isinstance(disk_usage, (int, float)) and disk_usage < 80:
            return "EXCELLENT"
        elif cpu_usage < 70 and memory_usage < 80 and isinstance(disk_usage, (int, float)) and disk_usage < 85:
            return "GOOD"
        else:
            return "FAIR"

    def get_network_information(self) -> Dict[str, Any]:
        """
        Get network information.

        Returns:
            Dictionary containing network information
        """
        network_info = {}

        try:
            with PerformanceTimer("Network information collection"):
                # Network interfaces
                network_info["interfaces"] = {}
                for interface, addrs in psutil.net_if_addrs().items():
                    interface_info = []
                    for addr in addrs:
                        interface_info.append(
                            {
                                "family": str(addr.family),
                                "address": addr.address,
                                "netmask": addr.netmask,
                                "broadcast": addr.broadcast,
                            }
                        )
                    network_info["interfaces"][interface] = interface_info

                # Network statistics
                net_io = psutil.net_io_counters()
                network_info["statistics"] = {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_sent_formatted": format_bytes(net_io.bytes_sent),
                    "bytes_received": net_io.bytes_recv,
                    "bytes_received_formatted": format_bytes(net_io.bytes_recv),
                    "packets_sent": net_io.packets_sent,
                    "packets_received": net_io.packets_recv,
                }

        except Exception as e:
            self.logger.warning(f"Failed to collect network information: {e}")
            network_info["error"] = f"Network information collection failed: {e}"

        return network_info

    def format_specs_output(self, specs_data: Dict[str, Any]) -> str:
        """
        Format system specifications for display and API consumption.

        Args:
            specs_data: System specifications dictionary

        Returns:
            Formatted string representation
        """
        try:
            import json

            return json.dumps(specs_data, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            self.logger.error(f"Failed to format specs output: {e}")
            return f"Error formatting output: {e}"

    def validate_collected_data(self, specs_data: Dict[str, Any]) -> bool:
        """
        Validate that all critical data was collected successfully.

        Args:
            specs_data: System specifications dictionary

        Returns:
            True if validation passes, False otherwise
        """
        try:
            validate_json_structure(specs_data, REQUIRED_SYSTEM_KEYS)

            # Check for critical errors in data
            error_count = 0
            for key, value in specs_data.items():
                if isinstance(value, dict) and "error" in value:
                    error_count += 1
                    self.logger.warning(f"Error in {key}: {value['error']}")

            # Allow some errors but not too many
            if error_count > len(REQUIRED_SYSTEM_KEYS) // 2:
                self.logger.error(f"Too many collection errors: {error_count}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Data validation failed: {e}")
            return False

    def export_to_json(self, specs_data: Dict[str, Any], file_path: str) -> bool:
        """
        Export specifications to JSON file.

        Args:
            specs_data: System specifications dictionary
            file_path: Path to save JSON file

        Returns:
            True if successful, False otherwise
        """
        return safe_json_export(specs_data, file_path)

    def get_summary(self, specs_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Get a summary of key system information.

        Args:
            specs_data: System specifications dictionary

        Returns:
            Dictionary containing summary information
        """
        summary = {}

        try:
            # OS Summary
            os_info = specs_data.get("os_information", {})
            summary["operating_system"] = f"{os_info.get('system')} {os_info.get('release')}"

            # Hardware Summary
            hardware = specs_data.get("hardware_specs", {})
            cpu_info = hardware.get("cpu", {})
            memory_info = hardware.get("memory", {})

            summary["processor"] = cpu_info.get("name", "Unknown")
            summary["memory"] = memory_info.get("total_formatted", "Unknown")

            # System Health Summary
            health = specs_data.get("system_health", {})
            summary["cpu_usage"] = f"{health.get('cpu_usage_percent', 'Unknown')}%"
            summary["memory_usage"] = f"{health.get('memory_usage_percent', 'Unknown')}%"

            # Collection Info
            summary["collection_time"] = specs_data.get("collection_timestamp", "Unknown")

        except Exception as e:
            self.logger.warning(f"Failed to generate summary: {e}")
            summary["error"] = f"Summary generation failed: {e}"

        return summary

    def cleanup_resources(self) -> None:
        """
        Clean up system resources including WMI connections and COM initialization.
        Should be called before application shutdown.
        """
        try:
            self.logger.debug("Cleaning up SystemSpecsCollector resources...")

            # Clean up WMI connection
            if hasattr(self, "wmi_connection") and self.wmi_connection:
                try:
                    self.wmi_connection = None
                    self.logger.debug("WMI connection cleaned up")
                except Exception as e:
                    self.logger.warning(f"Error cleaning up WMI connection: {e}")

            # Clean up COM for this thread
            if pythoncom:
                try:
                    pythoncom.CoUninitialize()
                    self.logger.debug("COM uninitialized")
                except Exception as e:
                    self.logger.debug(f"COM cleanup note: {e}")

        except Exception as e:
            self.logger.warning(f"Error during resource cleanup: {e}")
