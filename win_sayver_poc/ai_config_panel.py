#!/usr/bin/env python3
"""
AI Configuration Panel for Win Sayver GUI
=========================================

Comprehensive AI settings management interface with model selection,
thinking budget controls, performance modes, and secure API key management.
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

# Add the missing imports
from ai_client import AIClient
from utils import PerformanceTimer

try:
    from PyQt6.QtCore import QObject, QEvent, Qt, QThread, QTimer
    from PyQt6.QtCore import pyqtSignal
    from PyQt6.QtCore import pyqtSignal as Signal
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QFontComboBox,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QSpinBox,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    # Import stubs for type checking
    if TYPE_CHECKING:
        from PyQt6.QtCore import QObject, QEvent, Qt, QThread, QTimer
        from PyQt6.QtCore import pyqtSignal
        from PyQt6.QtCore import pyqtSignal as Signal
        from PyQt6.QtGui import QFont
        from PyQt6.QtWidgets import (
            QCheckBox,
            QComboBox,
            QFontComboBox,
            QFormLayout,
            QFrame,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMessageBox,
            QProgressBar,
            QPushButton,
            QSpinBox,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    else:
        # Create mock classes for runtime
        class QWidget:
            pass

        class QVBoxLayout:
            pass

        class QHBoxLayout:
            pass

        class QFormLayout:
            pass

        class QLabel:
            pass

        class QPushButton:
            pass

        class QComboBox:
            pass

        class QSpinBox:
            pass

        class QCheckBox:
            pass

        class QLineEdit:
            pass

        class QGroupBox:
            pass

        class QProgressBar:
            pass

        class QMessageBox:
            pass

        class QFrame:
            pass

        class QTextEdit:
            pass

        class QThread:
            pass

        class QFont:
            pass

        class Qt:
            pass

        class QTimer:
            def __init__(self):
                self._timeout = Signal() if Signal else None
            
            def setSingleShot(self, single_shot):
                pass
                
            def start(self, msec):
                pass
                
            def stop(self):
                pass
                
            @property
            def timeout(self):
                return self._timeout if self._timeout else Signal()
        def pyqtSignal(*args):
            return None

        Signal = pyqtSignal

        class QObject:
            pass
            
        class QEvent:
            class Type:
                Wheel = None

        class QFontComboBox:
            pass

@dataclass
class AIConfiguration:
    """AI configuration data class with official Google API parameters."""

    api_key: str = ""
    model: str = "gemini-2.5-pro"
    thinking_budget: str = "-1"  # Dynamic thinking budget (official Google API format)
    custom_thinking_value: int = 4096
    performance_mode: str = "balanced"
    enable_streaming: bool = True
    timeout_seconds: int = 60
    max_retries: int = 3
    enable_chain_of_thought: bool = True
    enable_search_grounding: bool = True  # Google Search Grounding
    url_context: List[str] = field(default_factory=list)  # URL context for grounding

    def __post_init__(self):
        """Initialize mutable default values."""
        pass  # field(default_factory=list) handles the list initialization


class APIKeySaveWorker(QThread):
    """Background worker for saving API key securely."""
    
    save_completed = pyqtSignal(bool, str)  # success, message

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def run(self) -> None:
        """Save API key in background thread."""
        try:
            if self.api_key.strip():
                # Import SecurityManager to save API key securely
                from security_manager import SecurityManager
                security_manager = SecurityManager()
                
                # Store API key using secure encryption
                security_manager.store_api_key(self.api_key.strip())
                self.save_completed.emit(True, "API key saved successfully")
            else:
                # Remove existing API key if input is empty
                from security_manager import SecurityManager
                security_manager = SecurityManager()
                security_manager.remove_api_key()
                self.save_completed.emit(True, "API key removed")
        except Exception as e:
            self.save_completed.emit(False, f"Failed to save API key: {str(e)}")


class ConnectionTester(QThread):
    """Background thread for testing AI API connection."""

    test_completed = Signal(bool, str)  # success, message
    progress_updated = Signal(int)  # progress percentage

    def __init__(self, config: AIConfiguration):
        super().__init__()
        self.config = config

    def run(self) -> None:
        """Run connection test in background."""
        try:
            self.progress_updated.emit(20)

            # Create AI client with test configuration
            ai_client = AIClient(
                api_key=self.config.api_key,
                model_name=self.config.model,
                thinking_budget=self.config.thinking_budget,
                enable_streaming=self.config.enable_streaming,
            )

            self.progress_updated.emit(60)

            # Test connection
            with PerformanceTimer("AI connection test") as timer:
                result = ai_client.test_connection()

            self.progress_updated.emit(100)

            if result.get("success", False):
                message = (
                    f"✅ Connection successful!\n\nModel: {self.config.model}\nResponse time: {timer.duration:.2f}s"
                )
                self.test_completed.emit(True, message)
            else:
                error_msg = result.get("error", "Unknown error")
                self.test_completed.emit(False, f"❌ Connection failed: {error_msg}")

        except Exception as e:
            self.test_completed.emit(False, f"❌ Test failed: {str(e)}")


class APIKeyWidget(QWidget):
    """Widget for secure API key management."""

    api_key_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.save_worker = None
        self.pending_save_key = None
        self.save_timer = None
        
        # Only create timer if PYQT6 is available
        try:
            if PYQT6_AVAILABLE:
                from PyQt6.QtCore import QTimer
                self.save_timer = QTimer()
                self.save_timer.setSingleShot(True)
                self.save_timer.timeout.connect(self._perform_save)
        except Exception:
            self.save_timer = None
            
        self._setup_ui()
        self._load_api_key()

    def _setup_ui(self) -> None:
        """Setup API key widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # API Key input with improved styling
        key_layout = QHBoxLayout()
        key_layout.setSpacing(8)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("Enter your Google Gemini API key")
        self.api_key_edit.setMinimumHeight(32)
        self.api_key_edit.textChanged.connect(self._on_key_changed)
        self.api_key_edit.editingFinished.connect(self._on_editing_finished)
        key_layout.addWidget(self.api_key_edit)

        # Show/Hide toggle with improved styling
        self.show_key_btn = QPushButton("👁 Show")
        self.show_key_btn.setMaximumWidth(80)
        self.show_key_btn.setMinimumHeight(32)
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.setToolTip("Show/Hide API key")
        self.show_key_btn.setStyleSheet(
            """
            QPushButton {
                font-size: 12px;
                font-weight: normal;
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #f0f0f0;
                color: #333333;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:checked {
                background-color: #2196F3;
                color: white;
                border: 1px solid #1976D2;
            }
        """
        )
        self.show_key_btn.toggled.connect(self._toggle_key_visibility)
        key_layout.addWidget(self.show_key_btn)

        layout.addLayout(key_layout)

        # Status with improved styling
        info_layout = QHBoxLayout()
        info_layout.setSpacing(8)

        self.status_label = QLabel("No API key configured")
        self.status_label.setStyleSheet("color: #ff6b6b; font-size: 12px; font-weight: 500;")
        info_layout.addWidget(self.status_label)

        info_layout.addStretch()

        # Get API key link with improved styling
        get_key_btn = QPushButton("🔑 Get API Key")
        get_key_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """
        )
        get_key_btn.clicked.connect(self._open_api_key_page)
        info_layout.addWidget(get_key_btn)

        layout.addLayout(info_layout)

    def _on_key_changed(self, key: str) -> None:
        """Handle API key change with debounced saving."""
        if key.strip():
            self.status_label.setText("✅ API key configured")
            self.status_label.setStyleSheet("color: #4caf50; font-size: 12px; font-weight: 500;")
        else:
            self.status_label.setText("No API key configured")
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 12px; font-weight: 500;")

        self.api_key_changed.emit(key)
        
        # Start debounced save timer (1 second delay) if available
        try:
            if hasattr(self, 'save_timer') and self.save_timer:
                self.pending_save_key = key
                self.save_timer.start(1000)  # Save after 1 second of no typing
        except:
            # If any error occurs, save immediately
            self._perform_save()

    def _on_editing_finished(self) -> None:
        """Handle when user finishes editing (focus lost)."""
        # Save immediately when focus is lost
        try:
            if hasattr(self, 'save_timer') and self.save_timer:
                self.save_timer.stop()
        except:
            pass
        self._perform_save()

    def _perform_save(self) -> None:
        """Perform the actual API key saving in background."""
        try:
            if hasattr(self, 'save_worker') and self.save_worker and hasattr(self.save_worker, 'isRunning') and self.save_worker.isRunning():
                # If a save is already in progress, wait for it to finish
                return
        except:
            pass
            
        # Get key value safely
        key = ""
        try:
            if hasattr(self, 'pending_save_key') and self.pending_save_key is not None:
                key = self.pending_save_key
            elif hasattr(self, 'api_key_edit') and self.api_key_edit:
                key = self.api_key_edit.text()
        except:
            pass
        
        # Start background save worker
        try:
            self.save_worker = APIKeySaveWorker(key)
            self.save_worker.save_completed.connect(self._on_save_completed)
            self.save_worker.start()
        except:
            # If worker fails, emit the signal directly
            try:
                if hasattr(self, 'api_key_edit') and self.api_key_edit:
                    self.api_key_changed.emit(self.api_key_edit.text())
            except:
                pass

    def _on_save_completed(self, success: bool, message: str) -> None:
        """Handle completion of background API key save."""
        if not success:
            print(f"Warning: {message}")
        # Emit the signal to notify that the configuration was saved
        self.api_key_changed.emit(self.api_key_edit.text())

    def _toggle_key_visibility(self, show: bool) -> None:
        """Toggle API key visibility."""
        if show:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_key_btn.setText("🙈 Hide")
            self.show_key_btn.setStyleSheet(
                """
                QPushButton {
                    font-size: 12px;
                    font-weight: normal;
                    border: 1px solid #1976D2;
                    border-radius: 4px;
                    background-color: #2196F3;
                    color: white;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """
            )
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_key_btn.setText("👁 Show")
            self.show_key_btn.setStyleSheet(
                """
                QPushButton {
                    font-size: 12px;
                    font-weight: normal;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    background-color: #f0f0f0;
                    color: #333333;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """
            )

    def _open_api_key_page(self) -> None:
        """Open Google AI Studio page for API key."""
        import webbrowser

        webbrowser.open("https://ai.google.dev/gemini-api")

    def _load_api_key(self) -> None:
        """Load saved API key from SecurityManager."""
        try:
            # Import SecurityManager to retrieve API key
            from security_manager import SecurityManager
            security_manager = SecurityManager()
            
            # Retrieve securely stored API key
            if security_manager.has_api_key():
                api_key = security_manager.retrieve_api_key()
                if api_key:
                    self.api_key_edit.setText(api_key)
                    # Update status label
                    self.status_label.setText("✅ API key configured")
                    self.status_label.setStyleSheet("color: #4caf50; font-size: 12px; font-weight: 500;")
        except Exception as e:
            # Log error but don't crash the UI
            print(f"Warning: Failed to load API key: {e}")

    def get_api_key(self) -> str:
        """Get current API key."""
        return self.api_key_edit.text().strip()


class AIConfigurationPanel(QWidget):
    """Comprehensive AI configuration panel."""

    configuration_changed = pyqtSignal(object)  # AIConfiguration object
    configuration_saved = pyqtSignal(str)  # API key string when configuration is saved

    def __init__(self, parent=None):
        super().__init__(parent)

        self.config = AIConfiguration()
        self.connection_tester = None
        self.save_timer = None

        # Create a timer for debounced saving
        try:
            if PYQT6_AVAILABLE:
                from PyQt6.QtCore import QTimer
                self.save_timer = QTimer()
                self.save_timer.setSingleShot(True)
                self.save_timer.timeout.connect(self._save_configuration)
        except Exception:
            self.save_timer = None

        self._setup_ui()
        self._setup_connections()
        self._load_configuration()

    def _get_available_models(self) -> List[Tuple[str, str]]:
        """
        Get available models with descriptions using official Google documentation.

        Returns:
            List of tuples (model_id, description)
        """
        # Updated model definitions based on official Google Gemini API docs
        all_models = [
            ("gemini-2.5-pro", "🧠 Gemini 2.5 Pro - State-of-the-art thinking model (RECOMMENDED)"),
            ("gemini-2.5-flash", "⚡ Gemini 2.5 Flash - Best price-performance with adaptive thinking"),
            ("gemini-2.5-flash-lite", "💰 Gemini 2.5 Flash-Lite - Most cost-efficient, high throughput"),
            ("gemini-2.0-flash", "🚀 Gemini 2.0 Flash - Next generation features and speed"),
            ("gemini-2.0-flash-lite", "🏃 Gemini 2.0 Flash-Lite - Cost efficiency and low latency"),
            ("gemini-1.5-pro", "📚 Gemini 1.5 Pro - Legacy stable model (Deprecated)"),
            ("gemini-1.5-flash", "🏃 Gemini 1.5 Flash - Legacy fast model (Deprecated)"),
        ]

        # Try to get available models from AI client if available
        try:
            if hasattr(self, "config") and self.config.api_key:
                # Create temporary client to check availability
                from ai_client import AIClient

                temp_client = AIClient(api_key=self.config.api_key)
                available_model_names = temp_client.get_available_models()

                # Filter models based on availability
                available_models = [
                    (model_id, desc) for model_id, desc in all_models if model_id in available_model_names
                ]

                if available_models:
                    return available_models
        except Exception:
            # Fall back to all models if checking fails
            pass

        # Return all models as fallback
        return all_models

    def _setup_ui(self) -> None:
        """Setup configuration panel UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)  # Increase spacing between main sections
        layout.setContentsMargins(20, 20, 20, 20)  # Add margins around the panel

        # Header with improved styling
        header_label = QLabel("🤖 AI Configuration")
        header_font = QFont()
        header_font.setPointSize(18)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("margin-bottom: 15px; color: #2196F3; padding: 10px;")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        layout.addWidget(header_label)

        # API Key section with improved styling
        api_group = QGroupBox("🔑 API Key Configuration")
        api_group.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #E0E0E0;
                border-radius: 10px;
                margin-top: 1ex;
                padding-top: 20px;
                background-color: #FFFFFF;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #2196F3;
                font-size: 16px;
            }
            """
        )
        api_layout = QVBoxLayout(api_group)
        api_layout.setSpacing(15)
        api_layout.setContentsMargins(15, 15, 15, 15)

        self.api_key_widget = APIKeyWidget()
        api_layout.addWidget(self.api_key_widget)

        layout.addWidget(api_group)

        # Model Configuration with improved styling
        model_group = QGroupBox("🧠 Model Configuration")
        model_group.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #E0E0E0;
                border-radius: 10px;
                margin-top: 1ex;
                padding-top: 20px;
                background-color: #FFFFFF;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #2196F3;
                font-size: 16px;
            }
            """
        )
        model_layout = QFormLayout(model_group)
        model_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)  # type: ignore
        model_layout.setHorizontalSpacing(20)
        model_layout.setVerticalSpacing(15)
        model_layout.setContentsMargins(15, 15, 15, 15)

        # Model selection with dynamic availability checking
        self.model_combo = QComboBox()
        self.model_combo.setMinimumHeight(36)  # Make combo boxes more accessible
        self.model_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Prevent wheel events when not focused
        self.model_combo.setStyleSheet(
            """
            QComboBox {
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                padding: 8px 12px;
                background-color: white;
                font-size: 14px;
                min-width: 300px;
            }
            QComboBox:hover {
                border-color: #2196F3;
            }
            QComboBox::drop-down {
                border: none;
                border-radius: 6px;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #CCCCCC;
                selection-background-color: #2196F3;
                selection-color: white;
                border-radius: 6px;
            }
            """
        )

        # Get available models dynamically
        available_models = self._get_available_models()

        for model_id, description in available_models:
            self.model_combo.addItem(description, model_id)

        model_layout.addRow("Model:", self.model_combo)

        # Model information and guidance
        self.model_info_label = QLabel()
        self.model_info_label.setWordWrap(True)
        self.model_info_label.setStyleSheet(
            """
            QLabel {
                background-color: #f0f8ff;
                border: 2px solid #d0e0f0;
                border-radius: 8px;
                padding: 15px;
                font-size: 13px;
                color: #333;
                margin: 5px;
            }
        """
        )
        self._update_model_info()  # Set initial info
        model_layout.addRow("Capabilities:", self.model_info_label)

        # Thinking budget with official Google documentation ranges
        self.thinking_combo = QComboBox()
        self.thinking_combo.setMinimumHeight(36)
        self.thinking_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Prevent wheel events when not focused
        self.thinking_combo.setStyleSheet(
            """
            QComboBox {
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                padding: 8px 12px;
                background-color: white;
                font-size: 14px;
                min-width: 300px;
            }
            QComboBox:hover {
                border-color: #2196F3;
            }
            QComboBox::drop-down {
                border: none;
                border-radius: 6px;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #CCCCCC;
                selection-background-color: #2196F3;
                selection-color: white;
                border-radius: 6px;
            }
            """
        )
        thinking_options = [
            ("-1", "DYNAMIC - Model decides when and how much to think (Recommended)"),
            ("4096", "HIGH - Deep reasoning (4096 tokens)"),
            ("2048", "MEDIUM - Balanced thinking (2048 tokens)"),
            ("1024", "STANDARD - Normal thinking (1024 tokens)"),
            ("512", "LIGHT - Quick thinking (512 tokens)"),
            ("0", "DISABLED - No thinking (Flash models only)"),
        ]

        for budget_value, description in thinking_options:
            self.thinking_combo.addItem(description, budget_value)

        model_layout.addRow("Thinking Budget:", self.thinking_combo)

        # Performance mode
        self.performance_combo = QComboBox()
        self.performance_combo.setMinimumHeight(36)
        self.performance_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Prevent wheel events when not focused
        self.performance_combo.setStyleSheet(
            """
            QComboBox {
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                padding: 8px 12px;
                background-color: white;
                font-size: 14px;
                min-width: 300px;
            }
            QComboBox:hover {
                border-color: #2196F3;
            }
            QComboBox::drop-down {
                border: none;
                border-radius: 6px;
            }
            QComboBox QAbstractItemView {
                border: 2px solid #CCCCCC;
                selection-background-color: #2196F3;
                selection-color: white;
                border-radius: 6px;
            }
            """
        )
        performance_modes = [
            ("balanced", "⚖️ Balanced - Good quality and speed"),
            ("quality", "🎯 Quality - Best analysis, slower"),
            ("speed", "⚡ Speed - Fast responses, basic analysis"),
        ]

        for mode_id, description in performance_modes:
            self.performance_combo.addItem(description, mode_id)

        model_layout.addRow("Performance Mode:", self.performance_combo)

        layout.addWidget(model_group)

        # Google Search Grounding Configuration with improved styling
        grounding_group = QGroupBox("🔍 Google Search Grounding")
        grounding_group.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #E0E0E0;
                border-radius: 10px;
                margin-top: 1ex;
                padding-top: 20px;
                background-color: #FFFFFF;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #2196F3;
                font-size: 16px;
            }
            """
        )
        grounding_layout = QFormLayout(grounding_group)
        grounding_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)  # type: ignore
        grounding_layout.setHorizontalSpacing(20)
        grounding_layout.setVerticalSpacing(15)
        grounding_layout.setContentsMargins(15, 15, 15, 15)

        # Enable grounding checkbox
        self.grounding_checkbox = QCheckBox("Enable real-time Google Search for AI analysis")
        self.grounding_checkbox.setChecked(True)
        self.grounding_checkbox.setStyleSheet(
            """
            QCheckBox {
                spacing: 10px;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #cccccc;
                border-radius: 4px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #2196F3;
                border-radius: 4px;
                background-color: #2196F3;
            }
            """
        )
        self.grounding_checkbox.setToolTip(
            "When enabled, the AI can search the web in real-time to provide\n"
            "more accurate and up-to-date solutions based on current information."
        )
        grounding_layout.addRow("Search Grounding:", self.grounding_checkbox)

        # URL Context input
        self.url_context_edit = QTextEdit()
        self.url_context_edit.setMaximumHeight(120)
        self.url_context_edit.setMinimumHeight(100)
        self.url_context_edit.setStyleSheet(
            """
            QTextEdit {
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
                font-size: 13px;
            }
            QTextEdit:focus {
                border-color: #2196F3;
            }
            """
        )
        self.url_context_edit.setPlaceholderText(
            "Optional: Enter specific URLs for context (one per line)\n"
            "Example:\n"
            "https://docs.microsoft.com/windows\n"
            "https://support.microsoft.com/help"
        )
        grounding_layout.addRow("URL Context:", self.url_context_edit)

        # Grounding info
        grounding_info = QLabel(
            "🔍 Search Grounding connects AI to real-time web content for:\n"
            "• Latest Windows updates and patches\n"
            "• Community solutions and forum discussions\n"
            "• Official Microsoft documentation\n"
            "• Source citations and verification"
        )
        grounding_info.setWordWrap(True)
        grounding_info.setStyleSheet(
            "QLabel {"
            "    background-color: #f0f8ff;"
            "    border: 2px solid #d0e0f0;"
            "    border-radius: 8px;"
            "    padding: 15px;"
            "    font-size: 12px;"
            "    color: #333;"
            "    margin: 5px;"
            "}"
        )
        grounding_layout.addRow("", grounding_info)

        layout.addWidget(grounding_group)

        # Advanced Settings with improved styling
        advanced_group = QGroupBox("⚙️ Advanced Settings")
        advanced_group.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #E0E0E0;
                border-radius: 10px;
                margin-top: 1ex;
                padding-top: 20px;
                background-color: #FFFFFF;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #2196F3;
                font-size: 16px;
            }
            """
        )
        advanced_layout = QFormLayout(advanced_group)
        advanced_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)  # type: ignore
        advanced_layout.setHorizontalSpacing(20)
        advanced_layout.setVerticalSpacing(15)
        advanced_layout.setContentsMargins(15, 15, 15, 15)

        # Streaming
        self.streaming_checkbox = QCheckBox("Enable streaming responses")
        self.streaming_checkbox.setChecked(True)
        self.streaming_checkbox.setStyleSheet(
            """
            QCheckBox {
                spacing: 10px;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #cccccc;
                border-radius: 4px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #2196F3;
                border-radius: 4px;
                background-color: #2196F3;
            }
            """
        )
        advanced_layout.addRow("Streaming:", self.streaming_checkbox)

        # Timeout
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 300)
        self.timeout_spin.setValue(60)
        self.timeout_spin.setSuffix(" seconds")
        self.timeout_spin.setMinimumHeight(36)
        self.timeout_spin.setStyleSheet(
            """
            QSpinBox {
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
                font-size: 14px;
                min-width: 150px;
            }
            QSpinBox:focus {
                border-color: #2196F3;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                border: none;
                background-color: #f0f0f0;
                width: 25px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #e0e0e0;
            }
            """
        )
        advanced_layout.addRow("Timeout:", self.timeout_spin)

        # Max retries
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(1, 10)
        self.retries_spin.setValue(3)
        self.retries_spin.setMinimumHeight(36)
        self.retries_spin.setStyleSheet(
            """
            QSpinBox {
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
                font-size: 14px;
                min-width: 150px;
            }
            QSpinBox:focus {
                border-color: #2196F3;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                border: none;
                background-color: #f0f0f0;
                width: 25px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #e0e0e0;
            }
            """
        )
        advanced_layout.addRow("Max Retries:", self.retries_spin)

        layout.addWidget(advanced_group)

        # Connection Testing with improved styling
        test_group = QGroupBox("🔗 Connection Testing")
        test_group.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #E0E0E0;
                border-radius: 10px;
                margin-top: 1ex;
                padding-top: 20px;
                background-color: #FFFFFF;
                font-size: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #2196F3;
                font-size: 16px;
            }
            """
        )
        test_layout = QVBoxLayout(test_group)
        test_layout.setSpacing(15)
        test_layout.setContentsMargins(15, 15, 15, 15)

        test_btn_layout = QHBoxLayout()

        self.test_connection_btn = QPushButton("🔍 Test Connection")
        self.test_connection_btn.setMinimumHeight(40)
        self.test_connection_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 600;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            """
        )
        self.test_connection_btn.clicked.connect(self._test_connection)
        test_btn_layout.addWidget(self.test_connection_btn)

        test_btn_layout.addStretch()

        test_layout.addLayout(test_btn_layout)

        # Test progress
        self.test_progress = QProgressBar()
        self.test_progress.setVisible(False)
        self.test_progress.setMinimumHeight(25)
        self.test_progress.setStyleSheet(
            """
            QProgressBar {
                border: 2px solid #CCCCCC;
                border-radius: 6px;
                text-align: center;
                background-color: #f0f0f0;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 4px;
            }
            """
        )
        test_layout.addWidget(self.test_progress)

        # Test result
        self.test_result_label = QLabel("Click 'Test Connection' to verify your AI configuration")
        self.test_result_label.setWordWrap(True)
        self.test_result_label.setStyleSheet("color: #666666; margin: 8px; padding: 8px; font-size: 13px;")
        test_layout.addWidget(self.test_result_label)

        layout.addWidget(test_group)

        # Action buttons with improved styling
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        self.reset_btn = QPushButton("🔄 Reset to Defaults")
        self.reset_btn.setMinimumHeight(40)
        self.reset_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 600;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #e68a00;
            }
            QPushButton:pressed {
                background-color: #cc7a00;
            }
        """
        )
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(self.reset_btn)

        button_layout.addStretch()

        self.save_btn = QPushButton("💾 Save Configuration")
        self.save_btn.setMinimumHeight(40)
        self.save_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 600;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """
        )
        self.save_btn.clicked.connect(self._save_configuration)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

    def _setup_connections(self) -> None:
        """Setup signal connections."""
        self.api_key_widget.api_key_changed.connect(self._on_config_changed)
        self.model_combo.currentTextChanged.connect(self._on_config_changed)
        self.model_combo.currentTextChanged.connect(self._update_model_info)  # Update info when model changes
        self.thinking_combo.currentTextChanged.connect(self._on_config_changed)
        self.performance_combo.currentTextChanged.connect(self._on_config_changed)
        self.streaming_checkbox.toggled.connect(self._on_config_changed)
        self.timeout_spin.valueChanged.connect(self._on_config_changed)
        self.retries_spin.valueChanged.connect(self._on_config_changed)

        # Google Search Grounding connections
        self.grounding_checkbox.toggled.connect(self._on_config_changed)
        self.url_context_edit.textChanged.connect(self._on_config_changed)

    def _on_config_changed(self) -> None:
        """Handle configuration change."""
        self._update_configuration()
        self.configuration_changed.emit(self.config)
        
        # Start debounced save (1.5 seconds delay)
        try:
            if hasattr(self, 'save_timer') and self.save_timer:
                self.save_timer.start(1500)
        except:
            # If timer fails, save immediately
            self._save_configuration()

    def _update_model_info(self) -> None:
        """Update model information display based on selected model."""
        current_model = self.model_combo.currentData()

        model_info = {
            "gemini-2.5-pro": {
                "description": "State-of-the-art thinking model with maximum response accuracy",
                "capabilities": [
                    "🧠 Advanced thinking and reasoning",
                    "📊 Complex problem analysis",
                    "💻 Superior coding assistance",
                    "📈 Large database analysis",
                    "🎯 Highest accuracy available",
                ],
                "best_for": "Complex troubleshooting, detailed analysis, professional use",
            },
            "gemini-2.5-flash": {
                "description": "Balanced model with adaptive thinking and fast responses",
                "capabilities": [
                    "⚡ Fast response times",
                    "🧠 Adaptive thinking process",
                    "💰 Good price-performance ratio",
                    "🔄 Configurable thinking budget",
                    "📋 Well-rounded capabilities",
                ],
                "best_for": "General troubleshooting, balanced performance and speed",
            },
            "gemini-2.5-flash-lite": {
                "description": "Cost-efficient model optimized for high throughput",
                "capabilities": [
                    "💨 Ultra-low latency",
                    "💰 Most cost-efficient",
                    "📈 High throughput support",
                    "🔄 Real-time responses",
                    "⚡ Optimized for speed",
                ],
                "best_for": "Quick diagnostics, high-volume usage, cost-sensitive applications",
            },
            "gemini-2.0-flash": {
                "description": "Next generation features with enhanced speed",
                "capabilities": [
                    "🚀 Next-gen features",
                    "⚡ Enhanced speed",
                    "🔄 Real-time streaming",
                    "📊 Improved efficiency",
                    "🔧 Modern capabilities",
                ],
                "best_for": "Modern applications, real-time analysis",
            },
            "gemini-1.5-pro": {
                "description": "Legacy stable model with proven reliability",
                "capabilities": [
                    "🛡️ Proven stability",
                    "📚 Large context support",
                    "🔄 Reliable performance",
                    "💼 Enterprise tested",
                    "📋 Comprehensive analysis",
                ],
                "best_for": "Conservative deployments, proven stability requirements",
            },
            "gemini-1.5-flash": {
                "description": "Legacy fast model for basic troubleshooting",
                "capabilities": [
                    "⚡ Fast responses",
                    "💰 Economical choice",
                    "🔧 Basic troubleshooting",
                    "📋 Simple analysis",
                    "🔄 Reliable operation",
                ],
                "best_for": "Basic diagnostics, legacy system compatibility",
            },
        }

        info = model_info.get(
            current_model,
            {
                "description": "Advanced AI model for Windows troubleshooting",
                "capabilities": ["🤖 AI-powered analysis"],
                "best_for": "General troubleshooting",
            },
        )

        info_text = f"""<b>{info['description']}</b><br><br>
        <b>Key Capabilities:</b><br>
        {' • '.join([''] + info['capabilities'])}<br><br>
        <b>Best For:</b> {info['best_for']}"""

        self.model_info_label.setText(info_text)

    def _update_configuration(self) -> None:
        """Update configuration object from UI."""
        self.config.api_key = self.api_key_widget.get_api_key()
        self.config.model = self.model_combo.currentData()
        self.config.thinking_budget = self.thinking_combo.currentData()
        self.config.performance_mode = self.performance_combo.currentData()
        self.config.enable_streaming = self.streaming_checkbox.isChecked()
        self.config.timeout_seconds = self.timeout_spin.value()
        self.config.max_retries = self.retries_spin.value()

        # Google Search Grounding settings
        self.config.enable_search_grounding = self.grounding_checkbox.isChecked()
        url_text = self.url_context_edit.toPlainText().strip()
        self.config.url_context = [url.strip() for url in url_text.split("\n") if url.strip()]

    def _test_connection(self) -> None:
        """Test AI connection."""
        if not self.config.api_key:
            QMessageBox.warning(self, "API Key Required", "Please enter your API key first.")
            return

        # Show progress
        self.test_progress.setVisible(True)
        self.test_progress.setValue(0)
        self.test_connection_btn.setEnabled(False)
        self.test_result_label.setText("Testing connection...")

        # Start connection test
        self.connection_tester = ConnectionTester(self.config)
        self.connection_tester.progress_updated.connect(self.test_progress.setValue)
        self.connection_tester.test_completed.connect(self._on_test_completed)
        self.connection_tester.start()

    def _on_test_completed(self, success: bool, message: str) -> None:
        """Handle connection test completion."""
        self.test_progress.setVisible(False)
        self.test_connection_btn.setEnabled(True)
        self.test_result_label.setText(message)

        if success:
            self.test_result_label.setStyleSheet("color: #4caf50; margin: 5px;")
        else:
            self.test_result_label.setStyleSheet("color: #ff6b6b; margin: 5px;")

    def _reset_to_defaults(self) -> None:
        """Reset configuration to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset Configuration",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.config = AIConfiguration()
            self._apply_configuration_to_ui()
            self._on_config_changed()

    def _save_configuration(self) -> None:
        """Save configuration to file."""
        try:
            # Stop the timer if it's running
            try:
                if hasattr(self, 'save_timer') and self.save_timer and self.save_timer.isActive():
                    self.save_timer.stop()
            except:
                pass
                
            config_dir = Path.home() / ".winsayver"
            config_dir.mkdir(exist_ok=True)

            config_file = config_dir / "ai_config.json"

            config_data = {
                "model": self.config.model,
                "thinking_budget": self.config.thinking_budget,
                "performance_mode": self.config.performance_mode,
                "enable_streaming": self.config.enable_streaming,
                "timeout_seconds": self.config.timeout_seconds,
                "max_retries": self.config.max_retries,
                "enable_search_grounding": self.config.enable_search_grounding,
                "url_context": self.config.url_context,
            }

            with open(config_file, "w") as f:
                json.dump(config_data, f, indent=2)

            # Emit signal when configuration is saved with the API key
            if self.config.api_key:
                self.configuration_saved.emit(self.config.api_key)
            else:
                self.configuration_saved.emit("")

            # Show success message only in debug mode or for explicit saves
            # For auto-saves, we don't show a message to avoid annoying the user
            # QMessageBox.information(self, "Configuration Saved", "AI configuration has been saved successfully!")

        except Exception as e:
            print(f"Warning: Failed to save configuration: {e}")
            # Only show error for explicit saves, not auto-saves
            # QMessageBox.critical(self, "Save Error", f"Failed to save configuration: {e}")

    def _load_configuration(self) -> None:
        """Load configuration from file."""
        try:
            config_dir = Path.home() / ".winsayver"
            config_file = config_dir / "ai_config.json"

            if config_file.exists():
                with open(config_file, "r") as f:
                    config_data = json.load(f)

                self.config.model = config_data.get("model", self.config.model)
                self.config.thinking_budget = config_data.get("thinking_budget", self.config.thinking_budget)
                self.config.performance_mode = config_data.get("performance_mode", self.config.performance_mode)
                self.config.enable_streaming = config_data.get("enable_streaming", self.config.enable_streaming)
                self.config.timeout_seconds = config_data.get("timeout_seconds", self.config.timeout_seconds)
                self.config.max_retries = config_data.get("max_retries", self.config.max_retries)
                self.config.enable_search_grounding = config_data.get(
                    "enable_search_grounding", self.config.enable_search_grounding
                )
                self.config.url_context = config_data.get("url_context", self.config.url_context)

                self._apply_configuration_to_ui()

        except Exception as e:
            print(f"Warning: Failed to load configuration: {e}")
            # Use defaults if loading fails

    def _apply_configuration_to_ui(self) -> None:
        """Apply configuration to UI elements."""
        # Set model
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == self.config.model:
                self.model_combo.setCurrentIndex(i)
                break

        # Set thinking budget
        for i in range(self.thinking_combo.count()):
            if self.thinking_combo.itemData(i) == self.config.thinking_budget:
                self.thinking_combo.setCurrentIndex(i)
                break

        # Set performance mode
        for i in range(self.performance_combo.count()):
            if self.performance_combo.itemData(i) == self.config.performance_mode:
                self.performance_combo.setCurrentIndex(i)
                break

        # Set other settings
        self.streaming_checkbox.setChecked(self.config.enable_streaming)
        self.timeout_spin.setValue(self.config.timeout_seconds)
        self.retries_spin.setValue(self.config.max_retries)

        # Set grounding settings
        self.grounding_checkbox.setChecked(self.config.enable_search_grounding)
        if self.config.url_context:
            self.url_context_edit.setPlainText("\n".join(self.config.url_context))

    def get_configuration(self) -> AIConfiguration:
        """Get current configuration."""
        self._update_configuration()
        return self.config

    def set_configuration(self, config: AIConfiguration) -> None:
        """Set configuration."""
        self.config = config
        self._apply_configuration_to_ui()
        self.configuration_changed.emit(self.config)
