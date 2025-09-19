#!/usr/bin/env python3
"""
Windows Settings URLs Database for Win Sayver
===========================================

This module provides a comprehensive database of Windows settings URLs (ms-settings://)
for use in AI-powered troubleshooting responses. Based on official Microsoft documentation
and comprehensive research of Windows 10/11 settings pages.

Usage:
    from windows_settings_urls import WINDOWS_SETTINGS, get_settings_url, validate_settings_url

    # Get URL for display settings
    display_url = get_settings_url('display')

    # Validate a settings URL
    is_valid = validate_settings_url('ms-settings:display')
"""

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

# URL Fallback System for problematic Windows Settings URLs
URL_FALLBACKS = {
    "windows-security": [
        "ms-settings:windowssecurity",  # Primary verified working URL
        "ms-settings:windowsdefender",  # Legacy/fallback URL
        "ms-settings:privacy",  # Privacy & Security section
        "ms-settings:findmydevice",  # Security feature fallback
        "ms-settings:windowsupdate",  # Update & Security fallback
    ],
    "bluetooth": [
        "ms-settings:bluetooth",
        "ms-settings:connecteddevices",
        "ms-settings:devices",
    ],
    "wifi": [
        "ms-settings:network-wifi",
        "ms-settings:network-status",
        "ms-settings:network",
    ],
}

# Comprehensive Windows Settings URLs Database
WINDOWS_SETTINGS = {
    # System Settings
    "system": "ms-settings:system",
    "display": "ms-settings:display",
    "display-advanced": "ms-settings:display-advanced",
    "display-graphics": "ms-settings:display-advancedgraphics",
    "night-light": "ms-settings:nightlight",
    "sound": "ms-settings:sound",
    "sound-devices": "ms-settings:sound-devices",
    "volume-mixer": "ms-settings:apps-volume",
    "notifications": "ms-settings:notifications",
    "focus-assist": "ms-settings:quiethours",
    "power-sleep": "ms-settings:powersleep",
    "battery": "ms-settings:batterysaver",
    "battery-usage": "ms-settings:batterysaver-usagedetails",
    "storage": "ms-settings:storagesense",
    "storage-sense": "ms-settings:storagepolicies",
    "multitasking": "ms-settings:multitasking",
    "clipboard": "ms-settings:clipboard",
    "remote-desktop": "ms-settings:remotedesktop",
    "about": "ms-settings:about",
    # Network & Internet
    "network": "ms-settings:network-status",
    "wifi": "ms-settings:network-wifi",
    "ethernet": "ms-settings:network-ethernet",
    "vpn": "ms-settings:network-vpn",
    "mobile-hotspot": "ms-settings:network-mobilehotspot",
    "airplane-mode": "ms-settings:network-airplanemode",
    "proxy": "ms-settings:network-proxy",
    "cellular": "ms-settings:network-cellular",
    # Bluetooth & Devices
    "bluetooth": "ms-settings:bluetooth",
    "devices": "ms-settings:connecteddevices",
    "printers": "ms-settings:printers",
    "camera": "ms-settings:camera",
    "mouse": "ms-settings:mousetouchpad",
    "touchpad": "ms-settings:devices-touchpad",
    "pen": "ms-settings:pen",
    "autoplay": "ms-settings:autoplay",
    "usb": "ms-settings:usb",
    # Personalization
    "personalization": "ms-settings:personalization",
    "background": "ms-settings:personalization-background",
    "colors": "ms-settings:personalization-colors",
    "themes": "ms-settings:themes",
    "lock-screen": "ms-settings:lockscreen",
    "start": "ms-settings:personalization-start",
    "taskbar": "ms-settings:taskbar",
    "fonts": "ms-settings:fonts",
    # Apps
    "apps": "ms-settings:appsfeatures",
    "default-apps": "ms-settings:defaultapps",
    "startup-apps": "ms-settings:startupapps",
    "optional-features": "ms-settings:optionalfeatures",
    "apps-websites": "ms-settings:appsforwebsites",
    # Accounts
    "accounts": "ms-settings:accounts",
    "your-info": "ms-settings:yourinfo",
    "email-accounts": "ms-settings:emailandaccounts",
    "sign-in-options": "ms-settings:signinoptions",
    "family-users": "ms-settings:otherusers",
    "work-school": "ms-settings:workplace",
    "windows-backup": "ms-settings:backup",
    "sync-settings": "ms-settings:sync",
    # Time & Language
    "date-time": "ms-settings:dateandtime",
    "language": "ms-settings:regionlanguage",
    "typing": "ms-settings:typing",
    "speech": "ms-settings:speech",
    # Gaming
    "gaming": "ms-settings:gaming",
    "game-bar": "ms-settings:gaming-gamebar",
    "game-dvr": "ms-settings:gaming-gamedvr",
    "game-mode": "ms-settings:gaming-gamemode",
    # Accessibility
    "accessibility": "ms-settings:easeofaccess",
    "text-size": "ms-settings:easeofaccess-display",
    "magnifier": "ms-settings:easeofaccess-magnifier",
    "color-filters": "ms-settings:easeofaccess-colorfilter",
    "high-contrast": "ms-settings:easeofaccess-highcontrast",
    "narrator": "ms-settings:easeofaccess-narrator",
    "keyboard-accessibility": "ms-settings:easeofaccess-keyboard",
    "mouse-accessibility": "ms-settings:easeofaccess-mouse",
    # Privacy & Security
    "privacy": "ms-settings:privacy",
    "windows-security": "ms-settings:windowssecurity",
    "find-my-device": "ms-settings:findmydevice",
    "device-encryption": "ms-settings:deviceencryption",
    "location-privacy": "ms-settings:privacy-location",
    "camera-privacy": "ms-settings:privacy-webcam",
    "microphone-privacy": "ms-settings:privacy-microphone",
    "activity-history": "ms-settings:privacy-activityhistory",
    "diagnostics-feedback": "ms-settings:privacy-feedback",
    # Update & Security
    "windows-update": "ms-settings:windowsupdate",
    "windows-update-history": "ms-settings:windowsupdate-history",
    "windows-update-restart": "ms-settings:windowsupdate-restartoptions",
    "recovery": "ms-settings:recovery",
    "activation": "ms-settings:activation",
    "troubleshoot": "ms-settings:troubleshoot",
    "developers": "ms-settings:developers",
    # Windows Hello
    "windows-hello-face": "ms-settings:signinoptions-launchfaceenrollment",
    "windows-hello-fingerprint": "ms-settings:signinoptions-launchfingerprintenrollment",
    "windows-hello-pin": "ms-settings:signinoptions-launchpinenrollment",
    # Mixed Reality (if available)
    "mixed-reality": "ms-settings:holographic",
    "mixed-reality-audio": "ms-settings:holographic-audio",
    "mixed-reality-headset": "ms-settings:holographic-headset",
}

# Category mappings for easier lookup
SETTINGS_CATEGORIES = {
    "system": ["display", "sound", "notifications", "power-sleep", "storage", "about"],
    "network": ["wifi", "ethernet", "vpn", "bluetooth", "airplane-mode"],
    "devices": ["bluetooth", "printers", "camera", "mouse", "touchpad"],
    "personalization": ["background", "colors", "themes", "lock-screen", "taskbar"],
    "apps": ["apps", "default-apps", "startup-apps"],
    "accounts": ["your-info", "sign-in-options", "family-users"],
    "privacy": ["location-privacy", "camera-privacy", "microphone-privacy"],
    "security": ["windows-security", "device-encryption", "find-my-device"],
    "accessibility": ["text-size", "magnifier", "narrator", "high-contrast"],
    "updates": ["windows-update", "recovery", "troubleshoot"],
}

# Common troubleshooting scenarios mapped to settings
TROUBLESHOOTING_MAPPINGS = {
    "audio": ["sound", "sound-devices", "volume-mixer", "microphone-privacy"],
    "display": ["display", "display-advanced", "night-light", "display-graphics"],
    "connectivity": ["wifi", "ethernet", "network", "bluetooth", "vpn"],
    "security": ["windows-security", "device-encryption", "privacy", "windows-update"],
    "performance": ["storage", "startup-apps", "power-sleep", "troubleshoot"],
    "privacy": ["privacy", "location-privacy", "camera-privacy", "microphone-privacy"],
    "updates": ["windows-update", "windows-update-history", "recovery"],
    "accessibility": ["accessibility", "narrator", "magnifier", "high-contrast"],
    "personalization": ["personalization", "themes", "colors", "background"],
    "devices": ["bluetooth", "printers", "camera", "mouse", "usb"],
}


def get_settings_url(setting_key: str) -> Optional[str]:
    """
    Get the Windows settings URL for a given setting key.

    Args:
        setting_key: The setting identifier (e.g., 'display', 'wifi')

    Returns:
        The ms-settings:// URL or None if not found
    """
    return WINDOWS_SETTINGS.get(setting_key.lower())


def get_settings_for_category(category: str) -> List[Tuple[str, str]]:
    """
    Get all settings URLs for a given category.

    Args:
        category: Category name (e.g., 'system', 'network')

    Returns:
        List of (setting_name, url) tuples
    """
    category_settings = SETTINGS_CATEGORIES.get(category.lower(), [])
    return [(setting, WINDOWS_SETTINGS[setting]) for setting in category_settings if setting in WINDOWS_SETTINGS]


def get_troubleshooting_urls(issue_type: str) -> List[Tuple[str, str]]:
    """
    Get relevant settings URLs for a troubleshooting scenario.

    Args:
        issue_type: Type of issue (e.g., 'audio', 'connectivity')

    Returns:
        List of (setting_name, url) tuples
    """
    relevant_settings = TROUBLESHOOTING_MAPPINGS.get(issue_type.lower(), [])
    return [(setting, WINDOWS_SETTINGS[setting]) for setting in relevant_settings if setting in WINDOWS_SETTINGS]


def validate_settings_url(url: str) -> bool:
    """
    Validate if a URL is a valid Windows settings URL.

    Args:
        url: URL to validate

    Returns:
        True if valid ms-settings:// URL, False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    # Check if it starts with ms-settings:
    if not url.lower().startswith("ms-settings:"):
        return False

    # Check if it's in our known settings
    return url in WINDOWS_SETTINGS.values()


def search_settings(query: str) -> List[Tuple[str, str]]:
    """
    Search for settings URLs matching a query.

    Args:
        query: Search query

    Returns:
        List of (setting_name, url) tuples matching the query
    """
    query_lower = query.lower()
    matches = []

    for setting_name, url in WINDOWS_SETTINGS.items():
        if query_lower in setting_name.lower() or query_lower in url.lower().replace("ms-settings:", ""):
            matches.append((setting_name, url))

    return matches


def get_windows_settings_regex() -> str:
    """
    Get regex pattern for matching Windows settings URLs.

    Returns:
        Regex pattern string for ms-settings:// URLs
    """
    return r"(ms-settings:[a-zA-Z0-9\-_:]+)"


# Predefined patterns for common issues
COMMON_ISSUE_PATTERNS = {
    "sound not working": ["sound", "sound-devices", "microphone-privacy"],
    "wifi issues": ["wifi", "network", "troubleshoot"],
    "bluetooth problems": ["bluetooth", "devices", "troubleshoot"],
    "display issues": ["display", "display-advanced", "display-graphics"],
    "startup problems": ["startup-apps", "recovery", "troubleshoot"],
    "privacy concerns": ["privacy", "location-privacy", "camera-privacy"],
    "security issues": ["windows-security", "device-encryption", "windows-update"],
    "performance issues": ["storage", "startup-apps", "power-sleep"],
    "update problems": ["windows-update", "recovery", "troubleshoot"],
    "accessibility needs": ["accessibility", "narrator", "magnifier"],
}


def get_fallback_urls(setting_key: str) -> List[str]:
    """
    Get fallback URLs for a setting that might have compatibility issues.

    Args:
        setting_key: The setting identifier (e.g., 'windows-security')

    Returns:
        List of alternative URLs to try if the primary URL fails
    """
    return URL_FALLBACKS.get(setting_key.lower(), [])


def get_primary_and_fallbacks(setting_key: str) -> List[str]:
    """
    Get primary URL and all fallback URLs for a setting.

    Args:
        setting_key: The setting identifier

    Returns:
        List of URLs starting with primary, followed by fallbacks
    """
    urls = []

    # Add primary URL if exists
    primary_url = get_settings_url(setting_key)
    if primary_url:
        urls.append(primary_url)

    # Add fallback URLs
    fallbacks = get_fallback_urls(setting_key)
    for fallback in fallbacks:
        if fallback not in urls:  # Avoid duplicates
            urls.append(fallback)

    return urls


def validate_and_get_alternatives(url: str) -> List[str]:
    """
    Validate a URL and provide alternatives if it's known to be problematic.

    Args:
        url: The URL to validate

    Returns:
        List of URLs including the original and alternatives
    """
    if not validate_settings_url(url):
        return []

    # Find which setting this URL belongs to
    for setting_key, setting_url in WINDOWS_SETTINGS.items():
        if setting_url == url:
            return get_primary_and_fallbacks(setting_key)

    return [url]  # Return original if no alternatives found


def get_urls_for_issue(issue_description: str) -> List[Tuple[str, str]]:
    """
    Get relevant settings URLs based on issue description.

    Args:
        issue_description: Description of the issue

    Returns:
        List of (setting_name, url) tuples
    """
    issue_lower = issue_description.lower()
    relevant_urls = []

    # Check against common patterns
    for pattern, settings in COMMON_ISSUE_PATTERNS.items():
        if pattern in issue_lower:
            for setting in settings:
                if setting in WINDOWS_SETTINGS:
                    relevant_urls.append((setting, WINDOWS_SETTINGS[setting]))

    # If no matches, try keyword matching
    if not relevant_urls:
        keywords = [
            "sound",
            "audio",
            "wifi",
            "network",
            "bluetooth",
            "display",
            "screen",
            "privacy",
            "security",
            "update",
            "startup",
            "performance",
        ]

        for keyword in keywords:
            if keyword in issue_lower:
                matches = search_settings(keyword)
                relevant_urls.extend(matches[:3])  # Limit to top 3 matches
                break

    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for item in relevant_urls:
        if item[1] not in seen:
            seen.add(item[1])
            unique_urls.append(item)

    return unique_urls[:5]  # Limit to top 5 relevant URLs
