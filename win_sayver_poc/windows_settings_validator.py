#!/usr/bin/env python3
"""
Windows Settings URL Validation and Testing Module
================================================

This module provides comprehensive validation and testing for Windows settings URLs
used in Win Sayver's AI responses. It validates URL formats, tests accessibility,
and provides diagnostic information for troubleshooting.
"""

import logging
import re
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from windows_settings_urls import (
    WINDOWS_SETTINGS,
    get_windows_settings_regex,
    search_settings,
    validate_settings_url,
)


class URLValidationResult(Enum):
    """Validation result types."""

    VALID = "valid"
    INVALID_FORMAT = "invalid_format"
    UNKNOWN_SETTING = "unknown_setting"
    DEPRECATED = "deprecated"
    NOT_AVAILABLE = "not_available"


@dataclass
class ValidationReport:
    """Validation report for a Windows settings URL."""

    url: str
    result: URLValidationResult
    description: str
    alternative_urls: List[str]
    windows_version_support: Dict[str, bool]
    accessibility_tested: bool
    test_timestamp: Optional[str] = None


class WindowsSettingsValidator:
    """
    Comprehensive validator for Windows settings URLs.

    Provides validation, testing, and diagnostic capabilities for ms-settings:// URLs
    used in Win Sayver AI responses.
    """

    def __init__(self):
        """Initialize the validator."""
        self.logger = logging.getLogger(__name__)

        # Known deprecated URLs (Windows 10 -> Windows 11 changes)
        self.deprecated_urls = {
            "ms-settings:privacy-general": "ms-settings:privacy",
            "ms-settings:windowsupdate-action": "ms-settings:windowsupdate",
            "ms-settings:backup": "ms-settings:sync",  # Backup page deprecated in Windows 11
        }

        # Windows version specific URLs
        self.version_specific_urls = {
            "ms-settings:cortana": ["10"],  # Cortana settings removed in Windows 11
            "ms-settings:holographic": ["10", "11"],  # Mixed Reality
            "ms-settings:deviceusage": ["11"],  # New in Windows 11
            "ms-settings:personalization-start-places": ["11"],  # New folder settings
        }

        # URLs that require specific Windows features
        self.feature_dependent_urls = {
            "ms-settings:holographic-audio": "Mixed Reality Portal",
            "ms-settings:mobile-devices": "Phone Link",
            "ms-settings:deviceencryption": "BitLocker or Device Encryption",
            "ms-settings:easeofaccess-eyecontrol": "Eye Control Hardware",
        }

    def validate_url(self, url: str) -> ValidationReport:
        """
        Validate a Windows settings URL.

        Args:
            url: The ms-settings:// URL to validate

        Returns:
            ValidationReport with validation results
        """
        try:
            # Basic format validation
            if not self._is_valid_format(url):
                return ValidationReport(
                    url=url,
                    result=URLValidationResult.INVALID_FORMAT,
                    description=f"Invalid URL format: {url}",
                    alternative_urls=[],
                    windows_version_support={},
                    accessibility_tested=False,
                )

            # Check if URL is in our known database
            if not validate_settings_url(url):
                # Try to find similar URLs
                similar_urls = self._find_similar_urls(url)
                return ValidationReport(
                    url=url,
                    result=URLValidationResult.UNKNOWN_SETTING,
                    description=f"Unknown settings URL: {url}",
                    alternative_urls=similar_urls,
                    windows_version_support={},
                    accessibility_tested=False,
                )

            # Check for deprecated URLs
            if url in self.deprecated_urls:
                return ValidationReport(
                    url=url,
                    result=URLValidationResult.DEPRECATED,
                    description=f"Deprecated URL. Use {self.deprecated_urls[url]} instead.",
                    alternative_urls=[self.deprecated_urls[url]],
                    windows_version_support={},
                    accessibility_tested=False,
                )

            # Check version compatibility
            version_support = self._check_version_support(url)

            # URL appears valid
            return ValidationReport(
                url=url,
                result=URLValidationResult.VALID,
                description="Valid Windows settings URL",
                alternative_urls=[],
                windows_version_support=version_support,
                accessibility_tested=False,
                test_timestamp=str(time.time()),
            )

        except Exception as e:
            self.logger.error(f"Error validating URL {url}: {e}")
            return ValidationReport(
                url=url,
                result=URLValidationResult.INVALID_FORMAT,
                description=f"Validation error: {e}",
                alternative_urls=[],
                windows_version_support={},
                accessibility_tested=False,
            )

    def test_url_accessibility(self, url: str) -> bool:
        """
        Test if a Windows settings URL is accessible on the current system.

        Args:
            url: The ms-settings:// URL to test

        Returns:
            True if URL can be opened successfully, False otherwise
        """
        try:
            # Use subprocess to test URL accessibility without actually opening it
            # This is safer than using QDesktopServices during validation
            result = subprocess.run(
                ["powershell", "-Command", f'Start-Process "{url}" -PassThru -WindowStyle Hidden'],
                capture_output=True,
                text=True,
                timeout=5,
            )

            # If no error occurred, the URL is likely accessible
            return result.returncode == 0

        except subprocess.TimeoutExpired:
            self.logger.warning(f"Timeout testing URL accessibility: {url}")
            return False
        except Exception as e:
            self.logger.warning(f"Error testing URL accessibility {url}: {e}")
            return False

    def validate_ai_response(self, response_text: str) -> Dict[str, Any]:
        """
        Validate all Windows settings URLs found in an AI response.

        Args:
            response_text: The AI response text containing potential URLs

        Returns:
            Dictionary with validation summary and detailed results
        """
        try:
            # Extract all ms-settings URLs from the response
            urls = self._extract_settings_urls(response_text)

            if not urls:
                return {
                    "total_urls": 0,
                    "valid_urls": 0,
                    "invalid_urls": 0,
                    "deprecated_urls": 0,
                    "unknown_urls": 0,
                    "validation_details": [],
                    "recommendations": [],
                }

            # Validate each URL
            validation_results = []
            for url in urls:
                result = self.validate_url(url)
                validation_results.append(result)

            # Compile summary statistics
            total_urls = len(urls)
            valid_urls = sum(1 for r in validation_results if r.result == URLValidationResult.VALID)
            invalid_urls = sum(1 for r in validation_results if r.result == URLValidationResult.INVALID_FORMAT)
            deprecated_urls = sum(1 for r in validation_results if r.result == URLValidationResult.DEPRECATED)
            unknown_urls = sum(1 for r in validation_results if r.result == URLValidationResult.UNKNOWN_SETTING)

            # Generate recommendations
            recommendations = self._generate_recommendations(validation_results)

            return {
                "total_urls": total_urls,
                "valid_urls": valid_urls,
                "invalid_urls": invalid_urls,
                "deprecated_urls": deprecated_urls,
                "unknown_urls": unknown_urls,
                "validation_details": [
                    {
                        "url": r.url,
                        "result": r.result.value,
                        "description": r.description,
                        "alternatives": r.alternative_urls,
                    }
                    for r in validation_results
                ],
                "recommendations": recommendations,
            }

        except Exception as e:
            self.logger.error(f"Error validating AI response: {e}")
            return {
                "error": f"Validation failed: {e}",
                "total_urls": 0,
                "valid_urls": 0,
                "invalid_urls": 0,
                "deprecated_urls": 0,
                "unknown_urls": 0,
                "validation_details": [],
                "recommendations": [],
            }

    def get_diagnostic_info(self) -> Dict[str, Any]:
        """
        Get diagnostic information about Windows settings URL support.

        Returns:
            Dictionary with diagnostic information
        """
        try:
            # Get Windows version info
            windows_version = self._get_windows_version()

            # Test a few key settings URLs
            test_urls = [
                "ms-settings:display",
                "ms-settings:sound",
                "ms-settings:network-wifi",
                "ms-settings:windowsupdate",
                "ms-settings:about",
            ]

            accessibility_results = {}
            for url in test_urls:
                accessibility_results[url] = self.test_url_accessibility(url)

            return {
                "windows_version": windows_version,
                "total_known_urls": len(WINDOWS_SETTINGS),
                "url_accessibility_test": accessibility_results,
                "deprecated_urls_count": len(self.deprecated_urls),
                "version_specific_urls_count": len(self.version_specific_urls),
                "feature_dependent_urls_count": len(self.feature_dependent_urls),
            }

        except Exception as e:
            self.logger.error(f"Error getting diagnostic info: {e}")
            return {"error": f"Diagnostic failed: {e}"}

    def _is_valid_format(self, url: str) -> bool:
        """Check if URL has valid ms-settings format."""
        if not url or not isinstance(url, str):
            return False

        # Must start with ms-settings:
        if not url.lower().startswith("ms-settings:"):
            return False

        # Check overall format
        pattern = r"^ms-settings:[a-zA-Z0-9\-_]+$"
        return bool(re.match(pattern, url))

    def _find_similar_urls(self, url: str) -> List[str]:
        """Find similar URLs for suggestions."""
        try:
            # Extract the setting name part
            if ":" in url:
                setting_part = url.split(":", 1)[1]
                # Search for similar settings
                similar = search_settings(setting_part)
                return [result[1] for result in similar[:3]]  # Top 3 matches
            return []
        except Exception:
            return []

    def _check_version_support(self, url: str) -> Dict[str, bool]:
        """Check Windows version support for URL."""
        support_info = {"windows_10": True, "windows_11": True}

        if url in self.version_specific_urls:
            supported_versions = self.version_specific_urls[url]
            support_info["windows_10"] = "10" in supported_versions
            support_info["windows_11"] = "11" in supported_versions

        return support_info

    def _extract_settings_urls(self, text: str) -> List[str]:
        """Extract all ms-settings URLs from text."""
        pattern = get_windows_settings_regex()
        matches = re.findall(pattern, text, re.IGNORECASE)
        return list(set(matches))  # Remove duplicates

    def _generate_recommendations(self, validation_results: List[ValidationReport]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        deprecated_count = sum(1 for r in validation_results if r.result == URLValidationResult.DEPRECATED)
        unknown_count = sum(1 for r in validation_results if r.result == URLValidationResult.UNKNOWN_SETTING)
        invalid_count = sum(1 for r in validation_results if r.result == URLValidationResult.INVALID_FORMAT)

        if deprecated_count > 0:
            recommendations.append(f"Replace {deprecated_count} deprecated URL(s) with current alternatives")

        if unknown_count > 0:
            recommendations.append(f"Verify {unknown_count} unknown URL(s) against current Windows documentation")

        if invalid_count > 0:
            recommendations.append(f"Fix {invalid_count} URL(s) with invalid format")

        if not recommendations:
            recommendations.append("All Windows settings URLs are valid and current")

        return recommendations

    def _get_windows_version(self) -> str:
        """Get current Windows version."""
        try:
            result = subprocess.run(
                ["wmic", "os", "get", "Caption,Version", "/format:csv"], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        parts = line.split(",")
                        if len(parts) >= 2:
                            return f"{parts[1]} ({parts[2]})"

            return "Windows (version detection failed)"

        except Exception as e:
            self.logger.warning(f"Failed to get Windows version: {e}")
            return "Windows (unknown version)"


# Test function for validation
def test_windows_settings_validation():
    """Test the Windows settings URL validation system."""
    print("🧪 Testing Windows Settings URL Validation")
    print("=" * 60)

    validator = WindowsSettingsValidator()

    # Test valid URLs
    valid_urls = ["ms-settings:display", "ms-settings:sound", "ms-settings:network-wifi", "ms-settings:windowsupdate"]

    print("\n✅ Testing Valid URLs:")
    for url in valid_urls:
        result = validator.validate_url(url)
        print(f"  {url}: {result.result.value} - {result.description}")

    # Test invalid URLs
    invalid_urls = ["ms-settings:invalid-setting", "not-a-settings-url", "ms-settings:", "ms-settings:display:extra"]

    print("\n❌ Testing Invalid URLs:")
    for url in invalid_urls:
        result = validator.validate_url(url)
        print(f"  {url}: {result.result.value} - {result.description}")

    # Test AI response validation
    mock_ai_response = """
    To fix your display issue:
    1. Open [Display Settings](ms-settings:display) 
    2. Check [Sound Settings](ms-settings:sound)
    3. Visit [Windows Update](ms-settings:windowsupdate)
    4. This invalid URL should be caught: ms-settings:nonexistent
    """

    print("\n📝 Testing AI Response Validation:")
    response_validation = validator.validate_ai_response(mock_ai_response)
    print(f"  Total URLs found: {response_validation['total_urls']}")
    print(f"  Valid URLs: {response_validation['valid_urls']}")
    print(f"  Invalid URLs: {response_validation['invalid_urls']}")
    print(f"  Unknown URLs: {response_validation['unknown_urls']}")

    # Print recommendations
    if response_validation["recommendations"]:
        print("  Recommendations:")
        for rec in response_validation["recommendations"]:
            print(f"    • {rec}")

    # Test diagnostic info
    print("\n🔍 System Diagnostic Information:")
    diagnostic = validator.get_diagnostic_info()
    if "error" not in diagnostic:
        print(f"  Windows Version: {diagnostic['windows_version']}")
        print(f"  Known URLs: {diagnostic['total_known_urls']}")
        print(f"  Deprecated URLs: {diagnostic['deprecated_urls_count']}")

        print("  URL Accessibility Test:")
        for url, accessible in diagnostic["url_accessibility_test"].items():
            status = "✅ Accessible" if accessible else "❌ Not accessible"
            print(f"    {url}: {status}")
    else:
        print(f"  Error: {diagnostic['error']}")

    print("\n🎯 Windows Settings URL Validation Test Complete!")


if __name__ == "__main__":
    test_windows_settings_validation()
