#!/usr/bin/env python3
"""
API Key Dialog Module for Win Sayver POC.

This module provides a professional dialog for API key input, validation testing,
and secure storage integration with the SecurityManager.
"""

import logging
from typing import TYPE_CHECKING, Optional

try:
    from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
    from PyQt6.QtGui import QFont, QIcon, QPalette
    from PyQt6.QtWidgets import (
        QCheckBox,
        QDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    # Fallback imports for development
    if TYPE_CHECKING:
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QTextEdit,
            QProgressBar,
            QFrame,
            QWidget,
            QMessageBox,
            QCheckBox,
            QGroupBox,
        )
        from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
        from PyQt6.QtGui import QFont, QIcon, QPalette

from security_manager import SecurityManager
from utils import WinSayverError


class APIKeyDialogError(WinSayverError):
    """Raised when API key dialog operations fail."""

    pass


class ValidationWorker(QThread):
    """
    Worker thread for API key validation to keep UI responsive.
    """

    validation_complete = pyqtSignal(dict)
    validation_progress = pyqtSignal(str)

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

    def run(self):
        """
        Run API key validation in background thread.
        """
        try:
            self.validation_progress.emit("Initializing AI client...")

            # Import here to avoid circular imports
            from ai_client import AIClient

            self.validation_progress.emit("Testing API connection...")

            # Create AI client with the provided API key
            ai_client = AIClient(api_key=self.api_key)

            self.validation_progress.emit("Validating API key...")

            # Test the connection
            result = ai_client.test_connection()

            # Add additional validation info
            result["api_key_length"] = len(self.api_key)
            result["validation_timestamp"] = __import__("datetime").datetime.now().isoformat()

            self.validation_complete.emit(result)

        except Exception as e:
            self.logger.error(f"API key validation failed: {e}")
            error_result = {
                "success": False,
                "error": str(e),
                "error_type": "validation_error",
                "suggestion": "Check API key format and network connection",
            }
            self.validation_complete.emit(error_result)


class APIKeyDialog(QDialog):
    """
    Professional dialog for API key input, validation, and secure storage.

    This dialog provides a user-friendly interface for:
    - API key input with secure text handling
    - Real-time validation testing
    - Secure storage integration
    - User feedback and progress indication
    """

    api_key_saved = pyqtSignal(str)  # Emitted when API key is successfully saved

    def __init__(self, parent=None, current_api_key: Optional[str] = None):
        """
        Initialize the API Key Dialog.

        Args:
            parent: Parent widget
            current_api_key: Current API key if editing existing one
        """
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.security_manager = SecurityManager()
        self.validation_worker = None
        self.current_api_key = current_api_key

        # Dialog state
        self.validation_in_progress = False
        self.api_key_validated = False

        # Setup UI
        self._setup_ui()
        self._setup_connections()
        self._load_existing_key()

        self.logger.debug("APIKeyDialog initialized")

    def _setup_ui(self):
        """
        Setup the user interface components.
        """
        self.setWindowTitle("API Key Management - Win Sayver")
        self.setModal(True)
        self.setFixedSize(600, 500)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title and description
        title_label = QLabel("Google Gemini API Key Configuration")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        description_label = QLabel(
            "Enter your Google Gemini API key to enable AI-powered error analysis. "
            "Your API key will be encrypted and stored securely on your local machine."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(description_label)

        # API Key input section
        input_group = QGroupBox("API Key Input")
        input_layout = QVBoxLayout(input_group)

        # API key input field
        key_layout = QHBoxLayout()
        key_label = QLabel("API Key:")
        key_label.setMinimumWidth(80)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your Google Gemini API key...")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        # Show/hide button
        self.show_hide_btn = QPushButton("Show")
        self.show_hide_btn.setFixedWidth(60)
        self.show_hide_btn.setCheckable(True)

        key_layout.addWidget(key_label)
        key_layout.addWidget(self.api_key_input)
        key_layout.addWidget(self.show_hide_btn)
        input_layout.addLayout(key_layout)

        # Help text
        help_text = QLabel("Get your free API key from <a href='https://ai.google.dev'>Google AI Studio</a>")
        help_text.setOpenExternalLinks(True)
        help_text.setStyleSheet("color: #007ACC; font-size: 10px;")
        input_layout.addWidget(help_text)

        layout.addWidget(input_group)

        # Validation section
        validation_group = QGroupBox("API Key Validation")
        validation_layout = QVBoxLayout(validation_group)

        # Validation controls
        validation_controls = QHBoxLayout()
        self.validate_btn = QPushButton("Test API Key")
        self.validate_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #007ACC;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """
        )

        self.auto_validate_cb = QCheckBox("Auto-validate on input")
        self.auto_validate_cb.setChecked(True)

        validation_controls.addWidget(self.validate_btn)
        validation_controls.addStretch()
        validation_controls.addWidget(self.auto_validate_cb)
        validation_layout.addLayout(validation_controls)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #007ACC;
                border-radius: 3px;
            }
        """
        )
        validation_layout.addWidget(self.progress_bar)

        # Validation results
        self.validation_output = QTextEdit()
        self.validation_output.setMaximumHeight(120)
        self.validation_output.setReadOnly(True)
        self.validation_output.setStyleSheet(
            """
            QTextEdit {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #F8F8F8;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10px;
            }
        """
        )
        validation_layout.addWidget(self.validation_output)

        layout.addWidget(validation_group)

        # Security info
        security_frame = QFrame()
        security_frame.setFrameStyle(QFrame.Shape.Box)
        security_frame.setStyleSheet(
            """
            QFrame {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                background-color: #F0F8FF;
                padding: 5px;
            }
        """
        )
        security_layout = QVBoxLayout(security_frame)

        security_label = QLabel("🔒 Security Information:")
        security_label.setStyleSheet("font-weight: bold; color: #006600;")
        security_layout.addWidget(security_label)

        security_text = QLabel(
            "• Your API key is encrypted using Fernet (AES 128) encryption\n"
            "• The key is stored locally in your AppData folder\n"
            "• No API key data is transmitted to external servers except Google"
        )
        security_text.setStyleSheet("font-size: 10px; color: #004400;")
        security_layout.addWidget(security_text)

        layout.addWidget(security_frame)

        # Button layout
        button_layout = QHBoxLayout()

        self.remove_btn = QPushButton("Remove Key")
        self.remove_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #DC3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #C82333;
            }
        """
        )

        self.cancel_btn = QPushButton("Cancel")
        self.save_btn = QPushButton("Save API Key")
        self.save_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #28A745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """
        )

        button_layout.addWidget(self.remove_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

        # Set initial state
        self._update_ui_state()

    def _setup_connections(self):
        """
        Setup signal connections for UI components.
        """
        # Button connections
        self.show_hide_btn.toggled.connect(self._toggle_password_visibility)
        self.validate_btn.clicked.connect(self._validate_api_key)
        self.save_btn.clicked.connect(self._save_api_key)
        self.cancel_btn.clicked.connect(self.reject)
        self.remove_btn.clicked.connect(self._remove_api_key)

        # Input connections
        self.api_key_input.textChanged.connect(self._on_api_key_changed)

        # Auto-validation timer
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._auto_validate)

    def _load_existing_key(self):
        """
        Load existing API key if available.
        """
        try:
            if self.current_api_key:
                # Use provided key
                self.api_key_input.setText(self.current_api_key)
            else:
                # Try to load from secure storage
                stored_key = self.security_manager.retrieve_api_key()
                if stored_key:
                    self.api_key_input.setText(stored_key)
                    self.validation_output.append("Loaded existing API key from secure storage.")

        except Exception as e:
            self.logger.error(f"Failed to load existing API key: {e}")
            self.validation_output.append(f"Note: Could not load existing API key: {e}")

    def _toggle_password_visibility(self, checked: bool):
        """
        Toggle API key visibility.

        Args:
            checked: Whether show button is checked
        """
        if checked:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_hide_btn.setText("Hide")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_hide_btn.setText("Show")

    def _on_api_key_changed(self):
        """
        Handle API key input changes.
        """
        self.api_key_validated = False
        self._update_ui_state()

        # Auto-validation with delay
        if self.auto_validate_cb.isChecked() and len(self.api_key_input.text()) > 10:
            self.validation_timer.stop()
            self.validation_timer.start(2000)  # 2-second delay

    def _auto_validate(self):
        """
        Perform automatic validation after input delay.
        """
        if not self.validation_in_progress and len(self.api_key_input.text()) > 10:
            self._validate_api_key()

    def _validate_api_key(self):
        """
        Validate the entered API key.
        """
        api_key = self.api_key_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "Warning", "Please enter an API key first.")
            return

        if len(api_key) < 10:
            QMessageBox.warning(self, "Warning", "API key appears too short. Please check your input.")
            return

        # Start validation
        self.validation_in_progress = True
        self._update_ui_state()

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.validation_output.clear()
        self.validation_output.append("Starting API key validation...\n")

        # Create and start validation worker
        self.validation_worker = ValidationWorker(api_key)
        self.validation_worker.validation_progress.connect(self._on_validation_progress)
        self.validation_worker.validation_complete.connect(self._on_validation_complete)
        self.validation_worker.start()

    def _on_validation_progress(self, message: str):
        """
        Handle validation progress updates.

        Args:
            message: Progress message
        """
        self.validation_output.append(f"• {message}")
        self.validation_output.ensureCursorVisible()

    def _on_validation_complete(self, result: dict):
        """
        Handle validation completion.

        Args:
            result: Validation result dictionary
        """
        self.validation_in_progress = False
        self.progress_bar.setVisible(False)

        if result.get("success", False):
            self.api_key_validated = True
            self.validation_output.append("\n✅ API key validation successful!")
            self.validation_output.append(f"• Model: {result.get('model', 'Unknown')}")
            self.validation_output.append(f"• Response time: {result.get('response_time', 0):.2f}s")
            self.validation_output.append(f"• SDK: {result.get('sdk_version', 'Unknown')}")

            # Style for success
            self.validation_output.setStyleSheet(
                """
                QTextEdit {
                    border: 1px solid #28A745;
                    border-radius: 4px;
                    background-color: #F8FFF8;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 10px;
                }
            """
            )
        else:
            self.api_key_validated = False
            self.validation_output.append(f"\n❌ API key validation failed!")
            self.validation_output.append(f"• Error: {result.get('error', 'Unknown error')}")

            if result.get("suggestion"):
                self.validation_output.append(f"• Suggestion: {result.get('suggestion')}")

            # Style for error
            self.validation_output.setStyleSheet(
                """
                QTextEdit {
                    border: 1px solid #DC3545;
                    border-radius: 4px;
                    background-color: #FFF8F8;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 10px;
                }
            """
            )

        self._update_ui_state()
        self.validation_output.ensureCursorVisible()

    def _save_api_key(self):
        """
        Save the API key securely.
        """
        api_key = self.api_key_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "Warning", "Please enter an API key first.")
            return

        # Confirm if not validated
        if not self.api_key_validated:
            reply = QMessageBox.question(
                self,
                "Confirm Save",
                "The API key has not been validated. Are you sure you want to save it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            # Save using SecurityManager
            success = self.security_manager.store_api_key(api_key, validate=True)

            if success:
                QMessageBox.information(
                    self, "Success", "API key saved securely! The key has been encrypted and stored locally."
                )
                self.api_key_saved.emit(api_key)
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save API key. Please check the logs for details.")

        except Exception as e:
            self.logger.error(f"Failed to save API key: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save API key: {str(e)}")

    def _remove_api_key(self):
        """
        Remove the stored API key.
        """
        reply = QMessageBox.question(
            self,
            "Confirm Remove",
            "Are you sure you want to remove the stored API key? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = self.security_manager.remove_api_key()
                if success:
                    QMessageBox.information(self, "Success", "API key removed successfully.")
                    self.api_key_input.clear()
                    self.validation_output.clear()
                    self.api_key_validated = False
                    self._update_ui_state()
                else:
                    QMessageBox.warning(self, "Warning", "Failed to remove API key.")
            except Exception as e:
                self.logger.error(f"Failed to remove API key: {e}")
                QMessageBox.critical(self, "Error", f"Failed to remove API key: {str(e)}")

    def _update_ui_state(self):
        """
        Update UI component states based on current conditions.
        """
        has_input = bool(self.api_key_input.text().strip())
        has_stored_key = self.security_manager.has_api_key()

        # Update button states
        self.validate_btn.setEnabled(has_input and not self.validation_in_progress)
        self.save_btn.setEnabled(has_input and not self.validation_in_progress)
        self.remove_btn.setEnabled(has_stored_key)

        # Update save button text based on validation status
        if self.api_key_validated:
            self.save_btn.setText("Save Validated Key")
        else:
            self.save_btn.setText("Save API Key")

    def closeEvent(self, a0):
        """
        Handle dialog close event.
        """
        # Clean up validation worker if running
        if self.validation_worker and self.validation_worker.isRunning():
            self.validation_worker.terminate()
            self.validation_worker.wait(3000)  # Wait up to 3 seconds

        super().closeEvent(a0)
