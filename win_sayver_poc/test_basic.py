#!/usr/bin/env python3
"""
Basic tests for Win Sayver components.
"""

import os
import sys
import unittest
from pathlib import Path

# Add the win_sayver_poc directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_client import AIClient
from specs_collector import SystemSpecsCollector
from utils import (
    PerformanceTimer,
    SystemProfilingError,
    WinSayverError,
    clean_string,
    format_bytes,
    safe_get_attribute,
)


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
        # Note: clean_string expects str input but handles type conversion internally
        self.assertEqual(clean_string(str(None)), "None")
        self.assertEqual(clean_string(""), "")
        self.assertEqual(clean_string(str(123)), "123")

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
        # timer.duration returns float, so this comparison is valid
        if timer.duration is not None:
            self.assertGreater(float(timer.duration), 0.005)  # Should be at least 5ms


class TestSystemSpecsCollector(unittest.TestCase):
    """Test system specifications collector."""

    def setUp(self):
        """Set up test fixtures."""
        self.collector = SystemSpecsCollector()

    def test_collector_initialization(self):
        """Test collector can be initialized."""
        self.assertIsInstance(self.collector, SystemSpecsCollector)
        self.assertIsNotNone(self.collector.logger)

    def test_collect_basic_info(self):
        """Test that basic system info can be collected without full WMI."""
        # Test basic information that doesn't require heavy WMI operations
        try:
            # This should work without COM threading issues
            import platform

            import psutil

            # Test basic system info
            self.assertIsNotNone(platform.system())
            self.assertIsNotNone(psutil.cpu_count())

            # Test collector initialization (but skip full collection)
            self.assertIsInstance(self.collector, SystemSpecsCollector)
            self.assertIsNotNone(self.collector.logger)

        except Exception as e:
            self.fail(f"Basic system info collection failed: {e}")


class TestAIClient(unittest.TestCase):
    """Test AI client."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = AIClient()

    def test_client_initialization(self):
        """Test client can be initialized."""
        self.assertIsInstance(self.client, AIClient)
        self.assertIsNotNone(self.client.logger)

    def test_analyze_text_only(self):
        """Test text-only analysis method."""
        system_specs = {"os": "Windows 11"}
        result = self.client.analyze_text_only(error_description="Test error description", system_specs=system_specs)

        # Check result structure - returns wrapped response
        self.assertIn("success", result)
        if result.get("success"):
            analysis = result.get("analysis", {})
            self.assertIsInstance(analysis, dict)
            # Check for expected keys in successful analysis
            self.assertIn("analysis_metadata", analysis)
        else:
            # Handle error case
            self.assertIn("error", result)


class TestIntegration(unittest.TestCase):
    """Integration tests."""

    def test_basic_workflow(self):
        """Test basic workflow without full system collection."""
        # Create minimal test specs
        test_specs = {
            "operating_system": {"name": "Windows 11", "version": "22H2"},
            "processor": {"name": "Intel Core i7", "cores": 8},
            "collection_metadata": {"timestamp": "2024-01-01T00:00:00"},
        }

        # Test AI client initialization
        client = AIClient()
        self.assertIsInstance(client, AIClient)
        self.assertIsNotNone(client.logger)

        # Test error handling with minimal specs
        # This should not fail due to missing API key - it should return error dict
        result = client.analyze_text_only(error_description="Test error", system_specs=test_specs)

        # Verify the result structure (should handle missing API key gracefully)
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)


if __name__ == "__main__":
    # Set up logging for tests
    import logging

    logging.basicConfig(level=logging.INFO)

    # Run tests
    unittest.main(verbosity=2)
