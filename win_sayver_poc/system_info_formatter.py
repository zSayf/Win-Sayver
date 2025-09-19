#!/usr/bin/env python3
"""
System Information Formatter
===========================

Utility class to convert raw system specification JSON data into
human-readable, organized format suitable for modern card-based display.

Handles data transformation, formatting, and categorization for the
responsive System Info interface.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union


class SystemInfoFormatter:
    """
    Formats raw system specifications into human-readable card data.

    Transforms JSON system data into organized categories with proper
    formatting, units, and visual elements for modern UI display.
    """

    def __init__(self):
        """Initialize the formatter."""
        self.logger = logging.getLogger(__name__)

    def format_system_data(self, system_specs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert raw system specs to formatted card data.

        Args:
            system_specs: Raw system specification dictionary

        Returns:
            List of card data dictionaries for UI display
        """
        try:
            # Validate input
            if not system_specs or not isinstance(system_specs, dict):
                self.logger.warning("Invalid or empty system specs provided")
                return self._create_no_data_card()

            cards = []

            # Computer Overview Card
            try:
                overview_card = self._create_overview_card(system_specs)
                if overview_card:
                    cards.append(overview_card)
            except Exception as e:
                self.logger.error(f"Failed to create overview card: {e}")

            # Processor Information Card
            try:
                processor_card = self._create_processor_card(system_specs)
                if processor_card:
                    cards.append(processor_card)
            except Exception as e:
                self.logger.error(f"Failed to create processor card: {e}")

            # Memory Information Card
            try:
                memory_card = self._create_memory_card(system_specs)
                if memory_card:
                    cards.append(memory_card)
            except Exception as e:
                self.logger.error(f"Failed to create memory card: {e}")

            # Storage Information Card
            try:
                storage_card = self._create_storage_card(system_specs)
                if storage_card:
                    cards.append(storage_card)
            except Exception as e:
                self.logger.error(f"Failed to create storage card: {e}")

            # Network Information Card
            try:
                network_card = self._create_network_card(system_specs)
                if network_card:
                    cards.append(network_card)
            except Exception as e:
                self.logger.error(f"Failed to create network card: {e}")

            # Graphics Information Card
            try:
                graphics_card = self._create_graphics_card(system_specs)
                if graphics_card:
                    cards.append(graphics_card)
            except Exception as e:
                self.logger.error(f"Failed to create graphics card: {e}")

            # System Performance Card
            try:
                performance_card = self._create_performance_card(system_specs)
                if performance_card:
                    cards.append(performance_card)
            except Exception as e:
                self.logger.error(f"Failed to create performance card: {e}")

            # Ensure we have at least one card
            if not cards:
                self.logger.warning("No cards were created from system specs")
                return self._create_no_data_card()

            self.logger.info(f"Formatted system data into {len(cards)} cards")
            return cards

        except Exception as e:
            self.logger.error(f"Failed to format system data: {e}")
            return self._create_error_card(str(e))

    def _create_overview_card(self, specs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create computer overview card."""
        try:
            if not specs or not isinstance(specs, dict):
                return None

            os_info = specs.get("os_information", {})
            hardware_specs = specs.get("hardware_specs", {})

            # Ensure we have dict objects
            if not isinstance(os_info, dict):
                os_info = {}
            if not isinstance(hardware_specs, dict):
                hardware_specs = {}

            items = []

            # Computer name
            computer_name = None
            try:
                computer_name = os_info.get("node") or hardware_specs.get("computer_name")
                if computer_name and isinstance(computer_name, str):
                    items.append({"label": "Computer Name", "value": computer_name, "type": "text"})
            except Exception as e:
                self.logger.debug(f"Failed to get computer name: {e}")

            # Operating System
            try:
                system = os_info.get("system")
                release = os_info.get("release")
                version = os_info.get("version")

                if system and isinstance(system, str):
                    os_display = f"{system} {release}" if release and isinstance(release, str) else system
                    if version and isinstance(version, str):
                        os_display += f" (Build {version})"
                    items.append({"label": "Operating System", "value": os_display, "type": "text"})
            except Exception as e:
                self.logger.debug(f"Failed to get OS info: {e}")

            # Architecture
            try:
                architecture = os_info.get("architecture") or os_info.get("machine")
                if architecture and isinstance(architecture, str):
                    items.append({"label": "Architecture", "value": architecture, "type": "text"})
            except Exception as e:
                self.logger.debug(f"Failed to get architecture: {e}")

            # Platform
            try:
                platform = os_info.get("platform")
                if platform and isinstance(platform, str):
                    items.append({"label": "Platform", "value": platform, "type": "text"})
            except Exception as e:
                self.logger.debug(f"Failed to get platform: {e}")

            # Python version (for debugging)
            try:
                python_version = os_info.get("python_version")
                if python_version and isinstance(python_version, str):
                    items.append({"label": "Python Version", "value": python_version, "type": "text"})
            except Exception as e:
                self.logger.debug(f"Failed to get Python version: {e}")

            # Collection timestamp
            try:
                timestamp = specs.get("collection_timestamp")
                if timestamp and isinstance(timestamp, str):
                    formatted_time = self._format_datetime(timestamp)
                    items.append({"label": "Last Updated", "value": formatted_time, "type": "text"})
            except Exception as e:
                self.logger.debug(f"Failed to get timestamp: {e}")

            if not items:
                return None

            return {"title": "💻 Computer Overview", "category": "overview", "color": "#2196F3", "items": items}  # Blue

        except Exception as e:
            self.logger.warning(f"Failed to create overview card: {e}")
            return None

    def _create_processor_card(self, specs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create processor information card."""
        try:
            hardware_specs = specs.get("hardware_specs", {})
            os_info = specs.get("os_information", {})

            items = []

            # Processor name - prioritize hardware specs CPU name over OS processor identifier
            cpu_info = hardware_specs.get("cpu", {})
            processor_name = cpu_info.get("name")  # Real CPU name like "AMD Ryzen 5 5600X 6-Core Processor"

            # Fallback to OS processor info if hardware specs unavailable
            if not processor_name:
                processor_name = os_info.get("processor")

            if processor_name:
                items.append({"label": "Processor", "value": processor_name, "type": "text"})

            # Machine architecture
            machine = os_info.get("machine")
            if machine:
                items.append({"label": "Architecture", "value": machine, "type": "text"})

            # Platform information
            platform = os_info.get("platform")
            if platform:
                items.append({"label": "Platform Details", "value": platform, "type": "text"})

            # Try to get CPU info from hardware specs
            cpu_info = hardware_specs.get("cpu", {})
            if cpu_info:
                # Physical cores
                physical_cores = cpu_info.get("physical_cores")
                if physical_cores:
                    items.append({"label": "Physical Cores", "value": str(physical_cores), "type": "text"})

                # Logical cores
                logical_cores = cpu_info.get("logical_cores")
                if logical_cores:
                    items.append({"label": "Logical Cores", "value": str(logical_cores), "type": "text"})

                # CPU frequency
                frequency = cpu_info.get("frequency")
                if frequency:
                    freq_display = (
                        self.format_frequency(frequency) if isinstance(frequency, (int, float)) else str(frequency)
                    )
                    items.append({"label": "Base Frequency", "value": freq_display, "type": "text"})

            # System health info for CPU usage/temperature
            system_health = specs.get("system_health", {})
            cpu_info_health = system_health.get("cpu", {})

            # CPU usage
            cpu_usage = cpu_info_health.get("usage_percent")
            if cpu_usage is not None:
                items.append(
                    {
                        "label": "CPU Usage",
                        "value": f"{cpu_usage:.1f}%",
                        "type": "progress",
                        "progress": cpu_usage,
                        "color": self._get_usage_color(cpu_usage),
                    }
                )

            # CPU temperature
            cpu_temp = cpu_info_health.get("temperature")
            if cpu_temp:
                temp_status = "normal" if cpu_temp < 70 else "warning" if cpu_temp < 85 else "critical"
                items.append(
                    {"label": "Temperature", "value": f"{cpu_temp}°C", "type": "status", "status": temp_status}
                )

            if not items:
                return None

            return {"title": "🔧 Processor", "category": "processor", "color": "#FF9800", "items": items}  # Orange

        except Exception as e:
            self.logger.warning(f"Failed to create processor card: {e}")
            return None

    def _create_memory_card(self, specs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create memory information card."""
        try:
            if not specs or not isinstance(specs, dict):
                return None

            hardware_specs = specs.get("hardware_specs", {})
            system_health = specs.get("system_health", {})

            # Ensure we have dict objects
            if not isinstance(hardware_specs, dict):
                hardware_specs = {}
            if not isinstance(system_health, dict):
                system_health = {}

            items = []

            # Memory info from hardware specs
            memory_info = hardware_specs.get("memory", {})
            if not isinstance(memory_info, dict):
                memory_info = {}

            # Total memory
            try:
                total_memory = memory_info.get("total")
                if total_memory and isinstance(total_memory, (int, float)) and total_memory > 0:
                    total_gb = total_memory / (1024**3)
                    items.append({"label": "Total Memory", "value": f"{total_gb:.1f} GB", "type": "text"})

                    # Available memory from system health
                    memory_health = system_health.get("memory", {})
                    if not isinstance(memory_health, dict):
                        memory_health = {}

                    available = memory_health.get("available")

                    if available and isinstance(available, (int, float)) and available > 0:
                        available_gb = available / (1024**3)
                        used_gb = max(0, total_gb - available_gb)  # Ensure non-negative
                        usage_percent = min(100, max(0, (used_gb / total_gb) * 100))  # Clamp to 0-100

                        items.append({"label": "Available", "value": f"{available_gb:.1f} GB", "type": "text"})
                        items.append(
                            {
                                "label": "Memory Usage",
                                "value": f"{usage_percent:.1f}% ({used_gb:.1f} GB used)",
                                "type": "progress",
                                "progress": usage_percent,
                                "color": self._get_usage_color(usage_percent),
                            }
                        )

                    # Alternative: memory percentage
                    elif not available:
                        memory_percent = memory_health.get("percent")
                        if memory_percent and isinstance(memory_percent, (int, float)):
                            memory_percent = min(100, max(0, memory_percent))  # Clamp to 0-100
                            items.append(
                                {
                                    "label": "Memory Usage",
                                    "value": f"{memory_percent:.1f}%",
                                    "type": "progress",
                                    "progress": memory_percent,
                                    "color": self._get_usage_color(memory_percent),
                                }
                            )
            except Exception as e:
                self.logger.debug(f"Failed to process memory totals: {e}")

            # Memory modules (if available)
            try:
                modules = memory_info.get("modules", [])
                if modules and isinstance(modules, list) and len(modules) > 0:
                    module_count = len(modules)
                    items.append({"label": "Memory Modules", "value": f"{module_count} installed", "type": "text"})

                    # Show first module details as example
                    first_module = modules[0]
                    if isinstance(first_module, dict):
                        size = first_module.get("size")
                        speed = first_module.get("speed")
                        if size and speed:
                            try:
                                size_display = self.format_bytes(size) if isinstance(size, (int, float)) else str(size)
                                speed_display = str(speed)
                                items.append(
                                    {
                                        "label": "Module Type",
                                        "value": f"{size_display} @ {speed_display}MHz",
                                        "type": "text",
                                    }
                                )
                            except Exception as e:
                                self.logger.debug(f"Failed to format module details: {e}")
            except Exception as e:
                self.logger.debug(f"Failed to process memory modules: {e}")

            if not items:
                return None

            return {"title": "💾 Memory", "category": "memory", "color": "#4CAF50", "items": items}  # Green

        except Exception as e:
            self.logger.warning(f"Failed to create memory card: {e}")
            return None

    def _create_storage_card(self, specs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create storage information card with enhanced physical drive and partition display."""
        try:
            hardware_specs = specs.get("hardware_specs", {})
            storage_info = hardware_specs.get("storage", {})

            items = []

            # Handle new comprehensive storage data structure
            if isinstance(storage_info, dict) and "physical_drives" in storage_info:
                # New comprehensive storage format
                physical_drives = storage_info.get("physical_drives", [])
                partitions = storage_info.get("partitions", [])
                summary = storage_info.get("summary", {})

                if physical_drives:
                    # Physical drives count
                    drive_count = len(physical_drives)
                    items.append({"label": "Physical Drives", "value": str(drive_count), "type": "text"})

                    # Drive types summary
                    drive_types = summary.get("drive_types", {})
                    if drive_types:
                        type_parts = []
                        for drive_type, count in drive_types.items():
                            if drive_type != "Unknown" and count > 0:
                                type_parts.append(f"{count} {drive_type}")

                        if type_parts:
                            storage_type_text = ", ".join(type_parts)
                            items.append({"label": "Storage Types", "value": storage_type_text, "type": "text"})

                    # Individual drive details (show up to 3 drives)
                    for i, drive in enumerate(physical_drives[:3], 1):
                        drive_label = f"Drive {i}" if len(physical_drives) > 1 else "Primary Drive"
                        model = drive.get("model", "Unknown")
                        size_formatted = drive.get("size_formatted", "Unknown")
                        drive_type = drive.get("drive_type", "Unknown")

                        drive_info = f"{model} ({size_formatted}, {drive_type})"
                        items.append({"label": drive_label, "value": drive_info, "type": "text"})

                    # Show additional drives count if more than 3
                    if len(physical_drives) > 3:
                        additional_count = len(physical_drives) - 3
                        items.append(
                            {"label": "Additional Drives", "value": f"+{additional_count} more", "type": "text"}
                        )

                    # System drive usage from partitions
                    system_drive = summary.get("system_drive")
                    if system_drive:
                        usage_percent = system_drive.get("usage_percent", 0)
                        drive_letter = system_drive.get("drive_letter", "C:")
                        items.append(
                            {
                                "label": f"System Drive ({drive_letter}) Usage",
                                "value": f"{usage_percent:.1f}%",
                                "type": "progress",
                                "progress": usage_percent,
                                "color": self._get_usage_color(usage_percent),
                            }
                        )

                elif partitions:
                    # Fallback to partition-only display
                    items.append({"label": "Logical Drives", "value": str(len(partitions)), "type": "text"})

                    # Find system drive
                    for partition in partitions:
                        if partition.get("drive_letter", "").upper().startswith("C"):
                            usage_percent = partition.get("usage_percent", 0)
                            total_formatted = partition.get("total_formatted", "Unknown")
                            items.append({"label": "System Drive (C:)", "value": total_formatted, "type": "text"})
                            items.append(
                                {
                                    "label": "System Drive Usage",
                                    "value": f"{usage_percent:.1f}%",
                                    "type": "progress",
                                    "progress": usage_percent,
                                    "color": self._get_usage_color(usage_percent),
                                }
                            )
                            break

            # Handle legacy storage data structures for backward compatibility
            elif isinstance(storage_info, list):
                # Check if this is physical disk data (has 'model' field) or logical drives (has 'device' field)
                if storage_info and "model" in storage_info[0]:
                    # Legacy physical disk information
                    disks = storage_info
                    physical_disk_count = len(disks)
                    items.append({"label": "Physical Disks", "value": str(physical_disk_count), "type": "text"})

                    # Analyze and display individual physical disks
                    ssd_count = 0
                    hdd_count = 0
                    nvme_count = 0
                    disk_details = []

                    for disk in disks:
                        if isinstance(disk, dict):
                            drive_type = disk.get("drive_type", "Unknown")
                            model = disk.get("model", "Unknown")
                            size_formatted = disk.get("size_formatted", "Unknown")

                            # Count drive types
                            if "nvme" in drive_type.lower():
                                nvme_count += 1
                            elif "ssd" in drive_type.lower():
                                ssd_count += 1
                            elif "hdd" in drive_type.lower():
                                hdd_count += 1

                            # Store disk details for individual display
                            disk_details.append({"model": model, "size": size_formatted, "type": drive_type})

                    # Display storage type summary
                    type_parts = []
                    if nvme_count > 0:
                        type_parts.append(f"{nvme_count} NVMe SSD")
                    if ssd_count > 0:
                        type_parts.append(f"{ssd_count} SSD")
                    if hdd_count > 0:
                        type_parts.append(f"{hdd_count} HDD")

                    if type_parts:
                        storage_type_text = ", ".join(type_parts)
                        items.append({"label": "Storage Types", "value": storage_type_text, "type": "text"})

                    # Display individual disk information
                    for i, disk_detail in enumerate(disk_details[:3], 1):  # Show up to 3 disks
                        disk_label = f"Drive {i}" if len(disk_details) > 1 else "Primary Drive"
                        disk_info = f"{disk_detail['model']} ({disk_detail['size']}, {disk_detail['type']})"
                        items.append({"label": disk_label, "value": disk_info, "type": "text"})

                    # If more than 3 disks, show count of additional ones
                    if len(disk_details) > 3:
                        additional_count = len(disk_details) - 3
                        items.append(
                            {"label": "Additional Drives", "value": f"+{additional_count} more", "type": "text"}
                        )

                else:
                    # Legacy logical drive information (fallback)
                    disks = storage_info
                    if disks:
                        disk_count = len(disks)
                        items.append({"label": "Logical Drives", "value": str(disk_count), "type": "text"})

                        # Show primary drive details
                        primary_drive = disks[0] if isinstance(disks[0], dict) else {}
                        device = primary_drive.get("device", "Unknown")
                        total_formatted = primary_drive.get("total_formatted", "Unknown")

                        if device and total_formatted:
                            items.append(
                                {"label": "Primary Drive", "value": f"{device} ({total_formatted})", "type": "text"}
                            )

            elif isinstance(storage_info, dict):
                # Legacy dict structure (fallback)
                drives = storage_info.get("drives", [])
                if drives and isinstance(drives, list):
                    # Count drives by type
                    ssd_count = sum(1 for d in drives if d.get("is_ssd", False))
                    hdd_count = len(drives) - ssd_count

                    if ssd_count > 0 and hdd_count > 0:
                        items.append(
                            {"label": "Storage Types", "value": f"{ssd_count} SSD, {hdd_count} HDD", "type": "text"}
                        )
                    elif ssd_count > 0:
                        items.append({"label": "Storage Type", "value": f"{ssd_count} SSD", "type": "text"})
                    elif hdd_count > 0:
                        items.append({"label": "Storage Type", "value": f"{hdd_count} HDD", "type": "text"})

                    # Show primary drive details
                    primary_drive = drives[0] if drives else None
                    if primary_drive and isinstance(primary_drive, dict):
                        total_size = primary_drive.get("total_size")
                        free_space = primary_drive.get("free_space")
                        drive_letter = primary_drive.get("drive_letter", "C:")

                        if total_size and isinstance(total_size, (int, float)):
                            total_gb = total_size / (1024**3)
                            items.append(
                                {"label": f"Drive {drive_letter} Total", "value": f"{total_gb:.1f} GB", "type": "text"}
                            )

                            if free_space and isinstance(free_space, (int, float)):
                                free_gb = free_space / (1024**3)
                                used_gb = max(0, total_gb - free_gb)
                                usage_percent = min(100, max(0, (used_gb / total_gb) * 100))

                                items.append(
                                    {
                                        "label": f"Drive {drive_letter} Usage",
                                        "value": f"{usage_percent:.1f}% ({used_gb:.1f} GB used)",
                                        "type": "progress",
                                        "progress": usage_percent,
                                        "color": self._get_usage_color(usage_percent),
                                    }
                                )

            # Check system health for disk usage (fallback)
            if not any(item.get("type") == "progress" for item in items):
                system_health = specs.get("system_health", {})
                if isinstance(system_health, dict):
                    disk_usage = system_health.get("system_disk_usage_percent")
                    if disk_usage and isinstance(disk_usage, (int, float)):
                        items.append(
                            {
                                "label": "System Disk Usage",
                                "value": f"{disk_usage:.1f}%",
                                "type": "progress",
                                "progress": disk_usage,
                                "color": self._get_usage_color(disk_usage),
                            }
                        )

            if not items:
                return None

            return {"title": "💽 Storage", "category": "storage", "color": "#9C27B0", "items": items}  # Purple

        except Exception as e:
            self.logger.warning(f"Failed to create storage card: {e}")
            return None

    def _create_network_card(self, specs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create network information card."""
        try:
            network_info = specs.get("network_information", {})

            if not network_info or not isinstance(network_info, dict):
                return None

            items = []

            # Network interfaces (from current data structure)
            interfaces = network_info.get("interfaces", {})
            if interfaces and isinstance(interfaces, dict):
                interface_count = len(interfaces)
                items.append({"label": "Network Interfaces", "value": str(interface_count), "type": "text"})

                # Find primary interface (first non-loopback, active interface)
                primary_interface = None
                primary_name = None

                for name, interface_data in interfaces.items():
                    if isinstance(interface_data, dict):
                        # Skip loopback and virtual interfaces
                        if "loopback" not in name.lower() and "virtual" not in name.lower():
                            # Prefer Ethernet over others
                            if "ethernet" in name.lower() or not primary_interface:
                                primary_interface = interface_data
                                primary_name = name
                                break

                if primary_interface and primary_name:
                    # Connection type
                    if "ethernet" in primary_name.lower():
                        connection_type = "Ethernet"
                    elif "wi-fi" in primary_name.lower() or "wifi" in primary_name.lower():
                        connection_type = "Wi-Fi"
                    else:
                        connection_type = "Network"

                    items.append({"label": "Primary Connection", "value": connection_type, "type": "text"})

                    # IP addresses
                    ip_addresses = primary_interface.get("ip_addresses", [])
                    if ip_addresses and isinstance(ip_addresses, list):
                        # Find first non-local IP
                        primary_ip = None
                        for ip in ip_addresses:
                            if (
                                isinstance(ip, str)
                                and not ip.startswith("127.")
                                and not ip.startswith("169.254.")
                                and ip != "0.0.0.0"
                            ):
                                primary_ip = ip
                                break

                        if primary_ip:
                            items.append({"label": "IP Address", "value": primary_ip, "type": "text"})

                    # Interface status (assume active if IP addresses exist)
                    is_connected = bool(ip_addresses and len(ip_addresses) > 0)
                    items.append(
                        {
                            "label": "Connection Status",
                            "value": "Connected" if is_connected else "Disconnected",
                            "type": "status",
                            "status": "normal" if is_connected else "critical",
                        }
                    )

            # Network adapters (legacy structure)
            adapters = network_info.get("adapters", [])
            if adapters and not interfaces:
                active_adapters = [a for a in adapters if a.get("is_active", True) or a.get("status") == "active"]
                items.append(
                    {
                        "label": "Network Adapters",
                        "value": f"{len(active_adapters)} active of {len(adapters)}",
                        "type": "text",
                    }
                )

                # Show primary adapter details
                primary_adapter = None
                for adapter in active_adapters:
                    if (
                        adapter.get("is_primary")
                        or "Ethernet" in adapter.get("name", "")
                        or "Wi-Fi" in adapter.get("name", "")
                    ):
                        primary_adapter = adapter
                        break

                if not primary_adapter and active_adapters:
                    primary_adapter = active_adapters[0]

                if primary_adapter:
                    adapter_name = primary_adapter.get("name", "Unknown")
                    adapter_type = (
                        "Ethernet" if "Ethernet" in adapter_name else "Wi-Fi" if "Wi-Fi" in adapter_name else "Network"
                    )
                    items.append({"label": "Primary Connection", "value": adapter_type, "type": "text"})

                    # IP addresses
                    ip_addresses = primary_adapter.get("ip_addresses", [])
                    if ip_addresses:
                        # Get the first non-local IP
                        primary_ip = None
                        for ip in ip_addresses:
                            if not ip.startswith("127.") and not ip.startswith("169.254."):
                                primary_ip = ip
                                break

                        if primary_ip:
                            items.append({"label": "IP Address", "value": primary_ip, "type": "text"})

                    # Connection status
                    status = primary_adapter.get("status", "unknown")
                    is_connected = status == "active" or primary_adapter.get("is_active", False)
                    items.append(
                        {
                            "label": "Connection Status",
                            "value": "Connected" if is_connected else "Disconnected",
                            "type": "status",
                            "status": "normal" if is_connected else "critical",
                        }
                    )

            # Network statistics
            statistics = network_info.get("statistics", {})
            if statistics and isinstance(statistics, dict):
                bytes_sent = statistics.get("bytes_sent_formatted")
                bytes_received = statistics.get("bytes_received_formatted")

                if bytes_sent:
                    items.append({"label": "Data Sent", "value": str(bytes_sent), "type": "text"})

                if bytes_received:
                    items.append({"label": "Data Received", "value": str(bytes_received), "type": "text"})

            # Internet connectivity check (if available)
            connectivity = network_info.get("internet_connectivity")
            if connectivity is not None:
                items.append(
                    {
                        "label": "Internet Access",
                        "value": "Available" if connectivity else "No Internet",
                        "type": "status",
                        "status": "normal" if connectivity else "warning",
                    }
                )

            # Default gateway (if available)
            gateway = network_info.get("default_gateway")
            if gateway:
                items.append({"label": "Default Gateway", "value": gateway, "type": "text"})

            if not items:
                return None

            return {"title": "🌐 Network", "category": "network", "color": "#00BCD4", "items": items}  # Cyan

        except Exception as e:
            self.logger.warning(f"Failed to create network card: {e}")
            return None

    def _create_graphics_card(self, specs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create graphics information card."""
        try:
            hardware_specs = specs.get("hardware_specs", {})
            gpu_info = hardware_specs.get("gpu", {})

            # Also check for legacy gpu_info key
            if not gpu_info:
                gpu_info = specs.get("gpu_info", {})

            items = []

            # Handle different GPU data structures
            gpus = []
            if isinstance(gpu_info, list):
                # GPU is a list of GPU objects
                gpus = gpu_info
            elif isinstance(gpu_info, dict):
                if "gpus" in gpu_info and isinstance(gpu_info["gpus"], list):
                    gpus = gpu_info["gpus"]
                elif "name" in gpu_info or "gpu_name" in gpu_info or "caption" in gpu_info:
                    # Single GPU structure
                    gpus = [gpu_info]

            if gpus and len(gpus) > 0:
                primary_gpu = gpus[0] if isinstance(gpus[0], dict) else {}

                # GPU name
                gpu_name_fields = ["name", "gpu_name", "caption", "description"]
                gpu_name = None
                for field in gpu_name_fields:
                    name = primary_gpu.get(field)
                    if name and isinstance(name, str) and name.strip():
                        gpu_name = name.strip()
                        break

                if gpu_name:
                    items.append({"label": "Graphics Card", "value": gpu_name, "type": "text"})

                # VRAM/Memory
                memory_fields = [
                    "memory_total",
                    "vram",
                    "adapter_ram",
                    "memory",
                    "dedicated_video_memory",
                    "video_memory_size",
                ]

                memory = None
                for field in memory_fields:
                    mem = primary_gpu.get(field)
                    if mem and isinstance(mem, (int, float)) and mem > 0:
                        memory = mem
                        break

                if memory:
                    if memory > 1024**3:  # Likely in bytes
                        memory_gb = memory / (1024**3)
                        items.append({"label": "Video Memory", "value": f"{memory_gb:.1f} GB", "type": "text"})
                    elif memory > 1024:  # Likely in MB
                        if memory >= 1024:
                            memory_gb = memory / 1024
                            items.append({"label": "Video Memory", "value": f"{memory_gb:.1f} GB", "type": "text"})
                        else:
                            items.append({"label": "Video Memory", "value": f"{memory:.0f} MB", "type": "text"})
                    else:
                        # Small number, likely already in GB
                        items.append({"label": "Video Memory", "value": f"{memory:.1f} GB", "type": "text"})

                # Driver version
                driver_fields = ["driver_version", "driver_date", "inf_filename"]
                driver_info = None
                for field in driver_fields:
                    driver = primary_gpu.get(field)
                    if driver and isinstance(driver, str) and driver.strip():
                        driver_info = driver.strip()
                        break

                if driver_info:
                    items.append({"label": "Driver Version", "value": driver_info, "type": "text"})

                # GPU utilization (if available)
                usage_fields = ["utilization", "load", "usage_percent", "current_usage"]
                gpu_usage = None
                for field in usage_fields:
                    usage = primary_gpu.get(field)
                    if usage is not None and isinstance(usage, (int, float)):
                        gpu_usage = usage
                        break

                if gpu_usage is not None:
                    items.append(
                        {
                            "label": "GPU Usage",
                            "value": f"{gpu_usage:.1f}%",
                            "type": "progress",
                            "progress": gpu_usage,
                            "color": self._get_usage_color(gpu_usage),
                        }
                    )

                # Multiple GPUs
                if len(gpus) > 1:
                    items.append({"label": "Total GPUs", "value": str(len(gpus)), "type": "text"})

            # Display information (if available)
            display_info = specs.get("display_info", {})
            if isinstance(display_info, dict):
                displays = display_info.get("displays", [])
                if displays and isinstance(displays, list):
                    active_displays = [
                        d for d in displays if isinstance(d, dict) and (d.get("is_primary") or d.get("is_active", True))
                    ]
                    if active_displays:
                        items.append({"label": "Active Displays", "value": str(len(active_displays)), "type": "text"})

                        # Primary display resolution
                        primary_display = next((d for d in active_displays if d.get("is_primary")), None)
                        if not primary_display and active_displays:
                            primary_display = active_displays[0]

                        if primary_display and isinstance(primary_display, dict):
                            resolution = primary_display.get("resolution")
                            if resolution and isinstance(resolution, dict):
                                width = resolution.get("width")
                                height = resolution.get("height")
                                if (
                                    width
                                    and height
                                    and isinstance(width, (int, float))
                                    and isinstance(height, (int, float))
                                ):
                                    items.append(
                                        {
                                            "label": "Primary Resolution",
                                            "value": f"{int(width)} × {int(height)}",
                                            "type": "text",
                                        }
                                    )

            if not items:
                return None

            return {"title": "🎮 Graphics", "category": "graphics", "color": "#E91E63", "items": items}  # Pink

        except Exception as e:
            self.logger.warning(f"Failed to create graphics card: {e}")
            return None

    def _create_performance_card(self, specs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create system performance card."""
        try:
            # Check system_health first (primary location)
            system_health = specs.get("system_health", {})
            # Fallback to legacy performance key
            performance = specs.get("performance", {})
            # Also check system_info for boot time
            system_info = specs.get("system_info", {})

            if not isinstance(system_health, dict):
                system_health = {}
            if not isinstance(performance, dict):
                performance = {}
            if not isinstance(system_info, dict):
                system_info = {}

            items = []

            # System uptime
            boot_time = system_health.get("boot_time") or system_info.get("boot_time")
            if boot_time and isinstance(boot_time, str):
                uptime = self._calculate_uptime(boot_time)
                items.append({"label": "System Uptime", "value": uptime, "type": "text"})

            # Running processes count
            process_count = system_health.get("process_count") or performance.get("process_count")
            if process_count and isinstance(process_count, (int, float)):
                items.append({"label": "Running Processes", "value": str(int(process_count)), "type": "text"})

            # Network connections
            network_connections = system_health.get("network_connections_count")
            if network_connections and isinstance(network_connections, (int, float)):
                items.append({"label": "Network Connections", "value": str(int(network_connections)), "type": "text"})

            # Overall system status
            overall_status = system_health.get("overall_status")
            if overall_status and isinstance(overall_status, str):
                status_color = {
                    "good": "normal",
                    "excellent": "normal",
                    "warning": "warning",
                    "critical": "critical",
                }.get(overall_status.lower(), "normal")

                items.append(
                    {
                        "label": "System Status",
                        "value": overall_status.title(),
                        "type": "status",
                        "status": status_color,
                    }
                )

            # System load average (if available)
            load_avg = performance.get("load_average")
            if load_avg:
                if isinstance(load_avg, list) and len(load_avg) > 0:
                    items.append({"label": "Load Average (1m)", "value": f"{load_avg[0]:.2f}", "type": "text"})
                elif isinstance(load_avg, (int, float)):
                    items.append({"label": "Load Average", "value": f"{load_avg:.2f}", "type": "text"})

            # CPU and Memory usage from system_health
            cpu_usage = system_health.get("cpu_usage_percent")
            if cpu_usage is not None and isinstance(cpu_usage, (int, float)):
                items.append(
                    {
                        "label": "CPU Usage",
                        "value": f"{cpu_usage:.1f}%",
                        "type": "progress",
                        "progress": cpu_usage,
                        "color": self._get_usage_color(cpu_usage),
                    }
                )

            memory_usage = system_health.get("memory_usage_percent")
            if memory_usage is not None and isinstance(memory_usage, (int, float)):
                items.append(
                    {
                        "label": "Memory Usage",
                        "value": f"{memory_usage:.1f}%",
                        "type": "progress",
                        "progress": memory_usage,
                        "color": self._get_usage_color(memory_usage),
                    }
                )

            # System recommendations (if available)
            recommendations = system_health.get("recommendations", [])
            if recommendations and isinstance(recommendations, list) and len(recommendations) > 0:
                # Show first recommendation
                first_rec = recommendations[0]
                if isinstance(first_rec, str):
                    items.append({"label": "Recommendation", "value": first_rec, "type": "text"})
                elif isinstance(first_rec, dict) and "message" in first_rec:
                    items.append({"label": "Recommendation", "value": first_rec["message"], "type": "text"})

            # Swap/Pagefile usage (legacy support)
            swap_info = specs.get("memory_info", {})
            if isinstance(swap_info, dict):
                swap_total = swap_info.get("swap_total") or swap_info.get("swap_memory", {}).get("total")
                swap_used = swap_info.get("swap_used") or swap_info.get("swap_memory", {}).get("used")

                if (
                    swap_total
                    and swap_used
                    and isinstance(swap_total, (int, float))
                    and isinstance(swap_used, (int, float))
                ):
                    swap_percent = min(100, max(0, (swap_used / swap_total) * 100))
                    swap_gb = swap_total / (1024**3)
                    items.append({"label": "Pagefile Size", "value": f"{swap_gb:.1f} GB", "type": "text"})
                    items.append(
                        {
                            "label": "Pagefile Usage",
                            "value": f"{swap_percent:.1f}%",
                            "type": "progress",
                            "progress": swap_percent,
                            "color": self._get_usage_color(swap_percent),
                        }
                    )

            if not items:
                return None

            return {
                "title": "⚡ Performance",
                "category": "performance",
                "color": "#FF5722",  # Deep Orange
                "items": items,
            }

        except Exception as e:
            self.logger.warning(f"Failed to create performance card: {e}")
            return None

    def _create_error_card(self, error_message: str) -> List[Dict[str, Any]]:
        """Create error card when formatting fails."""
        return [
            {
                "title": "❌ Error",
                "category": "error",
                "color": "#F44336",  # Red
                "items": [{"label": "Error Message", "value": error_message, "type": "text"}],
            }
        ]

    def _create_no_data_card(self) -> List[Dict[str, Any]]:
        """Create placeholder card when no data is available."""
        return [
            {
                "title": "📊 No Data Available",
                "category": "no_data",
                "color": "#9E9E9E",  # Grey
                "items": [
                    {"label": "Status", "value": "No system information found in the provided data", "type": "text"},
                    {"label": "Suggestion", "value": "Please collect system specifications first", "type": "text"},
                ],
            }
        ]

    def _get_usage_color(self, percentage: float) -> str:
        """Get color based on usage percentage."""
        try:
            # Ensure percentage is a valid number
            if not isinstance(percentage, (int, float)):
                return "#9E9E9E"  # Grey for invalid data

            # Clamp percentage to 0-100 range
            percentage = max(0, min(100, float(percentage)))

            if percentage < 50:
                return "#4CAF50"  # Green
            elif percentage < 80:
                return "#FF9800"  # Orange
            else:
                return "#F44336"  # Red

        except Exception:
            return "#9E9E9E"  # Grey for errors

    def _format_datetime(self, dt_string: str) -> str:
        """Format datetime string for display."""
        try:
            # Try parsing common datetime formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]:
                try:
                    dt = datetime.strptime(dt_string, fmt)
                    return dt.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    continue

            # If parsing fails, return as-is
            return dt_string

        except Exception:
            return dt_string

    def _calculate_uptime(self, boot_time_str: str) -> str:
        """Calculate system uptime from boot time."""
        try:
            # Try parsing boot time with enhanced format support
            formats_to_try = [
                "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds (most common)
                "%Y-%m-%dT%H:%M:%S",  # ISO format without microseconds
                "%Y-%m-%d %H:%M:%S.%f",  # Space format with microseconds
                "%Y-%m-%d %H:%M:%S",  # Space format without microseconds
                "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with microseconds and Z
                "%Y-%m-%dT%H:%M:%SZ",  # ISO format without microseconds with Z
            ]

            boot_time = None
            for fmt in formats_to_try:
                try:
                    boot_time = datetime.strptime(boot_time_str, fmt)
                    break
                except ValueError:
                    continue

            # If standard parsing fails, try fromisoformat (Python 3.7+)
            if boot_time is None:
                try:
                    # Remove Z if present and handle timezone
                    clean_str = boot_time_str.replace("Z", "")
                    boot_time = datetime.fromisoformat(clean_str)
                except (ValueError, AttributeError):
                    pass

            if boot_time is None:
                self.logger.debug(f"Failed to parse boot time: {boot_time_str}")
                return "Unknown"

            # Calculate uptime
            now = datetime.now()
            uptime_delta = now - boot_time

            days = uptime_delta.days
            hours, remainder = divmod(uptime_delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"

        except Exception:
            return "Unknown"

    def format_bytes(self, bytes_value: Union[int, float], precision: int = 1) -> str:
        """Format bytes value with appropriate unit."""
        try:
            # Validate input
            if bytes_value is None:
                return "Unknown"

            bytes_value = float(bytes_value)

            # Handle negative or zero values
            if bytes_value < 0:
                return "Invalid"
            if bytes_value == 0:
                return "0 B"

            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if bytes_value < 1024.0:
                    return f"{bytes_value:.{precision}f} {unit}"
                bytes_value /= 1024.0

            return f"{bytes_value:.{precision}f} PB"

        except (ValueError, TypeError, OverflowError) as e:
            self.logger.debug(f"Failed to format bytes: {e}")
            return str(bytes_value) if bytes_value is not None else "Unknown"

    def format_frequency(self, hz_value: Union[int, float]) -> str:
        """Format frequency value with appropriate unit."""
        try:
            hz_value = float(hz_value)

            if hz_value >= 1_000_000_000:
                return f"{hz_value / 1_000_000_000:.2f} GHz"
            elif hz_value >= 1_000_000:
                return f"{hz_value / 1_000_000:.0f} MHz"
            elif hz_value >= 1_000:
                return f"{hz_value / 1_000:.0f} kHz"
            else:
                return f"{hz_value:.0f} Hz"

        except Exception:
            return str(hz_value)
