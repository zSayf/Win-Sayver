#!/usr/bin/env python3
"""
Basic system specifications collector for Win Sayver.

Lightweight version for CI/CD testing.
"""

import logging
import platform
import sys
from typing import Dict, Any

try:
    import psutil
except ImportError:
    psutil = None

from utils import (
    WinSayverError,
    SystemProfilingError,
    safe_get_attribute,
    clean_string,
    PerformanceTimer
)


class SystemSpecsCollector:
    """
    Collects basic Windows system specifications.
    """
    
    def __init__(self):
        """Initialize the system specs collector."""
        self.logger = logging.getLogger(__name__)
    
    def collect_all_specs(self) -> Dict[str, Any]:
        """
        Collect all system specifications.
        
        Returns:
            Dictionary containing system specifications
        """
        try:
            with PerformanceTimer("System specs collection") as timer:
                specs = {
                    'computer_system': self._get_computer_system_info(),
                    'operating_system': self._get_os_info(),
                    'processor': self._get_processor_info(),
                    'physical_memory': self._get_memory_info(),
                    'storage_devices': self._get_storage_info(),
                    'network_adapters': self._get_network_info(),
                    'graphics_cards': self._get_graphics_info(),
                    'audio_devices': self._get_audio_info(),
                    'installed_software': self._get_software_info(),
                    'system_services': self._get_services_info(),
                    'environment_variables': self._get_env_vars(),
                    'collection_metadata': {
                        'timestamp': timer.start_time,
                        'duration': timer.duration or 0,
                        'collector_version': '3.1.0',
                        'platform': platform.platform()
                    }
                }
                
                self.logger.info(f"System specs collected successfully in {timer.duration:.2f}s")
                return specs
                
        except Exception as e:
            self.logger.error(f"Failed to collect system specs: {e}")
            raise SystemProfilingError(f"System specs collection failed: {e}")
    
    def _get_computer_system_info(self) -> Dict[str, Any]:
        """Get basic computer system information."""
        return {
            'manufacturer': clean_string(platform.machine()),
            'model': clean_string(platform.processor()),
            'name': clean_string(platform.node()),
            'system_type': clean_string(platform.architecture()[0])
        }
    
    def _get_os_info(self) -> Dict[str, Any]:
        """Get operating system information."""
        return {
            'name': clean_string(platform.system()),
            'version': clean_string(platform.version()),
            'release': clean_string(platform.release()),
            'build_number': clean_string(platform.version().split('.')[-1] if '.' in platform.version() else 'Unknown')
        }
    
    def _get_processor_info(self) -> Dict[str, Any]:
        """Get processor information."""
        info = {
            'name': clean_string(platform.processor()),
            'architecture': clean_string(platform.architecture()[0]),
            'cores': 'Unknown',
            'threads': 'Unknown'
        }
        
        if psutil:
            try:
                info['cores'] = psutil.cpu_count(logical=False) or 'Unknown'
                info['threads'] = psutil.cpu_count(logical=True) or 'Unknown'
            except Exception:
                pass
        
        return info
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory information."""
        info = {'total_memory': 'Unknown'}
        
        if psutil:
            try:
                memory = psutil.virtual_memory()
                info['total_memory'] = f"{memory.total // (1024**3)} GB"
            except Exception:
                pass
        
        return info
    
    def _get_storage_info(self) -> Dict[str, Any]:
        """Get storage information."""
        info = {'devices': []}
        
        if psutil:
            try:
                partitions = psutil.disk_partitions()
                for partition in partitions:
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        info['devices'].append({
                            'device': partition.device,
                            'mountpoint': partition.mountpoint,
                            'fstype': partition.fstype,
                            'total': f"{usage.total // (1024**3)} GB"
                        })
                    except Exception:
                        continue
            except Exception:
                pass
        
        return info
    
    def _get_network_info(self) -> Dict[str, Any]:
        """Get network information."""
        return {'adapters': []}
    
    def _get_graphics_info(self) -> Dict[str, Any]:
        """Get graphics information."""
        return {'cards': []}
    
    def _get_audio_info(self) -> Dict[str, Any]:
        """Get audio information."""
        return {'devices': []}
    
    def _get_software_info(self) -> Dict[str, Any]:
        """Get software information."""
        return {'programs': []}
    
    def _get_services_info(self) -> Dict[str, Any]:
        """Get services information."""
        return {'services': []}
    
    def _get_env_vars(self) -> Dict[str, Any]:
        """Get environment variables."""
        import os
        return {
            'PATH': os.environ.get('PATH', 'Unknown'),
            'PYTHON_VERSION': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'PLATFORM': platform.platform()
        }


if __name__ == "__main__":
    collector = SystemSpecsCollector()
    specs = collector.collect_all_specs()
    print(f"Collected {len(specs)} system specification categories")