#!/usr/bin/env python3
"""
Win Sayver - Main GUI Application
=================================

Professional PyQt6 desktop interface for AI-powered Windows troubleshooting.
Supports multiple image analysis, error description input, and real-time
AI analysis with Gemini 2.5 Pro thinking capabilities.
"""

import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from PyQt6.QtCore import QPoint, QSettings, QSize, Qt, QThread, QTimer, pyqtSignal
    from PyQt6.QtGui import QAction, QFont, QFontMetrics, QIcon, QPalette, QPixmap
    from PyQt6.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMenuBar,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSplitter,
        QStatusBar,
        QTabWidget,
        QTextBrowser,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

# PyQt6 imports
try:
    from PyQt6.QtCore import QPoint, QSettings, QSize, Qt, QThread, QTimer, pyqtSignal
    from PyQt6.QtGui import QAction, QFont, QFontMetrics, QIcon, QPalette, QPixmap
    from PyQt6.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMenuBar,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSplitter,
        QStatusBar,
        QTabWidget,
        QTextBrowser,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    print("❌ PyQt6 not available. Install with: pip install PyQt6")

from ai_client import AIClient
from api_key_dialog import APIKeyDialog
from image_widgets import MultiImageDropArea
from prompt_engineer import PromptEngineer
from responsive_system_info import ResponsiveSystemInfoWidget
from security_manager import SecurityManager
from specs_collector import SystemSpecsCollector
from system_data_manager import SystemDataManager
from theme_manager import SettingsManager, ThemeMode

# Win Sayver imports
from utils import ErrorHandler, PerformanceTimer, WinSayverError, safe_execute


class CustomQTextBrowser(QTextBrowser):  # type: ignore
    """
    Custom QTextBrowser that prevents default URL loading for ms-settings URLs.

    This fixes the issue where clicking ms-settings URLs causes the text to disappear
    because QTextBrowser tries to load them as documents and fails.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # PROVEN SOLUTION: Disable automatic link navigation while keeping anchorClicked signal
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        # Now we handle ALL links manually via anchorClicked signal

    def setSource(self, name, type=None) -> None:
        """
        Override setSource to prevent loading ms-settings URLs as documents.

        Args:
            name: QUrl object representing the source to load
            type: Optional type parameter (for PyQt6 compatibility)
        """
        try:
            url_string = name.toString() if hasattr(name, "toString") else str(name)

            # Prevent loading ms-settings URLs as documents (they're not documents)
            if url_string.startswith("ms-settings:"):
                # Do nothing - let the anchorClicked signal handler deal with it
                # This prevents QTextBrowser from trying to load the URL and clearing content
                logging.getLogger(__name__).info(
                    f"CustomQTextBrowser: Blocked setSource for ms-settings URL: {url_string}"
                )
                return

            # For all other URLs, use the default behavior
            super().setSource(name, type)

        except Exception as e:
            # If anything goes wrong, just don't clear the content
            logging.getLogger(__name__).warning(f"setSource error for {name}: {e}")
            return

    def loadResource(self, type, name):
        """
        Override loadResource to prevent loading ms-settings URLs as resources.

        Args:
            type: Resource type
            name: QUrl object representing the resource to load
        """
        try:
            url_string = name.toString() if hasattr(name, "toString") else str(name)

            # Prevent loading ms-settings URLs as resources
            if url_string.startswith("ms-settings:"):
                logging.getLogger(__name__).info(
                    f"CustomQTextBrowser: Blocked loadResource for ms-settings URL: {url_string}"
                )
                return None

            # For all other URLs, use the default behavior
            return super().loadResource(type, name)

        except Exception as e:
            logging.getLogger(__name__).warning(f"loadResource error for {name}: {e}")
            return None

    def mousePressEvent(self, ev):
        """
        Override mouse press event to handle URL clicks more directly.
        """
        try:
            # Check if event is valid
            if not ev:
                super().mousePressEvent(ev)
                return

            # Get the cursor position and check if we're clicking on a link
            cursor = self.cursorForPosition(ev.pos())
            char_format = cursor.charFormat()

            if char_format.isAnchor():
                # We're clicking on a link - get the URL
                url = char_format.anchorHref()
                if url and url.startswith("ms-settings:"):
                    # Emit the anchorClicked signal directly and don't call parent
                    from PyQt6.QtCore import QUrl

                    self.anchorClicked.emit(QUrl(url))
                    return  # Don't call parent to prevent default handling

            # For non-ms-settings links or non-link clicks, use default behavior
            super().mousePressEvent(ev)

        except Exception as e:
            logging.getLogger(__name__).warning(f"mousePressEvent error: {e}")
            super().mousePressEvent(ev)


class GUIError(Exception):
    """Raised when GUI operations fail."""

    pass


class SystemSpecsWorker(QThread):  # type: ignore
    """Background worker thread for system specs collection."""

    # Signals
    specs_collected = pyqtSignal(dict)  # type: ignore  # System specs data
    collection_failed = pyqtSignal(str)  # type: ignore  # Error message
    progress_updated = pyqtSignal(str)  # type: ignore  # Progress message

    def __init__(self, specs_collector):
        super().__init__()
        self.specs_collector = specs_collector

    def run(self) -> None:
        """Run system specs collection in background."""
        try:
            self.progress_updated.emit("Starting system analysis...")

            with PerformanceTimer("Background system specs collection") as timer:
                if self.specs_collector:
                    system_specs = self.specs_collector.collect_all_specs()

                    self.progress_updated.emit(f"Collection completed ({timer.duration:.2f}s)")
                    self.specs_collected.emit(system_specs)
                else:
                    self.collection_failed.emit("System specs collector not initialized")

        except Exception as e:
            self.collection_failed.emit(f"System specs collection failed: {e}")


class WinSayverMainWindow(QMainWindow):  # type: ignore
    """
    Main application window for Win Sayver GUI.

    Provides a professional desktop interface for AI-powered Windows
    troubleshooting with multi-image support and real-time analysis.
    """

    @staticmethod
    def _format_markdown(text: str) -> str:
        """
        Convert markdown formatting to HTML for both **bold** and [text](url) links.
        Also converts plain URLs to clickable links with proper HTML escaping for security.

        Args:
            text: Input text with markdown formatting and/or plain URLs

        Returns:
            Text with HTML formatting for bold and clickable links, properly escaped
        """
        import html

        # Handle edge cases
        if not text or not isinstance(text, str):
            return str(text) if text is not None else ""

        # First, escape HTML to prevent XSS attacks
        escaped_text = html.escape(text)

        # Then process markdown links [text](url) -> <a href="url">text</a>
        # Use regex to match [text](url) format on escaped text
        link_pattern = r"\[([^\]]+?)\]\(([^\)]+?)\)"

        def replace_markdown_link(match):
            link_text = match.group(1)
            url = match.group(2)

            # Handle Windows settings URLs (ms-settings://)
            if url.startswith("ms-settings:"):
                # Windows settings URLs are safe and should be handled by the system
                escaped_url = url.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
                return f'<a href="{escaped_url}" style="color: #0066cc; text-decoration: underline; font-weight: bold;">{link_text}</a>'

            # Validate URL scheme for security - only allow HTTP(S)
            if not (url.startswith("http://") or url.startswith("https://")):
                # Return as plain text if not a valid HTTP(S) URL
                return f"[{link_text}]({url})"
            # Additional security: reject any URL containing dangerous patterns
            if "javascript:" in url.lower() or "data:" in url.lower() or "vbscript:" in url.lower():
                return f"[{link_text}]({url})"
            # Escape only critical characters for href attribute
            escaped_url = url.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
            return f'<a href="{escaped_url}" style="color: #0066cc; text-decoration: underline;">{link_text}</a>'

        formatted_text = re.sub(link_pattern, replace_markdown_link, escaped_text)

        # Process standalone URLs with security validation
        url_pattern = r'((?:https?|ms-settings)://[^\s<>"()]+|ms-settings:[^\s<>"()]+)'

        def replace_url(match):
            url = match.group(1)

            # Handle Windows settings URLs specially
            if url.startswith("ms-settings:"):
                # Clean trailing punctuation from URL for proper href
                clean_url = url.rstrip(".,;!?")
                # Windows settings URLs are safe and should be handled by the system
                escaped_clean_url = clean_url.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
                return f'<a href="{escaped_clean_url}" style="color: #0066cc; text-decoration: underline; font-weight: bold;">{url}</a>'

            # Handle HTTP(S) URLs
            # Clean trailing punctuation from URL for proper href
            clean_url = url.rstrip(".,;!?")
            # Additional security: validate URL format and reject dangerous patterns
            if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
                return url  # Return original if not valid
            if "javascript:" in clean_url.lower() or "data:" in clean_url.lower() or "vbscript:" in clean_url.lower():
                return url  # Return original if contains dangerous patterns
            # Escape the URL for href attribute (only escape quotes and angle brackets)
            # Don't double-escape ampersands since they're already properly formatted
            escaped_clean_url = clean_url.replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
            return f'<a href="{escaped_clean_url}" style="color: #0066cc; text-decoration: underline;">{url}</a>'

        # Apply URL pattern to text that doesn't already contain anchor tags
        # Split by existing anchor tags and only process non-anchor parts
        parts = re.split(r"(<a[^>]*>.*?</a>)", formatted_text)
        for i in range(len(parts)):
            if not parts[i].startswith("<a"):
                parts[i] = re.sub(url_pattern, replace_url, parts[i])
        formatted_text = "".join(parts)

        # Finally, process bold formatting **text** -> <b>text</b>
        # Use regex to match **content** where content doesn't contain **
        bold_pattern = r"\*\*([^*]+?)\*\*"
        formatted_text = re.sub(bold_pattern, r"<b>\1</b>", formatted_text)

        return formatted_text

    @staticmethod
    def _format_markdown_bold(text: str) -> str:
        """
        Legacy method for backward compatibility. Use _format_markdown() instead.

        Args:
            text: Input text with markdown formatting

        Returns:
            Text with HTML formatting
        """
        return WinSayverMainWindow._format_markdown(text)

    def _handle_url_click(self, url) -> None:
        """
        Handle ALL URL clicks manually with smart fallback system.

        This provides complete control over URL handling, prevents text clearing,
        and implements fallback URLs for problematic Windows settings.

        Args:
            url: QUrl object representing the clicked URL
        """
        try:
            url_string = url.toString()

            # Decode URL encoding to handle cases like recovery%60 -> recovery
            import urllib.parse

            url_string = urllib.parse.unquote(url_string)

            self.logger.debug(f"URL clicked: {url_string}")

            # Handle Windows settings URLs with fallback system
            if url_string.startswith("ms-settings:"):
                self._handle_windows_settings_url(url_string)

            # Handle HTTP(S) URLs
            elif url_string.startswith(("http://", "https://")):
                from PyQt6.QtCore import QUrl  # type: ignore
                from PyQt6.QtGui import QDesktopServices  # type: ignore

                success = QDesktopServices.openUrl(QUrl(url_string))
                status_bar = self.statusBar()
                if success:
                    self.logger.info(f"Successfully opened URL: {url_string}")
                    if status_bar:
                        status_bar.showMessage(f"Opened: {url_string}")
                else:
                    self.logger.warning(f"Failed to open URL: {url_string}")
                    if status_bar:
                        status_bar.showMessage(f"Failed to open: {url_string}")

            else:
                self.logger.warning(f"Unsupported URL scheme: {url_string}")
                status_bar = self.statusBar()
                if status_bar:
                    status_bar.showMessage(f"Unsupported URL: {url_string}")

        except Exception as e:
            self.logger.error(f"Error handling URL click: {e}")
            status_bar = self.statusBar()
            if status_bar:
                status_bar.showMessage(f"Error opening URL: {e}")

    def _handle_windows_settings_url(self, url_string: str) -> None:
        """
        Handle Windows settings URLs with intelligent fallback system.

        Args:
            url_string: The ms-settings URL to open
        """
        from PyQt6.QtCore import QUrl  # type: ignore
        from PyQt6.QtGui import QDesktopServices  # type: ignore
        from windows_settings_urls import validate_and_get_alternatives

        # Get primary URL and fallback alternatives
        url_alternatives = validate_and_get_alternatives(url_string)

        # If no alternatives found, just try the original
        if not url_alternatives:
            url_alternatives = [url_string]

        success = False
        tried_urls = []

        # Try each URL alternative until one works
        for attempt_url in url_alternatives:
            tried_urls.append(attempt_url)

            try:
                clean_url = QUrl(attempt_url)
                success = QDesktopServices.openUrl(clean_url)

                if success:
                    self.logger.info(f"Successfully opened Windows settings: {attempt_url}")

                    # Show appropriate status message
                    if attempt_url == url_string:
                        # Primary URL worked
                        status_bar = self.statusBar()
                        if status_bar:
                            status_bar.showMessage(
                                f"Opened Windows settings: {attempt_url.replace('ms-settings:', '')}"
                            )
                    else:
                        # Fallback URL worked
                        setting_name = attempt_url.replace("ms-settings:", "")
                        status_bar = self.statusBar()
                        if status_bar:
                            status_bar.showMessage(f"Opened Windows settings: {setting_name} (using alternative URL)")

                        # Log the fallback usage for future improvement
                        self.logger.info(f"Primary URL {url_string} failed, succeeded with fallback: {attempt_url}")

                    break  # Success, no need to try more URLs

                else:
                    self.logger.debug(f"Failed to open: {attempt_url}")

            except Exception as e:
                self.logger.debug(f"Exception opening {attempt_url}: {e}")
                continue

        # If all URLs failed, show comprehensive error message
        if not success:
            self.logger.warning(f"All Windows settings URLs failed. Tried: {tried_urls}")

            # Provide helpful error message with manual instructions
            setting_name = url_string.replace("ms-settings:", "").replace("-", " ").title()
            error_msg = (
                f"Could not open {setting_name} automatically. "
                f"Please open Windows Settings (Win+I) and navigate to {setting_name} manually."
            )

            status_bar = self.statusBar()
            if status_bar:
                status_bar.showMessage(error_msg)

            # Show a more detailed message in a tooltip or status for debugging
            if self.logger.isEnabledFor(logging.DEBUG):
                status_bar = self.statusBar()
                if status_bar:
                    status_bar.setToolTip(f"Tried URLs: {', '.join(tried_urls)}")

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # Initialize logging
        self.logger = logging.getLogger(__name__)

        # Initialize settings and theme manager
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.settings
        self.theme_manager = self.settings_manager.theme_manager

        # Initialize core components
        self.specs_collector = None
        self.ai_client = None
        self.prompt_engineer = None
        self.security_manager = None
        self.system_data_manager = None
        self.responsive_system_info = None

        # Initialize UI state
        self.selected_images = []
        self.system_specs = {}
        self.analysis_results = {}

        # Initialize fallback model tracking
        self._active_fallback_model: Optional[str] = None

        # Initialize background workers
        self._specs_worker: Optional[QThread] = None  # type: ignore

        # Setup UI
        self._setup_ui()
        self._setup_connections()
        self._load_settings()

        # Initialize components
        self._initialize_components()

        self.logger.info("Win Sayver GUI initialized successfully")

    def _setup_ui(self) -> None:
        """Setup the main user interface."""
        try:
            # Set window properties
            self.setWindowTitle("Win Sayver - AI-Powered Windows Troubleshooting")
            self.setMinimumSize(1200, 800)
            self.resize(1400, 900)

            # Set window icon (placeholder for now)
            # TODO: Add proper application icon

            # Create central widget
            central_widget = QWidget()  # type: ignore
            self.setCentralWidget(central_widget)

            # Create main layout
            main_layout = QVBoxLayout(central_widget)  # type: ignore
            main_layout.setContentsMargins(10, 10, 10, 10)
            main_layout.setSpacing(10)

            # Create header section
            header_widget = self._create_header_section()
            main_layout.addWidget(header_widget)

            # Create main content area with tabs
            content_widget = self._create_content_section()
            main_layout.addWidget(content_widget, 1)  # Stretch factor 1

            # Create status bar
            self.statusBar().showMessage("Ready - Welcome to Win Sayver")  # type: ignore

            # Create menu bar
            self._create_menu_bar()

            self.logger.debug("UI setup completed successfully")

        except Exception as e:
            self.logger.error(f"Failed to setup UI: {e}")
            raise GUIError(f"UI setup failed: {e}")

    def _create_header_section(self) -> QWidget:
        """Create the header section with title and quick actions."""
        header_widget = QFrame()  # type: ignore
        header_widget.setFrameStyle(QFrame.Shape.StyledPanel)  # type: ignore
        header_widget.setMaximumHeight(80)

        header_layout = QHBoxLayout(header_widget)  # type: ignore
        header_layout.setContentsMargins(15, 10, 15, 10)

        # Title and description
        title_layout = QVBoxLayout()  # type: ignore

        title_label = QLabel("Win Sayver")  # type: ignore
        title_font = QFont()  # type: ignore
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)

        subtitle_label = QLabel("AI-Powered Windows Troubleshooting Assistant")  # type: ignore
        subtitle_font = QFont()  # type: ignore
        subtitle_font.setPointSize(10)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: #666666;")

        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        title_layout.addStretch()

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # Quick action buttons
        self.collect_specs_btn = QPushButton("🔍 Collect System Specs")  # type: ignore
        self.collect_specs_btn.setMinimumHeight(35)
        self.collect_specs_btn.setToolTip("Collect current system specifications")

        self.analyze_btn = QPushButton("🤖 Start AI Analysis")  # type: ignore
        self.analyze_btn.setMinimumHeight(35)
        self.analyze_btn.setEnabled(False)  # Disabled until images/text provided
        self.analyze_btn.setToolTip("Start AI-powered error analysis")

        header_layout.addWidget(self.collect_specs_btn)
        header_layout.addWidget(self.analyze_btn)

        return header_widget

    def _create_content_section(self) -> QWidget:
        """Create the main content area with tabs."""
        # Create tab widget
        self.tab_widget = QTabWidget()  # type: ignore
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)  # type: ignore

        # Tab 1: Analysis Setup
        setup_tab = self._create_analysis_setup_tab()
        self.tab_widget.addTab(setup_tab, "📝 Analysis Setup")

        # Tab 2: System Information
        system_tab = self._create_system_info_tab()
        self.tab_widget.addTab(system_tab, "🖥️ System Info")

        # Tab 3: Results & Solutions
        results_tab = self._create_results_tab()
        self.tab_widget.addTab(results_tab, "📊 Results")

        # Tab 4: Settings
        settings_tab = self._create_settings_tab()
        self.tab_widget.addTab(settings_tab, "⚙️ Settings")

        return self.tab_widget

    def _create_analysis_setup_tab(self) -> QWidget:
        """Create the analysis setup tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Image selection section with professional drag & drop
        image_group = QGroupBox("📸 Error Screenshots")  # type: ignore
        image_layout = QVBoxLayout(image_group)  # type: ignore

        # Professional multi-image drop area
        self.image_drop_area = MultiImageDropArea()
        self.image_drop_area.images_added.connect(self._on_images_added)
        self.image_drop_area.images_removed.connect(self._on_images_removed)
        self.image_drop_area.selection_changed.connect(self._on_image_selection_changed)

        image_layout.addWidget(self.image_drop_area)
        layout.addWidget(image_group)

        # Error description section
        description_group = QGroupBox("📝 Error Description")  # type: ignore
        description_layout = QVBoxLayout(description_group)  # type: ignore

        # Error description text editor
        self.error_description = QTextEdit()  # type: ignore
        self.error_description.setMinimumHeight(150)
        self.error_description.setPlaceholderText(
            "Describe the error you're experiencing:\n"
            "• What were you doing when the error occurred?\n"
            "• What error message did you see?\n"
            "• What application or system component was affected?\n"
            "• Any other relevant details..."
        )
        description_layout.addWidget(self.error_description)

        layout.addWidget(description_group)

        # Enhanced progress section with intelligent feedback
        progress_group = QGroupBox("📊 Analysis Progress")  # type: ignore
        progress_layout = QVBoxLayout(progress_group)  # type: ignore

        # Smart progress bar with model awareness
        self.progress_bar = QProgressBar()  # type: ignore
        self.progress_bar.setVisible(False)

        # Enhanced progress label with timing
        self.progress_label = QLabel("Ready to analyze")  # type: ignore
        self.progress_label.setStyleSheet("color: #666666;")

        # Model status and timing info
        status_layout = QHBoxLayout()  # type: ignore

        self.model_status_label = QLabel("")  # type: ignore
        self.model_status_label.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self.model_status_label)

        status_layout.addStretch()

        self.timing_info_label = QLabel("")  # type: ignore
        self.timing_info_label.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self.timing_info_label)

        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addLayout(status_layout)

        layout.addWidget(progress_group)

        return tab_widget

    def _create_system_info_tab(self) -> QWidget:
        """Create the system information tab with modern responsive design."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create responsive system info widget
        self.responsive_system_info = ResponsiveSystemInfoWidget()

        # Connect signals
        self.responsive_system_info.refresh_requested.connect(self.collect_system_specs)

        # Add to layout
        layout.addWidget(self.responsive_system_info)

        return tab_widget

    def _create_results_tab(self) -> QWidget:
        """Create the results and solutions tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(15, 15, 15, 15)

        # Results display - Use custom QTextBrowser subclass for better URL handling
        self.results_text = CustomQTextBrowser()  # type: ignore
        self.results_text.setReadOnly(True)
        self.results_text.setAcceptRichText(True)  # Enable HTML formatting
        self.results_text.setOpenExternalLinks(False)  # Disable default external links to handle custom URLs

        # Additional protection: disconnect any default URL handling like in test
        try:
            self.results_text.sourceChanged.disconnect()
        except:
            pass  # No connections to disconnect

        # Connect custom URL handler for Windows settings URLs
        self.results_text.anchorClicked.connect(self._handle_url_click)

        self.results_text.setPlaceholderText(
            "AI analysis results will appear here after processing.\n"
            "Complete the Analysis Setup and click 'Start AI Analysis' to begin."
        )

        layout.addWidget(self.results_text)

        return tab_widget

    def _create_settings_tab(self) -> QWidget:
        """Create the settings tab with functional AI and theme controls."""
        tab_widget = QWidget()  # type: ignore
        layout = QVBoxLayout(tab_widget)  # type: ignore
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Import and use AI configuration panel
        try:
            from ai_config_panel import AIConfigurationPanel

            # AI Configuration Panel (replaces static labels)
            self.ai_config_panel = AIConfigurationPanel()
            self.ai_config_panel.configuration_changed.connect(self._on_ai_config_changed)
            layout.addWidget(self.ai_config_panel)

        except ImportError as e:
            self.logger.warning(f"Could not import AIConfigurationPanel: {e}")
            # Fallback to basic AI configuration
            ai_group = QGroupBox("🤖 AI Configuration")  # type: ignore
            ai_layout = QGridLayout(ai_group)  # type: ignore

            # API Key setting
            ai_layout.addWidget(QLabel("API Key:"), 0, 0)  # type: ignore
            self.api_key_label = QLabel("Not configured")  # type: ignore
            self.api_key_label.setStyleSheet("color: #ff6b6b;")
            ai_layout.addWidget(self.api_key_label, 0, 1)

            self.set_api_key_btn = QPushButton("Set API Key")  # type: ignore
            ai_layout.addWidget(self.set_api_key_btn, 0, 2)

            layout.addWidget(ai_group)

        # Theme Configuration (replaces static label)
        theme_group = QGroupBox("🎨 Theme Settings")  # type: ignore
        theme_layout = QFormLayout(theme_group)  # type: ignore

        # Theme selection dropdown
        self.theme_combo = QComboBox()  # type: ignore
        self.theme_combo.addItem("💡 Light Theme", "light")
        self.theme_combo.addItem("🌙 Dark Theme", "dark")
        self.theme_combo.addItem("🖥️ System Default", "system")
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_layout.addRow("Theme:", self.theme_combo)

        # Theme status label
        self.theme_status_label = QLabel("Current theme: System Default")  # type: ignore
        self.theme_status_label.setStyleSheet("color: #666; font-size: 11px;")
        theme_layout.addRow("", self.theme_status_label)

        layout.addWidget(theme_group)

        # Load current theme selection
        self._load_theme_selection()

        layout.addStretch()

        return tab_widget

    def _create_menu_bar(self) -> None:
        """Create the application menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")  # type: ignore

        # Open images action
        open_action = QAction("&Open Images...", self)  # type: ignore
        open_action.setShortcut("Ctrl+O")
        open_action.setToolTip("Open error screenshot images")
        open_action.triggered.connect(self._select_images_dialog)
        file_menu.addAction(open_action)  # type: ignore

        file_menu.addSeparator()  # type: ignore

        # Exit action
        exit_action = QAction("E&xit", self)  # type: ignore
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self._on_exit)
        file_menu.addAction(exit_action)  # type: ignore

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")  # type: ignore

        # Collect specs action
        collect_action = QAction("&Collect System Specs", self)  # type: ignore
        collect_action.setShortcut("Ctrl+S")
        collect_action.triggered.connect(self.collect_system_specs)
        tools_menu.addAction(collect_action)  # type: ignore

        # Analyze action
        analyze_action = QAction("&Start Analysis", self)  # type: ignore
        analyze_action.setShortcut("Ctrl+A")
        analyze_action.triggered.connect(self.start_analysis)
        tools_menu.addAction(analyze_action)  # type: ignore

        # Help menu
        help_menu = menubar.addMenu("&Help")  # type: ignore

        # About action
        about_action = QAction("&About Win Sayver", self)  # type: ignore
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)  # type: ignore

    def _setup_connections(self) -> None:
        """Setup signal-slot connections."""
        # Button connections
        self.collect_specs_btn.clicked.connect(self.collect_system_specs)
        self.analyze_btn.clicked.connect(self.start_analysis)

        # Only connect API key button if it exists (fallback mode)
        if hasattr(self, "set_api_key_btn"):
            self.set_api_key_btn.clicked.connect(self.set_api_key)

        # Text change connections
        self.error_description.textChanged.connect(self.update_analysis_ready_state)

        # Connect AI config panel signals if it exists
        if hasattr(self, "ai_config_panel"):
            # The configuration_changed signal is already connected in _create_settings_tab
            # Also connect for fallback model tracking
            self.ai_config_panel.configuration_changed.connect(self._on_ai_config_changed)
            pass

        # Connect theme combo if it exists
        if hasattr(self, "theme_combo"):
            # The currentTextChanged signal is already connected in _create_settings_tab
            pass

    def _on_ai_config_changed(self, config) -> None:
        """Handle AI configuration changes and clear fallback if user manually changes model."""
        try:
            # If user manually changes the model, clear any active fallback
            if (
                hasattr(self, "_active_fallback_model")
                and self._active_fallback_model
                and config.model != self._active_fallback_model
            ):
                self.logger.info(
                    f"User manually changed model from {self._active_fallback_model} to {config.model}, clearing fallback"
                )
                self._active_fallback_model = None

            # Update AI client with new configuration if available
            if hasattr(self, "ai_client") and self.ai_client and config.api_key:
                self.ai_client.model_name = config.model
                self.ai_client.thinking_budget = config.thinking_budget
                self.ai_client.enable_streaming = config.enable_streaming

                self.logger.info(f"AI configuration updated: model={config.model}, thinking={config.thinking_budget}")
                self.statusBar().showMessage(f"AI model updated to {config.model}")  # type: ignore

        except Exception as e:
            self.logger.warning(f"Error handling AI config change: {e}")

    def _on_exit(self) -> None:
        """Handle exit action from menu."""
        self.close()

    def _on_theme_changed(self, theme_text: str) -> None:
        """Handle theme selection change."""
        try:
            # Get theme mode from combo box data
            theme_data = self.theme_combo.currentData()

            if hasattr(self, "settings_manager") and self.settings_manager:
                # Map theme data to ThemeMode
                from theme_manager import ThemeMode

                theme_map = {"light": ThemeMode.LIGHT, "dark": ThemeMode.DARK, "system": ThemeMode.SYSTEM}

                theme_mode = theme_map.get(theme_data, ThemeMode.SYSTEM)

                # Apply theme through settings manager
                self.settings_manager.theme_manager.set_theme(theme_mode)

                # Update status label
                theme_name = self.settings_manager.theme_manager.get_theme_name(theme_mode)
                self.theme_status_label.setText(f"Current theme: {theme_name}")

                self.logger.info(f"Theme changed to: {theme_name}")
                self.statusBar().showMessage(f"Theme changed to {theme_name}")  # type: ignore

        except Exception as e:
            self.logger.error(f"Failed to change theme: {e}")

    def _load_theme_selection(self) -> None:
        """Load and set current theme selection in the combo box."""
        try:
            if hasattr(self, "settings_manager") and self.settings_manager:
                current_theme = self.settings_manager.theme_manager.get_current_theme()

                # Map ThemeMode to combo box data
                theme_map = {"LIGHT": "light", "DARK": "dark", "SYSTEM": "system"}

                theme_data = theme_map.get(current_theme.name, "system")

                # Set combo box selection
                for i in range(self.theme_combo.count()):
                    if self.theme_combo.itemData(i) == theme_data:
                        self.theme_combo.setCurrentIndex(i)
                        break

                # Update status label
                theme_name = self.settings_manager.theme_manager.get_theme_name(current_theme)
                if hasattr(self, "theme_status_label"):
                    self.theme_status_label.setText(f"Current theme: {theme_name}")

        except Exception as e:
            self.logger.warning(f"Failed to load theme selection: {e}")

    def _load_settings(self) -> None:
        """Load application settings including theme and AI configuration."""
        try:
            # Restore window geometry
            geometry = self.settings.value("geometry")  # type: ignore
            if geometry:
                self.restoreGeometry(geometry)

            # Restore window state
            state = self.settings.value("windowState")  # type: ignore
            if state:
                self.restoreState(state)

            # Load AI configuration if AI config panel exists
            if hasattr(self, "ai_config_panel"):
                try:
                    # Load saved AI settings with quota-efficient defaults
                    model = self.settings.value("ai/model", "gemini-2.5-flash")  # type: ignore  # Use Flash as default for quota efficiency
                    thinking_budget = self.settings.value("ai/thinking_budget", "PRO")  # type: ignore
                    performance_mode = self.settings.value("ai/performance_mode", "balanced")  # type: ignore
                    enable_streaming = self.settings.value("ai/enable_streaming", True, type=bool)  # type: ignore
                    timeout_seconds = self.settings.value("ai/timeout_seconds", 60, type=int)  # type: ignore
                    max_retries = self.settings.value("ai/max_retries", 3, type=int)  # type: ignore

                    # Load active fallback model if saved
                    saved_fallback = self.settings.value("ai/active_fallback_model", "")  # type: ignore
                    if saved_fallback:
                        self._active_fallback_model = saved_fallback
                        self.logger.info(f"Loaded active fallback model: {saved_fallback}")

                    # Apply settings to AI config panel
                    from ai_config_panel import AIConfiguration

                    config = AIConfiguration(
                        model=model,
                        thinking_budget=thinking_budget,
                        performance_mode=performance_mode,
                        enable_streaming=enable_streaming,
                        timeout_seconds=timeout_seconds,
                        max_retries=max_retries,
                    )
                    self.ai_config_panel.set_configuration(config)

                except Exception as e:
                    self.logger.warning(f"Failed to load AI configuration: {e}")

            self.logger.debug("Settings loaded successfully")

        except Exception as e:
            self.logger.warning(f"Failed to load settings: {e}")

    def _save_settings(self) -> None:
        """Save application settings including theme and AI configuration."""
        try:
            self.settings.setValue("geometry", self.saveGeometry())  # type: ignore
            self.settings.setValue("windowState", self.saveState())  # type: ignore

            # Save theme settings through settings manager
            if hasattr(self, "settings_manager") and self.settings_manager:
                self.settings_manager.sync()

            # Save AI configuration if available
            if hasattr(self, "ai_config_panel"):
                try:
                    config = self.ai_config_panel.get_configuration()
                    # Save non-sensitive settings
                    self.settings.setValue("ai/model", config.model)  # type: ignore
                    self.settings.setValue("ai/thinking_budget", config.thinking_budget)  # type: ignore
                    self.settings.setValue("ai/performance_mode", config.performance_mode)  # type: ignore
                    self.settings.setValue("ai/enable_streaming", config.enable_streaming)  # type: ignore
                    self.settings.setValue("ai/timeout_seconds", config.timeout_seconds)  # type: ignore
                    self.settings.setValue("ai/max_retries", config.max_retries)  # type: ignore
                except Exception as e:
                    self.logger.warning(f"Failed to save AI configuration: {e}")

            # Save active fallback model if set
            if hasattr(self, "_active_fallback_model") and self._active_fallback_model:
                self.settings.setValue("ai/active_fallback_model", self._active_fallback_model)  # type: ignore
                self.logger.info(f"Saved active fallback model: {self._active_fallback_model}")
            else:
                # Clear any previously saved fallback
                self.settings.remove("ai/active_fallback_model")  # type: ignore

            self.logger.debug("Settings saved successfully")

        except Exception as e:
            self.logger.warning(f"Failed to save settings: {e}")

    def _initialize_components(self) -> None:
        """Initialize core Win Sayver components."""
        try:
            # Initialize security manager first
            self.security_manager = SecurityManager()

            # Initialize settings manager with theme support
            from theme_manager import SettingsManager

            self.settings_manager = SettingsManager()

            # Initialize system data manager
            self.system_data_manager = SystemDataManager()

            # Initialize system specs collector
            self.specs_collector = SystemSpecsCollector()

            # Try to load existing system specs
            self._load_existing_system_specs()

            # Initialize prompt engineer
            self.prompt_engineer = PromptEngineer()

            # Initialize AI client if API key is available
            self._initialize_ai_client()

            # Update API key status in UI
            self._update_api_key_status()

            self.logger.debug("Core components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            self.statusBar().showMessage(f"Component initialization failed: {e}")  # type: ignore

    def _on_images_added(self, file_paths: List[str]) -> None:
        """Handle images added to the drop area."""
        self.logger.info(f"Added {len(file_paths)} images")
        self.statusBar().showMessage(f"Added {len(file_paths)} images")  # type: ignore
        self.update_analysis_ready_state()

    def _on_images_removed(self, file_paths: List[str]) -> None:
        """Handle images removed from the drop area."""
        self.logger.info(f"Removed {len(file_paths)} images")
        self.statusBar().showMessage(f"Removed {len(file_paths)} images")  # type: ignore
        self.update_analysis_ready_state()

    def _on_image_selection_changed(self, count: int) -> None:
        """Handle image selection count change."""
        if count > 0:
            self.statusBar().showMessage(f"{count} images selected")  # type: ignore
        else:
            self.statusBar().showMessage("No images selected")  # type: ignore
        self.update_analysis_ready_state()

    def collect_system_specs(self) -> None:
        """Collect current system specifications in background thread."""
        try:
            # Check if already collecting
            if hasattr(self, "_specs_worker") and self._specs_worker and self._specs_worker.isRunning():
                self.logger.warning("System specs collection already in progress")
                return

            # Start background collection
            self._start_specs_collection()

        except Exception as e:
            self.logger.error(f"Failed to start system specs collection: {e}")
            QMessageBox.critical(self, "Error", f"Failed to start system specs collection: {e}")  # type: ignore

    def _start_specs_collection(self) -> None:
        """Start background system specs collection."""
        try:
            # Disable the button and show progress
            self.collect_specs_btn.setEnabled(False)
            self.collect_specs_btn.setText("🔄 Collecting...")
            self.statusBar().showMessage("Starting system analysis...")  # type: ignore

            # Show progress in the Analysis Setup tab if not already visible
            if hasattr(self, "progress_label"):
                self.progress_label.setText("Collecting system specifications...")

            # Create and configure worker thread
            self._specs_worker = SystemSpecsWorker(self.specs_collector)

            # Connect signals
            self._specs_worker.specs_collected.connect(self._on_specs_collected)
            self._specs_worker.collection_failed.connect(self._on_specs_collection_failed)
            self._specs_worker.progress_updated.connect(self._on_specs_progress_updated)
            self._specs_worker.finished.connect(self._on_specs_worker_finished)

            # Start the worker
            self._specs_worker.start()

        except Exception as e:
            self.logger.error(f"Failed to start specs worker: {e}")
            self._reset_specs_collection_ui()
            raise

    def _on_specs_collected(self, system_specs: Dict[str, Any]) -> None:
        """Handle successful system specs collection."""
        try:
            self.system_specs = system_specs

            # Save to persistent storage
            if self.system_data_manager:
                # Calculate collection duration from worker
                collection_duration = None
                if hasattr(self._specs_worker, "collection_duration"):
                    collection_duration = getattr(self._specs_worker, "collection_duration", None)

                success = self.system_data_manager.save_system_specs(
                    system_specs, collection_duration=collection_duration, collection_method="manual"
                )

                if success:
                    self.logger.info("System specs saved to persistent storage")
                else:
                    self.logger.warning("Failed to save system specs to storage")

            # Display in responsive system info widget
            if self.responsive_system_info:
                self.responsive_system_info.update_system_data(system_specs)

            # Update analysis ready state
            self.update_analysis_ready_state()

            self.logger.info("System specs collected successfully via background thread")

        except Exception as e:
            self.logger.error(f"Error processing collected specs: {e}")

    def _on_specs_collection_failed(self, error_message: str) -> None:
        """Handle failed system specs collection."""
        self.logger.error(f"System specs collection failed: {error_message}")
        QMessageBox.critical(self, "Collection Error", f"System specs collection failed:\n{error_message}")  # type: ignore
        self.statusBar().showMessage("System specs collection failed")  # type: ignore

    def _on_specs_progress_updated(self, progress_message: str) -> None:
        """Handle progress updates from specs collection."""
        self.statusBar().showMessage(progress_message)  # type: ignore

    def _on_specs_worker_finished(self) -> None:
        """Handle worker thread completion."""
        self._reset_specs_collection_ui()

    def _reset_specs_collection_ui(self) -> None:
        """Reset UI elements after specs collection."""
        self.collect_specs_btn.setEnabled(True)
        self.collect_specs_btn.setText("🔍 Collect System Specs")

        # Reset progress label if it exists
        if hasattr(self, "progress_label"):
            self.progress_label.setText("Ready to analyze")

    def start_analysis(self) -> None:
        """Start AI-powered error analysis."""
        try:
            if not self.ai_client:
                QMessageBox.warning(
                    self, "API Key Required", "Please set your Google Gemini API key in the Settings tab first."
                )
                self.tab_widget.setCurrentIndex(3)  # Switch to settings tab
                return

            self.statusBar().showMessage("Starting AI analysis...")  # type: ignore
            self.analyze_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            self.progress_label.setText("Analyzing with AI...")

            # Start real AI analysis workflow
            self._start_real_ai_analysis()

        except Exception as e:
            self.logger.error(f"Failed to start analysis: {e}")
            QMessageBox.critical(self, "Error", f"Failed to start analysis: {e}")  # type: ignore
            self._reset_analysis_ui()

    def _start_real_ai_analysis(self) -> None:
        """Start real AI analysis using the AI workflow system with enhanced fallback mechanisms."""
        try:
            # Import AI workflow components
            from ai_config_panel import AIConfiguration
            from ai_workflow import AIAnalysisWorker, AnalysisRequest

            # Get analysis inputs
            images = self.image_drop_area.get_selected_images()
            error_description = self.error_description.toPlainText().strip()

            # Validate inputs before proceeding
            if not error_description and not images:
                QMessageBox.warning(
                    self,
                    "Input Required",
                    "Please provide either an error description or upload error screenshots before starting analysis.",
                )
                self._reset_analysis_ui()
                return

            if not self.system_specs:
                QMessageBox.warning(
                    self,
                    "System Specs Required",
                    "Please collect system specifications first by clicking 'Collect Specs' in the System Info tab.",
                )
                self._reset_analysis_ui()
                return

            # Get AI configuration from settings with robust fallbacks
            settings = self.settings if self.settings else self.settings_manager.settings

            # Get API key with multiple fallback sources
            api_key = ""
            if settings:
                api_key = settings.value("ai/api_key", "")

            # Check for API key in environment variables as fallback
            if not api_key:
                import os

                api_key = os.getenv("GEMINI_API_KEY", "")
                if api_key:
                    self.logger.info("Using API key from environment variable")

            # Check if API key exists
            if not api_key:
                reply = QMessageBox.question(
                    self,
                    "API Key Required",
                    "Google Gemini API key is required for AI analysis.\n\n" "Would you like to configure it now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )

                if reply == QMessageBox.StandardButton.Yes:
                    self.tab_widget.setCurrentIndex(3)  # Switch to settings tab

                self._reset_analysis_ui()
                return

            # Configure AI with robust settings - Check for active fallback first
            if hasattr(self, "ai_config_panel") and self.ai_config_panel:
                try:
                    # Get current configuration from the UI panel
                    current_config = self.ai_config_panel.get_configuration()

                    # Check if there's an active fallback model we should use instead
                    effective_model = current_config.model
                    if hasattr(self, "_active_fallback_model") and self._active_fallback_model:
                        effective_model = self._active_fallback_model
                        self.logger.info(
                            f"Using active fallback model: {effective_model} (original: {current_config.model})"
                        )

                    ai_config = AIConfiguration(
                        api_key=api_key,
                        model=effective_model,  # Use fallback model if available
                        thinking_budget=current_config.thinking_budget,
                        enable_streaming=current_config.enable_streaming,
                        performance_mode=current_config.performance_mode,
                        timeout_seconds=current_config.timeout_seconds,
                        max_retries=current_config.max_retries,
                    )
                    self.logger.info(f"Using effective AI configuration: model={ai_config.model}")
                except Exception as e:
                    self.logger.warning(f"Failed to get current UI config, using settings fallback: {e}")
                    # Fallback to settings with improved defaults
                    ai_config = AIConfiguration(
                        api_key=api_key,
                        model=(
                            settings.value("ai/model", "gemini-2.5-flash") if settings else "gemini-2.5-flash"
                        ),  # Use Flash as default for quota efficiency
                        thinking_budget=str(settings.value("ai/thinking_budget", "AUTO")) if settings else "AUTO",
                        enable_streaming=bool(settings.value("ai/enable_streaming", True)) if settings else True,
                    )
            else:
                # Fallback to settings with improved defaults
                ai_config = AIConfiguration(
                    api_key=api_key,
                    model=(
                        settings.value("ai/model", "gemini-2.5-flash") if settings else "gemini-2.5-flash"
                    ),  # Use Flash as default for quota efficiency
                    thinking_budget=str(settings.value("ai/thinking_budget", "AUTO")) if settings else "AUTO",
                    enable_streaming=bool(settings.value("ai/enable_streaming", True)) if settings else True,
                )

            # Create enhanced analysis request
            request = AnalysisRequest(
                images=images, error_description=error_description, system_specs=self.system_specs, ai_config=ai_config
            )

            # Test AI connection before starting analysis with enhanced quota handling
            try:
                from ai_client import AIClient

                test_client = AIClient(api_key=ai_config.api_key, model_name=ai_config.model)

                # Quick connection test
                connection_result = test_client.test_connection()
                if not connection_result.get("success", False):
                    error_msg = connection_result.get("error", "Unknown connection error")
                    error_type = connection_result.get("error_type", "unknown")

                    # Handle quota exhaustion with automatic model fallback
                    if error_type == "quota_exceeded" or "429" in error_msg or "quota" in error_msg.lower():
                        self.logger.warning(f"Quota exhausted for {ai_config.model}, attempting fallback")

                        # Force mark current model as quota exhausted to ensure fallback works
                        test_client.fallback_manager.mark_quota_exhausted(ai_config.model)

                        # Get available models from fallback manager after marking quota exhausted
                        quota_status = test_client.get_quota_status()
                        available_models = quota_status.get("available_models", [])
                        recommended_model = quota_status.get("recommended_model")

                        # Log quota status for debugging
                        self.logger.info(
                            f"Quota status - Available models: {available_models}, Recommended: {recommended_model}"
                        )

                        if recommended_model and len(available_models) > 0:
                            # AUTOMATIC FALLBACK - No user confirmation needed
                            self.logger.info(
                                f"Auto-switching from {ai_config.model} to {recommended_model} due to quota exhaustion"
                            )

                            # Show informative notification instead of confirmation dialog
                            QMessageBox.information(
                                self,
                                "Auto Fallback Activated",
                                f"Your quota for {ai_config.model} has been exhausted.\n\n"
                                f"🔄 Automatically switching to {recommended_model}\n\n"
                                f"Available models: {', '.join(available_models)}\n\n"
                                "Note: Flash models have higher free tier limits.",
                                QMessageBox.StandardButton.Ok,
                            )

                            # Update configuration to use recommended model
                            ai_config.model = recommended_model
                            self.logger.info(f"Switched to fallback model: {recommended_model}")

                            # CRITICAL FIX: Update the analysis request to use the new model
                            # This ensures the AIAnalysisWorker uses the correct fallback model
                            # while preserving all original user context (images, prompts, system specs)
                            if request.ai_config:
                                request.ai_config.model = recommended_model
                                self.logger.info(f"Updated analysis request to use fallback model: {recommended_model}")

                            # Persist the fallback choice for future analyses
                            self._active_fallback_model = recommended_model
                            self.logger.info(f"Set active fallback model: {recommended_model}")

                            # Update UI to reflect the change
                            if hasattr(self, "ai_config_panel") and self.ai_config_panel:
                                try:
                                    current_config = self.ai_config_panel.get_configuration()
                                    current_config.model = recommended_model
                                    self.ai_config_panel.set_configuration(current_config)
                                    self.logger.info(
                                        f"Updated UI configuration to use fallback model: {recommended_model}"
                                    )
                                except Exception as e:
                                    self.logger.warning(f"Failed to update UI config: {e}")

                            # Test with new model
                            test_client = AIClient(api_key=ai_config.api_key, model_name=ai_config.model)
                            connection_result = test_client.test_connection()

                            if not connection_result.get("success", False):
                                error_msg = connection_result.get("error", "Fallback model also failed")
                                QMessageBox.critical(
                                    self,
                                    "Auto Fallback Failed",
                                    f"Connection failed even with fallback model {recommended_model}:\n\n{error_msg}\n\n"
                                    "All available models may be exhausted. Please try again later.",
                                )
                                self._reset_analysis_ui()
                                return
                        else:
                            # No fallback available
                            QMessageBox.critical(
                                self,
                                "Quota Exhausted - No Fallback Available",
                                f"Your quota for {ai_config.model} has been exhausted and no alternative models are available.\n\n"
                                "Please wait for quota reset or upgrade to a paid plan.\n\n"
                                "Visit: https://ai.google.dev/pricing",
                            )
                            self._reset_analysis_ui()
                            return
                    else:
                        # Other connection errors
                        QMessageBox.critical(
                            self,
                            "AI Connection Failed",
                            f"Unable to connect to Google Gemini API:\n\n{error_msg}\n\n"
                            "Please check your API key and internet connection.",
                        )
                        self._reset_analysis_ui()
                        return

                self.logger.info(f"AI connection test successful with model: {ai_config.model}")

            except Exception as e:
                self.logger.error(f"AI connection test failed: {e}")
                QMessageBox.critical(
                    self,
                    "AI Setup Error",
                    f"Failed to initialize AI client:\n\n{e}\n\n" "Please check your configuration and try again.",
                )
                self._reset_analysis_ui()
                return

            # Create and start analysis worker
            self.analysis_worker = AIAnalysisWorker(request)

            # Log context preservation for debugging
            self.logger.info(f"Creating AIAnalysisWorker with:")
            self.logger.info(f"  - Model: {request.ai_config.model if request.ai_config else 'None'}")
            self.logger.info(f"  - Images: {len(request.images)} files")
            self.logger.info(f"  - Error description: {bool(request.error_description)}")
            self.logger.info(f"  - System specs available: {bool(request.system_specs)}")

            # Connect signals with enhanced error handling
            self.analysis_worker.analysis_completed.connect(self._on_analysis_completed)
            self.analysis_worker.analysis_error.connect(self._on_analysis_error)
            self.analysis_worker.progress_updated.connect(self._on_progress_updated)
            self.analysis_worker.step_completed.connect(self._on_step_completed)

            # Start the analysis
            self.analysis_worker.start()
            self.logger.info(
                f"Started AI analysis with {len(images)} images and error description: {bool(error_description)}"
            )

        except ImportError as e:
            self.logger.error(f"Failed to import AI workflow components: {e}")
            QMessageBox.critical(
                self,
                "Component Error",
                f"AI analysis components are not available:\n\n{e}\n\n" "Please check the application installation.",
            )
            self._reset_analysis_ui()
        except Exception as e:
            self.logger.error(f"Failed to start AI analysis: {e}")
            QMessageBox.critical(
                self,
                "Analysis Error",
                f"Failed to start AI analysis:\n\n{e}\n\n" "Please check your configuration and try again.",
            )
            self._reset_analysis_ui()

    def _on_progress_updated(self, progress: int) -> None:
        """Handle progress updates."""
        self.progress_bar.setValue(progress)

    def _on_step_completed(self, step_name: str, success: bool, details: str) -> None:
        """Handle step completion updates."""
        if success:
            self.progress_label.setText(f"✅ {step_name} completed")
        else:
            self.progress_label.setText(f"❌ {step_name} failed: {details}")

    def _on_analysis_completed(self, result) -> None:
        """Handle analysis completion with real results."""
        try:
            self.progress_bar.setVisible(False)
            self.progress_label.setText("Analysis complete")
            self.analyze_btn.setEnabled(True)

            # Debug logging to see what result we're actually displaying
            summary = getattr(result, "problem_summary", "No summary")[:100]
            metadata = getattr(result, "metadata", {})
            primary_source = metadata.get("primary_source", "unknown")
            self.logger.info(f"Displaying analysis result - Primary source: {primary_source}, Summary: {summary}...")

            # Format and display real AI results with bold formatting
            formatted_results = self._format_ai_results(result)
            # Apply markdown formatting (bold and links) and set as HTML
            html_results = self._format_markdown(formatted_results)
            self.results_text.setHtml(
                f"<pre style='white-space: pre-wrap; font-family: Consolas, Monaco, monospace;'>{html_results}</pre>"
            )
            self.tab_widget.setCurrentIndex(2)  # Switch to results tab

            # Update status
            confidence = result.confidence_score if hasattr(result, "confidence_score") else 0.0
            self.statusBar().showMessage(f"AI analysis completed - Confidence: {confidence:.1%}")  # type: ignore

        except Exception as e:
            self.logger.error(f"Failed to process analysis results: {e}")
            self._analysis_complete_with_error(f"Result processing failed: {e}")

    def _on_analysis_error(self, error_message: str) -> None:
        """Handle analysis errors."""
        self._analysis_complete_with_error(error_message)

    def _analysis_complete_with_error(self, error_message: str) -> None:
        """Complete analysis with error state."""
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Analysis failed")
        self.analyze_btn.setEnabled(True)

        error_result = f"""
❌ AI Analysis Failed

Error: {error_message}

🔧 **Troubleshooting Steps:**
1. **Check your Google Gemini API key** in Settings
2. **Ensure you have internet connectivity**
3. **Verify your API key has sufficient quota**
4. Try again with a simpler error description

**For help setting up your API key, visit:**
https://ai.google.dev/gemini-api/docs/api-key
        """

        # Apply markdown formatting (bold and links) to error result
        html_error_result = self._format_markdown(error_result)
        self.results_text.setHtml(
            f"<pre style='white-space: pre-wrap; font-family: Consolas, Monaco, monospace;'>{html_error_result}</pre>"
        )
        self.tab_widget.setCurrentIndex(2)  # Switch to results tab
        self.statusBar().showMessage("AI analysis failed")  # type: ignore

    def _format_ai_results(self, result) -> str:
        """Format AI analysis results for display with enhanced intelligence."""
        try:
            if not hasattr(result, "success") or not result.success:
                return f"""❌ AI Analysis Failed

Error: {getattr(result, 'error_message', 'Unknown error')}

🔧 Troubleshooting Steps:
1. Check your Google Gemini API key in Settings
2. Ensure you have internet connectivity
3. Verify your API key has sufficient quota
4. Try again with a simpler error description

For help setting up your API key, visit:
https://ai.google.dev/gemini-api/docs/api-key"""

            # Extract result data with enhanced intelligence
            confidence = getattr(result, "confidence_score", 0.0)
            problem_summary = getattr(result, "problem_summary", "No summary available")
            solutions = getattr(result, "solutions", [])
            risk_assessment = getattr(result, "risk_assessment", "Risk assessment unavailable")
            thinking_process = getattr(result, "thinking_process", [])
            metadata = getattr(result, "metadata", {})

            # Determine confidence level description
            if confidence >= 0.9:
                confidence_desc = "Very High - Strong evidence supports this diagnosis"
                confidence_icon = "🎯"
            elif confidence >= 0.75:
                confidence_desc = "High - Good evidence supports this diagnosis"
                confidence_icon = "🎯"
            elif confidence >= 0.6:
                confidence_desc = "Moderate - Some uncertainty in diagnosis"
                confidence_icon = "⚠️"
            else:
                confidence_desc = "Low - Limited evidence, proceed with caution"
                confidence_icon = "⚠️"

            # Format enhanced results
            formatted = f"""🤖 Windows Troubleshooting Analysis - Powered by Google Gemini
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{confidence_icon} CONFIDENCE SCORE: {confidence:.1%}
{confidence_desc}

📋 EXPERT PROBLEM ANALYSIS:
{problem_summary}

💡 RECOMMENDED SOLUTIONS (Priority Order):
"""

            # Add enhanced solutions with better formatting
            if solutions:
                for i, solution in enumerate(solutions[:5], 1):  # Show top 5 solutions
                    title = solution.get("title", f"Solution {i}")
                    description = solution.get("description", "No description available")
                    priority = solution.get("priority", "normal")
                    risk_level = solution.get("risk_level", "unknown")
                    estimated_time = solution.get("estimated_time", "Unknown")
                    admin_required = solution.get("admin_required", False)

                    # Format risk level with appropriate icons
                    risk_icon = (
                        "🟢" if risk_level.lower() == "low" else "🟡" if risk_level.lower() == "medium" else "🔴"
                    )
                    priority_icon = (
                        "🔥" if priority.lower() == "high" else "⭐" if priority.lower() == "medium" else "📋"
                    )
                    admin_icon = "🔐" if admin_required else ""

                    formatted += f"""\n{priority_icon} SOLUTION {i}: {title}
   Priority: {priority.upper()} | Risk: {risk_icon} {risk_level.upper()} | Time: {estimated_time} {admin_icon}
   
   📝 Description:
   {description}
"""

                    # Add specific commands if available with enhanced formatting
                    commands = solution.get("commands", [])
                    exact_commands = solution.get("exact_commands", [])

                    # Process enhanced exact_commands format first
                    if exact_commands:
                        formatted += "\n   💻 Commands to execute:\n\n"
                        for cmd_obj in exact_commands[:3]:  # Show up to 3 commands per solution
                            if isinstance(cmd_obj, dict):
                                command = cmd_obj.get("command", "")
                                explanation = cmd_obj.get("explanation", "")
                                expected_output = cmd_obj.get("expected_output", "")

                                formatted += f"   ▶️ **Command:**\n"
                                formatted += f"      `{command}`\n\n"
                                if explanation:
                                    formatted += f"   📝 **What it does:** {explanation}\n\n"
                                if expected_output:
                                    formatted += f"   ✅ **Expected result:** {expected_output}\n\n"
                            else:
                                formatted += f"   ▶️ `{str(cmd_obj)}`\n\n"
                    # Fallback to simple commands format
                    elif commands:
                        formatted += "\n   💻 Commands to execute:\n"
                        for cmd in commands[:3]:  # Show up to 3 commands per solution
                            formatted += f"   ▶️ `{cmd}`\n"

                    # Add registry keys if available
                    registry_keys = solution.get("registry_keys", [])
                    if registry_keys:
                        formatted += "\n   🗝️ Registry modifications:\n"
                        for key in registry_keys[:2]:  # Show up to 2 registry keys per solution
                            formatted += f"   📍 {key}\n"

                    # Add download links if available with professional formatting
                    download_links = solution.get("download_links", [])
                    if download_links:
                        formatted += "\n   📥 Required downloads:\n\n"
                        for link in download_links[:3]:  # Show up to 3 links per solution
                            if isinstance(link, dict):
                                # Professional formatting for dictionary-style links
                                desc = link.get("description", "Download")
                                url = link.get("url", "#")
                                file_size = link.get("file_size", "Size unknown")
                                checksum = link.get("checksum", "Not provided")

                                formatted += f"   🔗 **{desc}**\n"
                                formatted += f"      📍 URL: [{url}]({url})\n"
                                formatted += f"      📦 Size: {file_size}\n"
                                if checksum and checksum != "Not provided" and checksum != "Not provided by vendor":
                                    formatted += f"      🔒 Checksum: {checksum}\n"
                                formatted += "\n"
                            elif isinstance(link, str):
                                # Simple string link formatting
                                if link.startswith("http"):
                                    formatted += f"   🔗 [{link}]({link})\n\n"
                                else:
                                    formatted += f"   🔗 {link}\n\n"
                            else:
                                # Fallback for any other format
                                formatted += f"   🔗 {str(link)}\n\n"

                    # Add file locations if available with enhanced formatting
                    file_locations = solution.get("file_locations", [])
                    if file_locations:
                        formatted += "\n   📁 Important file locations:\n\n"
                        for file_obj in file_locations[:3]:  # Show up to 3 file locations per solution
                            if isinstance(file_obj, dict):
                                description = file_obj.get("description", "File location")
                                path = file_obj.get("path", "")
                                backup_recommended = file_obj.get("backup_recommended", False)

                                formatted += f"   📄 **{description}**\n"
                                formatted += f"      📍 Path: `{path}`\n"
                                if backup_recommended:
                                    formatted += f"      ⚠️ Backup recommended before modification\n"
                                formatted += "\n"
                            else:
                                formatted += f"   📄 `{str(file_obj)}`\n\n"

                    # Add official documentation if available
                    official_docs = solution.get("official_documentation", [])
                    if official_docs:
                        formatted += "\n   📚 Official documentation:\n\n"
                        for doc_obj in official_docs[:2]:  # Show up to 2 documentation links per solution
                            if isinstance(doc_obj, dict):
                                title = doc_obj.get("title", "Documentation")
                                url = doc_obj.get("url", "#")
                                relevance = doc_obj.get("relevance", "")

                                formatted += f"   📖 **{title}**\n"
                                formatted += f"      🔗 [{url}]({url})\n"
                                if relevance:
                                    formatted += f"      💡 {relevance}\n"
                                formatted += "\n"
                            else:
                                formatted += f"   📖 {str(doc_obj)}\n\n"

                    # Add success indicators with enhanced formatting
                    success_indicators = solution.get("success_indicators", [])
                    if success_indicators:
                        formatted += "\n   ✅ Success indicators:\n"
                        for indicator in success_indicators[:3]:
                            formatted += f"   • {indicator}\n"

                    # Add safety notes if available
                    safety_notes = solution.get("safety_notes", "")
                    if safety_notes:
                        formatted += f"\n   ⚠️ **Safety notes:** {safety_notes}\n"

                    # Add rollback procedure with enhanced formatting
                    rollback_steps = solution.get("rollback_steps", [])
                    rollback = solution.get("rollback_procedure", "")

                    if rollback_steps:
                        formatted += "\n   ⏪ Rollback procedure:\n"
                        for step in rollback_steps[:3]:
                            formatted += f"   • {step}\n"
                    elif rollback:
                        formatted += f"\n   ⏪ Rollback: {rollback}\n"

                    formatted += "\n   " + "─" * 60 + "\n"
            else:
                formatted += "\n⚠️ No specific solutions provided. Check system configuration and try again.\n"

            # Add enhanced risk assessment
            formatted += f"""\n⚠️ RISK ASSESSMENT:
{risk_assessment}

🧠 AI THINKING PROCESS (Expert Analysis):"""

            # Add thinking insights with better formatting
            if thinking_process:
                # Ensure thinking_process is a list of strings
                if isinstance(thinking_process, str):
                    # If it's a single string, split it into logical parts or wrap it
                    thinking_list = [thinking_process]
                elif isinstance(thinking_process, list):
                    thinking_list = thinking_process
                else:
                    thinking_list = [str(thinking_process)]

                for i, thought in enumerate(thinking_list[:4], 1):  # Show first 4 thoughts
                    if isinstance(thought, str) and thought.strip():
                        content = thought.strip()[:300] + ("..." if len(thought.strip()) > 300 else "")
                        formatted += f"\n{i}. {content}\n"
                    elif isinstance(thought, dict):
                        content = thought.get("content", "")[:300]
                        content += "..." if len(thought.get("content", "")) > 300 else ""
                        formatted += f"\n{i}. {content}\n"
            else:
                formatted += "\n• Analysis completed using advanced Windows troubleshooting methodology\n"

            # Add enhanced monitoring and prevention
            formatted += f"""\n📊 MONITORING & PREVENTION:
"""

            monitoring_recs = []
            prevention_tips = []

            # Extract from solutions if available
            for solution in solutions[:3]:
                if "monitoring_recommendations" in solution:
                    monitoring_recs.extend(solution["monitoring_recommendations"])
                if "prevention_tips" in solution:
                    prevention_tips.extend(solution["prevention_tips"])

            # Add monitoring recommendations
            if monitoring_recs:
                formatted += "🔍 Monitor these indicators:\n"
                for rec in monitoring_recs[:3]:
                    formatted += f"• {rec}\n"

            # Add prevention tips
            if prevention_tips:
                formatted += "\n🛡️ Prevention tips:\n"
                for tip in prevention_tips[:3]:
                    formatted += f"• {tip}\n"

            # Add metadata with enhanced intelligence
            if metadata:
                formatted += "\n📈 ANALYSIS METADATA:\n"
                for key, value in metadata.items():
                    formatted += f"• {key.replace('_', ' ').title()}: {value}\n"

            # Add professional next steps
            formatted += f"""\n💡 PROFESSIONAL NEXT STEPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 IMMEDIATE ACTIONS:
  1. Create a system restore point before making any changes
  2. Start with the lowest risk, highest priority solution
  3. Test each solution individually to isolate effectiveness
  4. Document any changes made for potential rollback

🔹 IF PROBLEMS PERSIST:
  1. Check Windows Event Logs for additional error details
  2. Run Windows Memory Diagnostic (mdsched.exe)
  3. Perform System File Check (sfc /scannow)
  4. Consider professional technical support

🔹 SYSTEM HEALTH:
  1. Keep Windows and drivers updated
  2. Monitor system performance regularly
  3. Maintain regular system backups
  4. Run periodic hardware diagnostics

🔄 Re-run this AI analysis if your system configuration changes or new symptoms appear.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📞 For enterprise support or complex issues, consider consulting certified Windows system administrators.
            """

            return formatted

        except Exception as e:
            self.logger.error(f"Failed to format AI results: {e}")
            return f"""❌ Result Formatting Error

Failed to format AI analysis results: {e}

Raw result available - check application logs for details.
            """

    def _reset_analysis_ui(self) -> None:
        """Reset analysis UI to initial state."""
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Ready to analyze")
        self.analyze_btn.setEnabled(True)

    def update_analysis_ready_state(self) -> None:
        """Update the analysis button state based on available inputs."""
        try:
            has_images = len(self.image_drop_area.get_selected_images()) > 0
            has_description = len(self.error_description.toPlainText().strip()) > 0
            has_specs = bool(self.system_specs)

            # Analysis is ready if we have at least images OR description, and system specs
            analysis_ready = (has_images or has_description) and has_specs

            self.analyze_btn.setEnabled(analysis_ready)

            # Update status with validation summary if we have images
            if has_images:
                try:
                    validation_summary = self.image_drop_area.get_validation_summary()
                    total = validation_summary.get("total_images", 0)
                    valid = validation_summary.get("valid_images", 0)
                    secure = validation_summary.get("secure_images", 0)
                    size_mb = validation_summary.get("total_size_mb", 0)

                    status_msg = f"{total} images selected ({valid} valid, {secure} secure, {size_mb:.1f}MB)"
                    if analysis_ready:
                        self.statusBar().showMessage(status_msg)  # type: ignore
                except Exception:
                    # Fallback to simple count
                    if analysis_ready:
                        self.statusBar().showMessage("Ready for AI analysis")  # type: ignore
                    else:
                        self.statusBar().showMessage(f"{len(self.image_drop_area.get_selected_images())} images selected")  # type: ignore
            elif analysis_ready:
                self.statusBar().showMessage("Ready for AI analysis")  # type: ignore
            else:
                missing_items = []
                if not (has_images or has_description):
                    missing_items.append("images or error description")
                if not has_specs:
                    missing_items.append("system specifications")

                self.statusBar().showMessage(f"Missing: {', '.join(missing_items)}")  # type: ignore

        except Exception as e:
            self.logger.warning(f"Error updating analysis ready state: {e}")
            # Fallback to basic check
            has_text = len(self.error_description.toPlainText().strip()) > 0
            has_specs = bool(self.system_specs)
            self.analyze_btn.setEnabled(has_text and has_specs)

    def set_api_key(self) -> None:
        """Set the Google Gemini API key using the secure dialog."""
        try:
            # Get current API key if available
            current_key = None
            if self.security_manager and self.security_manager.has_api_key():
                current_key = self.security_manager.retrieve_api_key()

            # Show API key dialog
            dialog = APIKeyDialog(self, current_key)
            dialog.api_key_saved.connect(self._on_api_key_saved)

            # Execute dialog
            if dialog.exec():
                self.logger.info("API key configuration completed")

        except Exception as e:
            self.logger.error(f"Failed to show API key dialog: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open API key configuration: {str(e)}")  # type: ignore

    def _load_existing_system_specs(self) -> None:
        """Load existing system specifications from persistent storage."""
        try:
            if not self.system_data_manager:
                return

            # Check if update is needed
            if self.system_data_manager.needs_update(threshold_days=7):
                self.logger.info("System specs may be outdated, will prompt for update")
                self.statusBar().showMessage("System specs may be outdated - consider recollecting")  # type: ignore
                return

            # Load latest specs
            specs_data = self.system_data_manager.load_latest_system_specs()
            if specs_data:
                self.system_specs = specs_data

                # Display in responsive system info widget
                if self.responsive_system_info:
                    self.responsive_system_info.update_system_data(specs_data)

                # Update analysis ready state
                self.update_analysis_ready_state()

                # Show load info
                metadata = specs_data.get("_metadata", {})
                last_updated = metadata.get("last_updated", "Unknown")
                self.statusBar().showMessage(f"Loaded system specs from {last_updated[:10]}")  # type: ignore

                self.logger.info("Loaded existing system specs from storage")
            else:
                self.logger.debug("No existing system specs found")

        except Exception as e:
            self.logger.error(f"Failed to load existing system specs: {e}")

    def _initialize_ai_client(self) -> None:
        """Initialize AI client if API key is available."""
        try:
            if not self.security_manager:
                return

            if self.security_manager.has_api_key():
                api_key = self.security_manager.retrieve_api_key()
                if api_key:
                    # Initialize with quota-efficient default model
                    self.ai_client = AIClient(api_key=api_key, model_name="gemini-2.5-flash")
                    self.logger.info("AI client initialized with stored API key")
                else:
                    self.logger.warning("API key marked as available but could not retrieve")
            else:
                self.logger.debug("No API key available, AI client not initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize AI client: {e}")

    def _update_api_key_status(self) -> None:
        """Update API key status in the UI."""
        try:
            if not self.security_manager:
                return

            # Only update if fallback UI elements exist (when AIConfigurationPanel is not available)
            if hasattr(self, "api_key_label") and hasattr(self, "set_api_key_btn"):
                if self.security_manager.has_api_key():
                    self.api_key_label.setText("✅ Configured")
                    self.api_key_label.setStyleSheet("color: #28a745;")
                    self.set_api_key_btn.setText("Update API Key")
                else:
                    self.api_key_label.setText("❌ Not configured")
                    self.api_key_label.setStyleSheet("color: #dc3545;")
                    self.set_api_key_btn.setText("Set API Key")
            # If AI config panel is available, it handles its own status updates

        except Exception as e:
            self.logger.error(f"Failed to update API key status: {e}")

    def _on_api_key_saved(self, api_key: str) -> None:
        """Handle API key saved event."""
        try:
            # Re-initialize AI client with new API key
            self.ai_client = AIClient(api_key=api_key)

            # Update UI status
            self._update_api_key_status()

            # Update analysis ready state
            self.update_analysis_ready_state()

            # Show success message
            self.statusBar().showMessage("API key saved and validated successfully")  # type: ignore

            self.logger.info("API key saved and AI client updated")

        except Exception as e:
            self.logger.error(f"Failed to handle API key save: {e}")
            QMessageBox.critical(  # type: ignore
                self, "Error", f"API key saved but failed to initialize AI client: {str(e)}"
            )

    def _select_images_dialog(self) -> None:
        """Open file dialog to select multiple images with comprehensive validation."""
        try:
            file_dialog = QFileDialog()  # type: ignore
            file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)  # type: ignore
            file_dialog.setNameFilter("Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tiff *.tif)")
            file_dialog.setWindowTitle("Select Error Screenshot Images")

            if file_dialog.exec():
                selected_files = file_dialog.selectedFiles()
                if selected_files:
                    # Add through the drop area for comprehensive validation
                    self.image_drop_area.add_images(selected_files)

                    # Show validation results to user
                    try:
                        validation_summary = self.image_drop_area.get_validation_summary()
                        total = validation_summary.get("total_images", 0)
                        valid = validation_summary.get("valid_images", 0)
                        secure = validation_summary.get("secure_images", 0)
                        screenshot_likely = validation_summary.get("screenshot_likely", 0)
                        size_mb = validation_summary.get("total_size_mb", 0)

                        if valid < len(selected_files):
                            invalid_count = len(selected_files) - valid
                            QMessageBox.warning(  # type: ignore
                                self,
                                "Image Validation Results",
                                f"Validation Summary:\n"
                                f"• {valid} of {len(selected_files)} images added successfully\n"
                                f"• {invalid_count} images rejected due to validation issues\n"
                                f"• {secure} images passed security checks\n"
                                f"• {screenshot_likely} images appear to be screenshots\n"
                                f"• Total size: {size_mb:.1f} MB\n\n"
                                "Rejected files may have:\n"
                                "• Invalid format or corruption\n"
                                "• Security concerns (excessive size, suspicious metadata)\n"
                                "• Unsupported format or extensions",
                            )
                        elif total > 0:
                            QMessageBox.information(  # type: ignore
                                self,
                                "Images Added Successfully",
                                f"Successfully added {total} images:\n"
                                f"• {secure} images passed security validation\n"
                                f"• {screenshot_likely} appear to be screenshots\n"
                                f"• Total size: {size_mb:.1f} MB",
                            )

                    except Exception as e:
                        self.logger.warning(f"Could not generate validation summary: {e}")
                        # Fallback to simple success message
                        current_count = len(self.image_drop_area.get_selected_images())
                        self.statusBar().showMessage(f"Images processed - {current_count} total selected")  # type: ignore

        except Exception as e:
            self.logger.error(f"Failed to select images: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open image selection dialog: {e}")  # type: ignore

    def _show_specs_history(self) -> None:
        """Show system specifications history dialog."""
        try:
            if not self.system_data_manager:
                QMessageBox.warning(self, "Error", "System data manager not initialized.")
                return

            history = self.system_data_manager.get_specs_history(limit=20)

            if not history:
                QMessageBox.information(self, "History", "No system specification history found.")
                return

            # Create history display dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("System Specifications History")
            dialog.setModal(True)
            dialog.resize(600, 400)

            layout = QVBoxLayout(dialog)

            # History list
            from PyQt6.QtWidgets import QListWidget, QListWidgetItem

            history_list = QListWidget()

            for entry in history:
                timestamp = entry.get("timestamp", "Unknown")
                method = entry.get("collection_method", "auto")
                duration = entry.get("collection_duration")
                current = " (Current)" if entry.get("is_current") else ""

                duration_text = f" ({duration:.1f}s)" if duration else ""
                item_text = f"{timestamp} - {method.title()}{duration_text}{current}"

                item = QListWidgetItem(item_text)
                history_list.addItem(item)

            layout.addWidget(QLabel("Recent System Specification Collections:"))
            layout.addWidget(history_list)

            # Close button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)

            dialog.exec()

        except Exception as e:
            self.logger.error(f"Failed to show specs history: {e}")
            QMessageBox.critical(self, "Error", f"Failed to show history: {str(e)}")

    def _export_system_specs(self) -> None:
        """Export current system specifications to file."""
        try:
            if not self.system_specs:
                QMessageBox.warning(
                    self, "Export Error", "No system specifications to export. Please collect specs first."
                )
                return

            from PyQt6.QtWidgets import QFileDialog

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export System Specifications",
                f"system_specs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "JSON Files (*.json);;Text Files (*.txt)",
            )

            if file_path:
                if file_path.endswith(".json"):
                    with open(file_path, "w") as f:
                        json.dump(self.system_specs, f, indent=2, default=str)
                else:
                    # Text export
                    with open(file_path, "w") as f:
                        f.write("Win Sayver - System Specifications Export\n")
                        f.write("=" * 50 + "\n\n")
                        f.write(json.dumps(self.system_specs, indent=2, default=str))

                QMessageBox.information(self, "Export Successful", f"System specifications exported to:\n{file_path}")
                self.logger.info(f"System specs exported to {file_path}")

        except Exception as e:
            self.logger.error(f"Failed to export system specs: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export specifications: {str(e)}")

    def show_about(self) -> None:
        """Show the about dialog."""
        about_text = """
<h2>Win Sayver v3.0</h2>
<p><b>AI-Powered Windows Troubleshooting Assistant</b></p>
<p>Professional desktop application for intelligent Windows error diagnosis using Google Gemini AI with advanced thinking capabilities.</p>
<br>
<p><b>Features:</b></p>
<ul>
<li>Multi-image error screenshot analysis with comprehensive validation</li>
<li>AI-powered diagnostic recommendations</li>
<li>Comprehensive system profiling</li>
<li>Real-time thinking process visualization</li>
<li>Security-focused image processing pipeline</li>
</ul>
<br>
<p><b>Phase 3:</b> Professional Desktop GUI Implementation</p>
<p>© 2025 Win Sayver Project</p>
        """

        QMessageBox.about(self, "About Win Sayver", about_text)

    def closeEvent(self, a0) -> None:  # type: ignore
        """Handle application close event with comprehensive resource cleanup."""
        try:
            self.logger.info("Beginning application shutdown process...")

            # Stop any running background workers
            if hasattr(self, "_specs_worker") and self._specs_worker and self._specs_worker.isRunning():
                self.logger.info("Stopping background worker threads...")
                self._specs_worker.terminate()
                self._specs_worker.wait(2000)  # Wait up to 2 seconds

                # Force cleanup if thread didn't stop gracefully
                if self._specs_worker.isRunning():
                    self.logger.warning("Background worker did not stop gracefully")
                    self._specs_worker.quit()
                    self._specs_worker.wait(1000)

            # Cleanup UI components that might hold references
            if hasattr(self, "responsive_system_info") and self.responsive_system_info:
                try:
                    if hasattr(self.responsive_system_info, "header"):
                        self.responsive_system_info.header.clear_status()
                    # Disconnect any timers
                    if hasattr(self.responsive_system_info, "resize_timer"):
                        self.responsive_system_info.resize_timer.stop()
                except Exception as e:
                    self.logger.warning(f"Error cleaning up responsive system info: {e}")

            # Cleanup core components
            if hasattr(self, "specs_collector") and self.specs_collector:
                try:
                    # Use the proper cleanup method
                    self.specs_collector.cleanup_resources()
                except Exception as e:
                    self.logger.warning(f"Error cleaning up specs collector: {e}")

            # Cleanup AI client
            if hasattr(self, "ai_client") and self.ai_client:
                try:
                    # Close any open connections
                    self.ai_client = None
                except Exception as e:
                    self.logger.warning(f"Error cleaning up AI client: {e}")

            # Save settings
            self._save_settings()

            # COM cleanup for the main thread
            try:
                import pythoncom

                if pythoncom:
                    pythoncom.CoUninitialize()
            except Exception:
                pass

            self.logger.info("Application shutdown completed successfully")
            a0.accept()  # type: ignore

        except Exception as e:
            self.logger.error(f"Error during application close: {e}")
            a0.accept()  # type: ignore


def main():
    """Main application entry point."""
    # Check PyQt6 availability
    if not PYQT6_AVAILABLE:
        print("❌ PyQt6 is required for the GUI version.")
        print("Install with: pip install PyQt6")
        return 1

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    try:
        # Create application
        app = QApplication(sys.argv)  # type: ignore
        app.setApplicationName("Win Sayver")
        app.setApplicationVersion("3.0")
        app.setOrganizationName("Win Sayver Project")

        # Create and show main window
        window = WinSayverMainWindow()
        window.show()

        # Run application
        return app.exec()

    except Exception as e:
        print(f"❌ Failed to start Win Sayver GUI: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
