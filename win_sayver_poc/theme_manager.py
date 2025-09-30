#!/usr/bin/env python3
"""
Simple Theme Manager for Win Sayver GUI
======================================

Professional theme system with light/dark mode support.
Provides consistent visual appearance and user preferences management.
"""

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

# PyQt6 availability check
try:
    from PyQt6.QtWidgets import QApplication

    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


class ThemeMode(Enum):
    """Theme mode enumeration."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class SimpleThemeManager:
    """
    Simple theme manager for Win Sayver GUI.

    Provides light/dark mode switching and stylesheet management.
    """

    def __init__(self, settings=None):
        """
        Initialize the theme manager.

        Args:
            settings: QSettings instance for persistent storage (optional)
        """
        self.settings = settings
        self.current_theme = ThemeMode.LIGHT  # Changed from ThemeMode.SYSTEM to make light mode default

        # Define theme stylesheets
        self._stylesheets = {ThemeMode.LIGHT: self._get_light_stylesheet(), ThemeMode.DARK: self._get_dark_stylesheet()}

        # Load saved theme preference if settings available
        if self.settings:
            self._load_theme_settings()

    def _get_light_stylesheet(self) -> str:
        """Get light theme stylesheet."""
        return """
        /* Win Sayver Light Theme */
        QMainWindow {
            background-color: #ffffff;
            color: #212121;
        }
        
        QWidget {
            background-color: #ffffff;
            color: #212121;
        }
        
        QTabWidget::pane {
            border: 1px solid #E0E0E0;
            background-color: #ffffff;
        }
        
        QTabBar::tab {
            background-color: #f5f5f5;
            color: #757575;
            padding: 8px 16px;
            margin: 2px;
            border-radius: 4px;
        }
        
        QTabBar::tab:selected {
            background-color: #2196F3;
            color: #ffffff;
        }
        
        QTabBar::tab:hover {
            background-color: #E3F2FD;
        }
        
        QPushButton {
            background-color: #2196F3;
            color: #ffffff;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        QPushButton:hover {
            background-color: #1976D2;
        }
        
        QPushButton:pressed {
            background-color: #0D47A1;
        }
        
        QPushButton:disabled {
            background-color: #BDBDBD;
            color: #ffffff;
        }
        
        QGroupBox {
            font-weight: 600;
            border: 2px solid #E0E0E0;
            border-radius: 8px;
            margin-top: 1ex;
            padding-top: 10px;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: #2196F3;
        }
        
        QTextEdit {
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            padding: 8px;
            background-color: #ffffff;
            color: #212121;
        }
        
        QTextEdit:focus {
            border: 2px solid #2196F3;
        }
        
        QScrollArea {
            border: 1px solid #E0E0E0;
            border-radius: 4px;
        }
        
        QStatusBar {
            background-color: #f5f5f5;
            color: #757575;
            border-top: 1px solid #E0E0E0;
        }
        
        QMenuBar {
            background-color: #ffffff;
            color: #212121;
            border-bottom: 1px solid #E0E0E0;
        }
        
        QMenuBar::item:selected {
            background-color: #E3F2FD;
        }
        
        QMenu {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #E0E0E0;
        }
        
        QMenu::item:selected {
            background-color: #E3F2FD;
        }
        
        QProgressBar {
            border: 1px solid #E0E0E0;
            border-radius: 4px;
            text-align: center;
            background-color: #f5f5f5;
        }
        
        QProgressBar::chunk {
            background-color: #2196F3;
            border-radius: 3px;
        }
        """

    def _get_dark_stylesheet(self) -> str:
        """Get dark theme stylesheet."""
        return """
        /* Win Sayver Dark Theme */
        QMainWindow {
            background-color: #121212;
            color: #ffffff;
        }
        
        QWidget {
            background-color: #121212;
            color: #ffffff;
        }
        
        QTabWidget::pane {
            border: 1px solid #424242;
            background-color: #1E1E1E;
        }
        
        QTabBar::tab {
            background-color: #2C2C2C;
            color: #B0B0B0;
            padding: 8px 16px;
            margin: 2px;
            border-radius: 4px;
        }
        
        QTabBar::tab:selected {
            background-color: #BB86FC;
            color: #000000;
        }
        
        QTabBar::tab:hover {
            background-color: #383838;
        }
        
        QPushButton {
            background-color: #BB86FC;
            color: #000000;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        QPushButton:hover {
            background-color: #A56CF5;
        }
        
        QPushButton:pressed {
            background-color: #8E4EC6;
        }
        
        QPushButton:disabled {
            background-color: #616161;
            color: #9E9E9E;
        }
        
        QGroupBox {
            font-weight: 600;
            border: 2px solid #424242;
            border-radius: 8px;
            margin-top: 1ex;
            padding-top: 10px;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: #BB86FC;
        }
        
        QTextEdit {
            border: 1px solid #424242;
            border-radius: 4px;
            padding: 8px;
            background-color: #1E1E1E;
            color: #ffffff;
        }
        
        QTextEdit:focus {
            border: 2px solid #BB86FC;
        }
        
        QScrollArea {
            border: 1px solid #424242;
            border-radius: 4px;
            background-color: #1E1E1E;
        }
        
        QStatusBar {
            background-color: #2C2C2C;
            color: #B0B0B0;
            border-top: 1px solid #424242;
        }
        
        QMenuBar {
            background-color: #1E1E1E;
            color: #ffffff;
            border-bottom: 1px solid #424242;
        }
        
        QMenuBar::item:selected {
            background-color: #383838;
        }
        
        QMenu {
            background-color: #1E1E1E;
            color: #ffffff;
            border: 1px solid #424242;
        }
        
        QMenu::item:selected {
            background-color: #383838;
        }
        
        QProgressBar {
            border: 1px solid #424242;
            border-radius: 4px;
            text-align: center;
            background-color: #2C2C2C;
            color: #ffffff;
        }
        
        QProgressBar::chunk {
            background-color: #BB86FC;
            border-radius: 3px;
        }
        """

    def get_current_theme(self) -> ThemeMode:
        """Get the current theme mode."""
        return self.current_theme

    def set_theme(self, theme: ThemeMode) -> None:
        """
        Set the application theme.

        Args:
            theme: Theme mode to apply
        """
        if theme != self.current_theme:
            self.current_theme = theme
            if self.settings:
                self._save_theme_settings()
            self._apply_theme()

    def toggle_theme(self) -> None:
        """Toggle between light and dark themes."""
        if self.current_theme == ThemeMode.LIGHT:
            self.set_theme(ThemeMode.DARK)
        elif self.current_theme == ThemeMode.DARK:
            self.set_theme(ThemeMode.LIGHT)
        else:
            # If system theme, switch to light
            self.set_theme(ThemeMode.LIGHT)

    def get_theme_name(self, theme: Optional[ThemeMode] = None) -> str:
        """
        Get display name for specified theme.

        Args:
            theme: Theme mode (uses current theme if None)

        Returns:
            Theme display name
        """
        if theme is None:
            theme = self._get_effective_theme()

        names = {ThemeMode.LIGHT: "Light Theme", ThemeMode.DARK: "Dark Theme", ThemeMode.SYSTEM: "System Default"}

        return names.get(theme, "Unknown Theme")

    def _get_effective_theme(self) -> ThemeMode:
        """Get the effective theme (resolves system theme)."""
        if self.current_theme == ThemeMode.SYSTEM:
            # Default to light theme instead of system theme
            return ThemeMode.LIGHT
        return self.current_theme

    def _apply_theme(self) -> None:
        """Apply the current theme to the application."""
        if not PYQT6_AVAILABLE:
            return

        try:
            # Import QApplication safely
            if not PYQT6_AVAILABLE:
                return

            from PyQt6.QtWidgets import QApplication  # type: ignore

            app = QApplication.instance()  # type: ignore
            if not app:
                return

            effective_theme = self._get_effective_theme()
            stylesheet = self._stylesheets.get(effective_theme, "")

            # Apply stylesheet to application (with type checking)
            if hasattr(app, "setStyleSheet"):
                app.setStyleSheet(stylesheet)  # type: ignore
        except Exception:
            # Ignore theme application errors
            pass

    def _load_theme_settings(self) -> None:
        """Load theme settings from persistent storage."""
        if not self.settings:
            return

        try:
            theme_value = self.settings.value("theme/mode", ThemeMode.SYSTEM.value)
            self.current_theme = ThemeMode(theme_value)
        except (ValueError, TypeError):
            self.current_theme = ThemeMode.SYSTEM

        # Apply the loaded theme
        self._apply_theme()

    def _save_theme_settings(self) -> None:
        """Save theme settings to persistent storage."""
        if self.settings:
            self.settings.setValue("theme/mode", self.current_theme.value)

    def get_available_themes(self) -> List[ThemeMode]:
        """Get list of available theme modes."""
        return list(ThemeMode)


class SettingsManager:
    """
    Simple settings manager for Win Sayver GUI.

    Manages application configuration and user preferences.
    """

    def __init__(self, organization: str = "WinSayver", application: str = "WinSayver"):
        """
        Initialize settings manager.

        Args:
            organization: Organization name for settings
            application: Application name for settings
        """
        # Initialize settings if PyQt6 is available
        if PYQT6_AVAILABLE:
            try:
                from PyQt6.QtCore import QSettings

                self.settings = QSettings(organization, application)
            except ImportError:
                self.settings = None
        else:
            self.settings = None

        # Initialize theme manager
        self.theme_manager = SimpleThemeManager(self.settings)

        # Default settings
        self._defaults = {
            "ai/api_key": "",
            "ai/model": "gemini-2.5-pro",
            "ai/thinking_budget": "AUTO",
            "ai/enable_streaming": True,
            "ui/last_directory": str(Path.home()),
            "analysis/auto_collect_specs": True,
            "analysis/save_results": True,
            "analysis/results_directory": str(Path.home() / "WinSayver_Results"),
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get setting value.

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value
        """
        if default is None:
            default = self._defaults.get(key)

        if self.settings:
            return self.settings.value(key, default)
        else:
            return default

    def set(self, key: str, value: Any) -> None:
        """
        Set setting value.

        Args:
            key: Setting key
            value: Setting value
        """
        if self.settings:
            self.settings.setValue(key, value)

    def sync(self) -> None:
        """Synchronize settings to persistent storage."""
        if self.settings:
            self.settings.sync()

    def get_all_keys(self) -> List[str]:
        """Get all setting keys."""
        if self.settings:
            return self.settings.allKeys()
        else:
            return list(self._defaults.keys())
