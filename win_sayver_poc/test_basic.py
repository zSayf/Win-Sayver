#!/usr/bin/env python3
"""
Basic tests for Win Sayver components.
"""

import sys
import os
import unittest
from pathlib import Path

# Add the win_sayver_poc directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import (
    WinSayverError,
    SystemProfilingError,
    safe_get_attribute,
    clean_string,
    format_bytes,
    PerformanceTimer
)
from specs_collector import SystemSpecsCollector
from ai_client import AIClient


class TestUtils(unittest.TestCase):
    """Test utility functions."""
    
    def test_safe_get_attribute(self):
        """Test safe attribute getting."""
        class TestObj:
            attr = "test_value"
        
        obj = TestObj()
        self.assertEqual(safe_get_attribute(obj, "attr"), "test_value")
        self.assertEqual(safe_get_attribute(obj, "nonexistent", "default"), "default")
    
    def test_clean_string(self):
        """Test string cleaning."""
        self.assertEqual(clean_string("  test  "), "test")
        self.assertEqual(clean_string(None), "Unknown")
        self.assertEqual(clean_string(""), "Unknown")
        self.assertEqual(clean_string(123), "123")
    
    def test_format_bytes(self):
        """Test byte formatting."""
        self.assertEqual(format_bytes(1024), "1.0 KB")
        self.assertEqual(format_bytes(1048576), "1.0 MB")
        self.assertEqual(format_bytes(1073741824), "1.0 GB")
    
    def test_performance_timer(self):
        """Test performance timer."""
        import time
        
        with PerformanceTimer("test") as timer:
            time.sleep(0.01)  # Sleep for 10ms
        
        self.assertIsNotNone(timer.duration)
        self.assertGreater(timer.duration, 0.005)  # Should be at least 5ms


class TestSystemSpecsCollector(unittest.TestCase):
    """Test system specifications collector."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.collector = SystemSpecsCollector()
    
    def test_collector_initialization(self):
        """Test collector can be initialized."""
        self.assertIsInstance(self.collector, SystemSpecsCollector)
        self.assertIsNotNone(self.collector.logger)
    
    def test_collect_all_specs(self):
        """Test that all specs can be collected."""
        specs = self.collector.collect_all_specs()
        
        # Check that all required keys are present
        required_keys = {
            'computer_system', 'operating_system', 'processor', 'physical_memory',
            'storage_devices', 'network_adapters', 'graphics_cards', 'audio_devices',
            'installed_software', 'system_services', 'environment_variables'
        }
        
        for key in required_keys:
            self.assertIn(key, specs, f"Missing required key: {key}")
        
        # Check metadata
        self.assertIn('collection_metadata', specs)
        metadata = specs['collection_metadata']
        self.assertIn('timestamp', metadata)
        self.assertIn('duration', metadata)
        self.assertIn('collector_version', metadata)


class TestAIClient(unittest.TestCase):
    """Test AI client."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = AIClient()
    
    def test_client_initialization(self):
        """Test client can be initialized."""
        self.assertIsInstance(self.client, AIClient)
        self.assertIsNotNone(self.client.logger)
    
    def test_analyze_error(self):
        """Test error analysis method."""
        system_specs = {'os': 'Windows 11'}
        result = self.client.analyze_error(system_specs)
        
        # Check result structure
        self.assertIn('analysis', result)
        self.assertIn('confidence', result)
        self.assertIn('suggestions', result)
        self.assertIn('metadata', result)
        
        # Check types
        self.assertIsInstance(result['analysis'], str)
        self.assertIsInstance(result['confidence'], (int, float))
        self.assertIsInstance(result['suggestions'], list)
        self.assertIsInstance(result['metadata'], dict)


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_full_workflow(self):
        """Test complete workflow from specs collection to AI analysis."""
        # Collect system specs
        collector = SystemSpecsCollector()
        specs = collector.collect_all_specs()
        
        # Analyze with AI client
        client = AIClient()
        result = client.analyze_error(specs, description="Test error")
        
        # Verify the workflow completed successfully
        self.assertIsInstance(specs, dict)
        self.assertIsInstance(result, dict)
        self.assertIn('analysis', result)


if __name__ == '__main__':
    # Set up logging for tests
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Run tests
    unittest.main(verbosity=2)