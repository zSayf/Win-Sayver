#!/usr/bin/env python3
"""
Rich Text Editor for Win Sayver GUI
==================================

Professional rich text editor with formatting toolbar and template system
for error descriptions. Provides common Windows error templates and
formatted text input capabilities.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QTextCharFormat, QTextCursor

# PyQt6 imports with proper error handling
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


@dataclass
class ErrorTemplate:
    """Data class for error description templates."""

    name: str
    category: str
    description: str
    content: str
    tags: List[str]
    difficulty: str


class TemplateManager:
    """Manages error description templates for common Windows issues."""

    def __init__(self):
        """Initialize template manager with built-in templates."""
        self.templates = self._load_builtin_templates()
        self.custom_templates = []

    def _load_builtin_templates(self) -> List[ErrorTemplate]:
        """Load built-in error templates."""
        return [
            ErrorTemplate(
                name="Blue Screen of Death (BSOD)",
                category="System Critical",
                description="Template for BSOD errors with stop codes",
                difficulty="intermediate",
                tags=["bsod", "crash", "system", "critical"],
                content="""<h3>🔴 Blue Screen of Death Error</h3>

<p><strong>When did this occur?</strong><br>
• During startup/shutdown<br>
• While using specific software<br>
• During gaming or intensive tasks<br>
• Randomly during normal use</p>

<p><strong>Error Details:</strong><br>
<em>Stop Code:</em> (e.g., SYSTEM_SERVICE_EXCEPTION)<br>
<em>Failed Process:</em> (if shown)<br>
<em>Error Address:</em> (if available)</p>

<p><strong>What was happening when the error occurred?</strong><br>
• Describe what you were doing<br>
• Any recent hardware/software changes<br>
• Frequency of occurrence</p>""",
            ),
            ErrorTemplate(
                name="Application Crash",
                category="Software Issues",
                description="Template for application crashes and freezes",
                difficulty="beginner",
                tags=["crash", "application", "software", "freeze"],
                content="""<h3>💥 Application Crash/Freeze</h3>

<p><strong>Application Information:</strong><br>
<em>Application Name:</em> <br>
<em>Version:</em> <br>
<em>Error Message:</em> (if any)</p>

<p><strong>When does this happen?</strong><br>
• On application startup<br>
• During specific actions<br>
• After running for some time<br>
• When opening certain files</p>

<p><strong>Steps to Reproduce:</strong><br>
1. <br>
2. <br>
3. </p>""",
            ),
            ErrorTemplate(
                name="Windows Update Error",
                category="System Updates",
                description="Template for Windows Update failures",
                difficulty="intermediate",
                tags=["update", "windows", "installation", "error"],
                content="""<h3>🔄 Windows Update Error</h3>

<p><strong>Update Information:</strong><br>
<em>Error Code:</em> (e.g., 0x80070643)<br>
<em>KB Number:</em> (if available)<br>
<em>Update Type:</em> (Security, Feature, Driver, etc.)</p>

<p><strong>Update Behavior:</strong><br>
• Fails to download<br>
• Downloads but fails to install<br>
• Installs but fails to configure<br>
• Installs but requires multiple restarts</p>""",
            ),
        ]

    def get_templates(self, category: Optional[str] = None) -> List[ErrorTemplate]:
        """Get templates, optionally filtered by category."""
        all_templates = self.templates + self.custom_templates

        if category:
            return [t for t in all_templates if t.category == category]

        return all_templates

    def get_categories(self) -> List[str]:
        """Get list of available template categories."""
        categories = set()
        for template in self.templates + self.custom_templates:
            categories.add(template.category)
        return sorted(list(categories))

    def get_template_by_name(self, name: str) -> Optional[ErrorTemplate]:
        """Get template by name."""
        for template in self.templates + self.custom_templates:
            if template.name == name:
                return template
        return None


class TemplateDialog(QDialog):
    """Dialog for selecting and previewing error templates."""

    def __init__(self, template_manager: TemplateManager, parent=None):
        """Initialize template dialog."""
        super().__init__(parent)

        self.template_manager = template_manager
        self.selected_template = None

        self._setup_ui()
        self._populate_templates()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        self.setWindowTitle("Error Description Templates")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("📝 Choose an Error Description Template")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(header_label)

        # Main content area
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side - Template list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Category filter
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Category:"))

        self.category_combo = QComboBox()
        self.category_combo.addItem("All Categories")
        self.category_combo.addItems(self.template_manager.get_categories())
        self.category_combo.currentTextChanged.connect(self._filter_templates)
        category_layout.addWidget(self.category_combo)
        category_layout.addStretch()

        left_layout.addLayout(category_layout)

        # Template list
        self.template_list = QListWidget()
        self.template_list.currentItemChanged.connect(self._on_template_selected)
        left_layout.addWidget(self.template_list)

        splitter.addWidget(left_widget)

        # Right side - Template preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        preview_label = QLabel("Template Preview:")
        preview_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(preview_label)

        self.preview_browser = QTextBrowser()
        self.preview_browser.setMinimumWidth(400)
        right_layout.addWidget(self.preview_browser)

        # Template info
        info_group = QGroupBox("Template Information")
        info_layout = QVBoxLayout(info_group)

        self.info_label = QLabel("Select a template to see details")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)

        right_layout.addWidget(info_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([300, 500])

        layout.addWidget(splitter)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

    def _populate_templates(self) -> None:
        """Populate the template list."""
        self.template_list.clear()
        templates = self.template_manager.get_templates()

        for template in templates:
            item_text = f"{template.name} ({template.difficulty})"
            self.template_list.addItem(item_text)

    def _filter_templates(self, category: str) -> None:
        """Filter templates by category."""
        self.template_list.clear()

        if category == "All Categories":
            templates = self.template_manager.get_templates()
        else:
            templates = self.template_manager.get_templates(category)

        for template in templates:
            item_text = f"{template.name} ({template.difficulty})"
            self.template_list.addItem(item_text)

    def _on_template_selected(self, current, previous) -> None:
        """Handle template selection."""
        if not current:
            return

        # Extract template name from list item text
        item_text = current.text()
        template_name = item_text.split(" (")[0]  # Remove difficulty suffix

        template = self.template_manager.get_template_by_name(template_name)
        if template:
            self.selected_template = template

            # Update preview
            self.preview_browser.setHtml(template.content)

            # Update info
            info_text = f"""
<b>Name:</b> {template.name}<br>
<b>Category:</b> {template.category}<br>
<b>Difficulty:</b> {template.difficulty.title()}<br>
<b>Description:</b> {template.description}<br>
<b>Tags:</b> {', '.join(template.tags)}
            """.strip()
            self.info_label.setText(info_text)

    def get_selected_template(self) -> Optional[ErrorTemplate]:
        """Get the selected template."""
        return self.selected_template


class RichTextEditor(QWidget):
    """Professional rich text editor with formatting toolbar and template support."""

    # Signals
    text_changed = pyqtSignal()
    template_applied = pyqtSignal(str)  # template name

    def __init__(self, parent=None):
        """Initialize rich text editor."""
        super().__init__(parent)

        self.template_manager = TemplateManager()
        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Setup the rich text editor UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Toolbar
        self.toolbar = self._create_toolbar()
        layout.addWidget(self.toolbar)

        # Text editor
        self.text_edit = QTextEdit()
        self.text_edit.setMinimumHeight(200)
        self.text_edit.setPlaceholderText(
            "Describe your Windows error or issue here...\n\n"
            "💡 Tip: Use the Template button above to get started with common error scenarios, "
            "or use the formatting tools to structure your description."
        )

        # Enable rich text formatting
        self.text_edit.setAcceptRichText(True)

        layout.addWidget(self.text_edit)

        # Status bar
        status_layout = QHBoxLayout()

        self.char_count_label = QLabel("0 characters")
        self.char_count_label.setStyleSheet("color: #666666; font-size: 11px;")
        status_layout.addWidget(self.char_count_label)

        status_layout.addStretch()

        self.format_info_label = QLabel("Plain text mode")
        self.format_info_label.setStyleSheet("color: #666666; font-size: 11px;")
        status_layout.addWidget(self.format_info_label)

        layout.addLayout(status_layout)

    def _create_toolbar(self) -> QToolBar:
        """Create the formatting toolbar."""
        toolbar = QToolBar()
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.setMaximumHeight(40)

        # Template button
        template_action = QAction("📝 Templates", self)
        template_action.setToolTip("Choose from pre-built error description templates")
        template_action.triggered.connect(self._show_template_dialog)
        toolbar.addAction(template_action)

        toolbar.addSeparator()

        # Font family
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("Segoe UI"))
        self.font_combo.setMaximumWidth(150)
        self.font_combo.setToolTip("Font family")
        toolbar.addWidget(self.font_combo)

        # Font size
        self.font_size_combo = QSpinBox()
        self.font_size_combo.setRange(8, 72)
        self.font_size_combo.setValue(11)
        self.font_size_combo.setSuffix("pt")
        self.font_size_combo.setToolTip("Font size")
        toolbar.addWidget(self.font_size_combo)

        toolbar.addSeparator()

        # Bold
        self.bold_action = QAction("B", self)
        self.bold_action.setCheckable(True)
        self.bold_action.setToolTip("Bold (Ctrl+B)")
        self.bold_action.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        toolbar.addAction(self.bold_action)

        # Italic
        self.italic_action = QAction("I", self)
        self.italic_action.setCheckable(True)
        self.italic_action.setToolTip("Italic (Ctrl+I)")
        font = QFont("Arial", 12)
        font.setItalic(True)
        self.italic_action.setFont(font)
        toolbar.addAction(self.italic_action)

        # Underline
        self.underline_action = QAction("U", self)
        self.underline_action.setCheckable(True)
        self.underline_action.setToolTip("Underline (Ctrl+U)")
        font = QFont("Arial", 12)
        font.setUnderline(True)
        self.underline_action.setFont(font)
        toolbar.addAction(self.underline_action)

        toolbar.addSeparator()

        # Text color
        self.text_color_btn = QPushButton("A")
        self.text_color_btn.setToolTip("Text color")
        self.text_color_btn.setMaximumSize(30, 25)
        self.text_color_btn.setStyleSheet("color: black; font-weight: bold;")
        toolbar.addWidget(self.text_color_btn)

        # Clear formatting
        self.clear_format_action = QAction("Clear Format", self)
        self.clear_format_action.setToolTip("Clear all formatting")
        toolbar.addAction(self.clear_format_action)

        return toolbar

    def _setup_connections(self) -> None:
        """Setup signal connections."""
        # Text editor connections
        self.text_edit.textChanged.connect(self._on_text_changed)
        self.text_edit.cursorPositionChanged.connect(self._update_format_info)

        # Toolbar connections
        self.font_combo.currentFontChanged.connect(self._apply_font_family)
        self.font_size_combo.valueChanged.connect(self._apply_font_size)

        self.bold_action.triggered.connect(self._apply_bold)
        self.italic_action.triggered.connect(self._apply_italic)
        self.underline_action.triggered.connect(self._apply_underline)

        self.text_color_btn.clicked.connect(self._choose_text_color)
        self.clear_format_action.triggered.connect(self._clear_formatting)

    def _show_template_dialog(self) -> None:
        """Show template selection dialog."""
        dialog = TemplateDialog(self.template_manager, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            template = dialog.get_selected_template()
            if template:
                self._apply_template(template)

    def _apply_template(self, template: ErrorTemplate) -> None:
        """Apply selected template to the editor."""
        self.text_edit.setHtml(template.content)
        self.template_applied.emit(template.name)

    def _on_text_changed(self) -> None:
        """Handle text change events."""
        # Update character count
        text = self.text_edit.toPlainText()
        char_count = len(text)
        self.char_count_label.setText(f"{char_count} characters")

        # Emit signal
        self.text_changed.emit()

    def _update_format_info(self) -> None:
        """Update format information display."""
        cursor = self.text_edit.textCursor()
        format_info = []

        char_format = cursor.charFormat()

        if char_format.font().bold():
            format_info.append("Bold")
        if char_format.font().italic():
            format_info.append("Italic")
        if char_format.font().underline():
            format_info.append("Underline")

        if format_info:
            self.format_info_label.setText(f"Format: {', '.join(format_info)}")
        else:
            self.format_info_label.setText("Plain text mode")

    def _apply_font_family(self, font: QFont) -> None:
        """Apply font family to selection."""
        char_format = QTextCharFormat()
        char_format.setFont(font)
        self._apply_char_format(char_format)

    def _apply_font_size(self, size: int) -> None:
        """Apply font size to selection."""
        char_format = QTextCharFormat()
        char_format.setFontPointSize(size)
        self._apply_char_format(char_format)

    def _apply_bold(self) -> None:
        """Apply bold formatting to selection."""
        char_format = QTextCharFormat()
        char_format.setFontWeight(QFont.Weight.Bold if self.bold_action.isChecked() else QFont.Weight.Normal)
        self._apply_char_format(char_format)

    def _apply_italic(self) -> None:
        """Apply italic formatting to selection."""
        char_format = QTextCharFormat()
        char_format.setFontItalic(self.italic_action.isChecked())
        self._apply_char_format(char_format)

    def _apply_underline(self) -> None:
        """Apply underline formatting to selection."""
        char_format = QTextCharFormat()
        char_format.setFontUnderline(self.underline_action.isChecked())
        self._apply_char_format(char_format)

    def _choose_text_color(self) -> None:
        """Choose text color."""
        color = QColorDialog.getColor(QColor("black"), self, "Choose Text Color")
        if color.isValid():
            char_format = QTextCharFormat()
            char_format.setForeground(color)
            self._apply_char_format(char_format)

            # Update button color
            self.text_color_btn.setStyleSheet(f"color: {color.name()}; font-weight: bold;")

    def _clear_formatting(self) -> None:
        """Clear all formatting from selection."""
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            char_format = QTextCharFormat()
            cursor.setCharFormat(char_format)
        else:
            self.text_edit.setCurrentCharFormat(QTextCharFormat())

    def _apply_char_format(self, char_format: QTextCharFormat) -> None:
        """Apply character format to current selection."""
        cursor = self.text_edit.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(char_format)
        else:
            self.text_edit.mergeCurrentCharFormat(char_format)

    def get_html(self) -> str:
        """Get the rich text content as HTML."""
        return self.text_edit.toHtml()

    def get_plain_text(self) -> str:
        """Get the content as plain text."""
        return self.text_edit.toPlainText()

    def set_html(self, html: str) -> None:
        """Set content from HTML."""
        self.text_edit.setHtml(html)

    def set_plain_text(self, text: str) -> None:
        """Set content from plain text."""
        self.text_edit.setPlainText(text)

    def clear(self) -> None:
        """Clear all content."""
        self.text_edit.clear()

    def is_empty(self) -> bool:
        """Check if editor is empty."""
        return len(self.text_edit.toPlainText().strip()) == 0
