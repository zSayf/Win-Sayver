#!/usr/bin/env python3
"""
System Info Cards - Modern UI Components
========================================

Professional PyQt6 widgets for displaying system information in a modern,
card-based layout with responsive design and visual appeal.

Includes InfoCard, MetricWidget, and specialized display components.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from PyQt6.QtCore import QSize, Qt, pyqtSignal
    from PyQt6.QtGui import QFont, QPainter, QPaintEvent, QResizeEvent
    from PyQt6.QtWidgets import (
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QScrollArea,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

# PyQt6 imports
try:
    from PyQt6.QtCore import (
        QEasingCurve,
        QPropertyAnimation,
        QRect,
        QSize,
        Qt,
        pyqtSignal,
    )
    from PyQt6.QtGui import (
        QBrush,
        QColor,
        QFont,
        QPainter,
        QPaintEvent,
        QPen,
        QResizeEvent,
    )
    from PyQt6.QtWidgets import (
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QProgressBar,
        QScrollArea,
        QSizePolicy,
        QSpacerItem,
        QVBoxLayout,
        QWidget,
    )

    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


class InfoCard(QFrame):  # type: ignore
    """
    Base card widget for displaying grouped system information.

    Features modern styling with rounded corners, subtle shadows,
    and organized content layout.
    """

    def __init__(self, card_data: Dict[str, Any], parent: Optional[QWidget] = None):
        """
        Initialize the info card.

        Args:
            card_data: Dictionary containing card information
            parent: Parent widget
        """
        super().__init__(parent)

        self.logger = logging.getLogger(__name__)
        self.card_data = card_data

        # Setup card properties
        self.setFrameStyle(QFrame.Shape.Box)  # type: ignore
        self.setLineWidth(0)

        # Set size policies
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)  # type: ignore
        self.setMinimumWidth(300)
        self.setMaximumWidth(500)
        self.setMinimumHeight(120)

        # Setup layout and content
        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self) -> None:
        """Setup the card UI layout."""
        try:
            # Main layout
            main_layout = QVBoxLayout(self)  # type: ignore
            main_layout.setContentsMargins(20, 16, 20, 16)
            main_layout.setSpacing(12)

            # Header section
            header_layout = self._create_header()
            main_layout.addLayout(header_layout)

            # Content section
            content_layout = self._create_content()
            main_layout.addLayout(content_layout)

            # Spacer to push content to top
            spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)  # type: ignore
            main_layout.addItem(spacer)

        except Exception as e:
            self.logger.error(f"Failed to setup InfoCard UI: {e}")

    def _create_header(self) -> QHBoxLayout:  # type: ignore
        """Create the card header with title and category color."""
        header_layout = QHBoxLayout()  # type: ignore
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        # Title label
        title = self.card_data.get("title", "Information")
        self.title_label = QLabel(title)  # type: ignore

        # Title font
        title_font = QFont()  # type: ignore
        title_font.setPointSize(14)
        title_font.setWeight(QFont.Weight.Bold)  # type: ignore
        self.title_label.setFont(title_font)

        # Title color based on category
        color = self.card_data.get("color", "#2196F3")
        self.title_label.setStyleSheet(f"color: {color}; margin: 0; padding: 0;")

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        return header_layout

    def _create_content(self) -> QVBoxLayout:  # type: ignore
        """Create the card content area."""
        content_layout = QVBoxLayout()  # type: ignore
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        # Add all items from card data
        items = self.card_data.get("items", [])

        for item in items:
            item_widget = self._create_item_widget(item)
            if item_widget:
                content_layout.addWidget(item_widget)

        return content_layout

    def _create_item_widget(self, item: Dict[str, Any]) -> Optional[QWidget]:  # type: ignore
        """Create a widget for a single item."""
        try:
            item_type = item.get("type", "text")

            if item_type == "text":
                return self._create_text_item(item)
            elif item_type == "progress":
                return self._create_progress_item(item)
            elif item_type == "status":
                return self._create_status_item(item)
            else:
                return self._create_text_item(item)  # Fallback

        except Exception as e:
            self.logger.warning(f"Failed to create item widget: {e}")
            return None

    def _create_text_item(self, item: Dict[str, Any]) -> QWidget:  # type: ignore
        """Create a simple text item."""
        widget = QWidget()  # type: ignore
        layout = QHBoxLayout(widget)  # type: ignore
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        # Label
        label = item.get("label", "")
        label_widget = QLabel(label + ":")  # type: ignore
        label_widget.setMinimumWidth(120)
        label_widget.setMaximumWidth(150)
        label_widget.setWordWrap(False)

        # Label font
        label_font = QFont()  # type: ignore
        label_font.setPointSize(10)
        label_font.setWeight(QFont.Weight.Medium)  # type: ignore
        label_widget.setFont(label_font)
        label_widget.setStyleSheet("color: #666666;")

        layout.addWidget(label_widget)

        # Value
        value = item.get("value", "")
        value_widget = QLabel(str(value))  # type: ignore
        value_widget.setWordWrap(True)
        try:
            value_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)  # type: ignore
        except AttributeError:
            # Fallback for older PyQt6 versions
            value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)  # type: ignore

        # Value font
        value_font = QFont()  # type: ignore
        value_font.setPointSize(10)
        value_widget.setFont(value_font)
        value_widget.setStyleSheet("color: #333333;")

        layout.addWidget(value_widget)
        layout.addStretch()

        return widget

    def _create_progress_item(self, item: Dict[str, Any]) -> QWidget:  # type: ignore
        """Create a progress bar item."""
        widget = QWidget()  # type: ignore
        layout = QVBoxLayout(widget)  # type: ignore
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)

        # Label and value row
        top_layout = QHBoxLayout()  # type: ignore
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        # Label
        label = item.get("label", "")
        label_widget = QLabel(label + ":")  # type: ignore
        label_font = QFont()  # type: ignore
        label_font.setPointSize(10)
        label_font.setWeight(QFont.Weight.Medium)  # type: ignore
        label_widget.setFont(label_font)
        label_widget.setStyleSheet("color: #666666;")

        top_layout.addWidget(label_widget)
        top_layout.addStretch()

        # Value
        value = item.get("value", "")
        value_widget = QLabel(str(value))  # type: ignore
        value_font = QFont()  # type: ignore
        value_font.setPointSize(10)
        value_font.setWeight(QFont.Weight.Medium)  # type: ignore
        value_widget.setFont(value_font)
        value_widget.setStyleSheet("color: #333333;")

        top_layout.addWidget(value_widget)

        layout.addLayout(top_layout)

        # Progress bar
        progress_value = item.get("progress", 0)
        progress_color = item.get("color", "#2196F3")

        progress_bar = QProgressBar()  # type: ignore
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        progress_bar.setValue(int(progress_value))
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(8)

        # Custom progress bar styling
        progress_style = f"""
        QProgressBar {{
            border: none;
            border-radius: 4px;
            background-color: #f0f0f0;
        }}
        QProgressBar::chunk {{
            background-color: {progress_color};
            border-radius: 4px;
        }}
        """
        progress_bar.setStyleSheet(progress_style)

        layout.addWidget(progress_bar)

        return widget

    def _create_status_item(self, item: Dict[str, Any]) -> QWidget:  # type: ignore
        """Create a status indicator item."""
        widget = QWidget()  # type: ignore
        layout = QHBoxLayout(widget)  # type: ignore
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        # Label
        label = item.get("label", "")
        label_widget = QLabel(label + ":")  # type: ignore
        label_widget.setMinimumWidth(120)
        label_widget.setMaximumWidth(150)

        label_font = QFont()  # type: ignore
        label_font.setPointSize(10)
        label_font.setWeight(QFont.Weight.Medium)  # type: ignore
        label_widget.setFont(label_font)
        label_widget.setStyleSheet("color: #666666;")

        layout.addWidget(label_widget)

        # Status indicator
        status = item.get("status", "normal")
        status_colors = {
            "normal": "#4CAF50",  # Green
            "warning": "#FF9800",  # Orange
            "critical": "#F44336",  # Red
            "info": "#2196F3",  # Blue
        }

        status_color = status_colors.get(status, "#4CAF50")

        # Status dot
        status_indicator = QLabel("●")  # type: ignore
        status_indicator.setFixedSize(16, 16)
        status_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        status_indicator.setStyleSheet(f"color: {status_color}; font-size: 12px;")

        layout.addWidget(status_indicator)

        # Value
        value = item.get("value", "")
        value_widget = QLabel(str(value))  # type: ignore

        value_font = QFont()  # type: ignore
        value_font.setPointSize(10)
        value_widget.setFont(value_font)
        value_widget.setStyleSheet("color: #333333;")

        layout.addWidget(value_widget)
        layout.addStretch()

        return widget

    def _apply_styling(self) -> None:
        """Apply modern card styling."""
        try:
            # Card background and border
            style = """
            InfoCard {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin: 4px;
            }
            InfoCard:hover {
                border: 1px solid #cccccc;
                background-color: #fafafa;
            }
            """

            self.setStyleSheet(style)

        except Exception as e:
            self.logger.warning(f"Failed to apply card styling: {e}")

    def update_card_data(self, new_data: Dict[str, Any]) -> None:
        """Update the card with new data."""
        try:
            self.card_data = new_data

            # Clear existing layout
            layout = self.layout()
            if layout:
                while layout.count():
                    child = layout.takeAt(0)
                    if child:
                        widget = child.widget()
                        if widget:
                            widget.deleteLater()

            # Rebuild UI
            self._setup_ui()
            self._apply_styling()

        except Exception as e:
            self.logger.error(f"Failed to update card data: {e}")


class MetricWidget(QWidget):  # type: ignore
    """Specialized widget for displaying metrics with visual indicators."""

    def __init__(
        self, title: str, value: str, progress: float = 0, color: str = "#2196F3", parent: Optional[QWidget] = None
    ):
        """Initialize the metric widget."""
        super().__init__(parent)

        self.logger = logging.getLogger(__name__)
        self.title = title
        self.value = value
        self.progress = progress
        self.color = color

        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self) -> None:
        """Setup the metric widget UI."""
        try:
            layout = QVBoxLayout(self)  # type: ignore
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(8)

            # Title
            title_label = QLabel(self.title)  # type: ignore
            title_font = QFont()  # type: ignore
            title_font.setPointSize(10)
            title_font.setWeight(QFont.Weight.Medium)  # type: ignore
            title_label.setFont(title_font)
            title_label.setStyleSheet("color: #666666;")

            layout.addWidget(title_label)

            # Value
            value_label = QLabel(self.value)  # type: ignore
            value_font = QFont()  # type: ignore
            value_font.setPointSize(18)
            value_font.setWeight(QFont.Weight.Bold)  # type: ignore
            value_label.setFont(value_font)
            value_label.setStyleSheet(f"color: {self.color};")

            layout.addWidget(value_label)

            # Progress bar (if progress > 0)
            if self.progress > 0:
                progress_bar = QProgressBar()  # type: ignore
                progress_bar.setMinimum(0)
                progress_bar.setMaximum(100)
                progress_bar.setValue(int(self.progress))
                progress_bar.setTextVisible(False)
                progress_bar.setFixedHeight(6)

                progress_style = f"""
                QProgressBar {{
                    border: none;
                    border-radius: 3px;
                    background-color: #f0f0f0;
                }}
                QProgressBar::chunk {{
                    background-color: {self.color};
                    border-radius: 3px;
                }}
                """
                progress_bar.setStyleSheet(progress_style)

                layout.addWidget(progress_bar)

        except Exception as e:
            self.logger.error(f"Failed to setup MetricWidget UI: {e}")

    def _apply_styling(self) -> None:
        """Apply styling to the metric widget."""
        style = """
        MetricWidget {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            margin: 2px;
        }
        MetricWidget:hover {
            border: 1px solid #cccccc;
        }
        """
        self.setStyleSheet(style)

    def update_metric(self, value: str, progress: Optional[float] = None) -> None:
        """Update the metric value and progress."""
        try:
            self.value = value
            if progress is not None:
                self.progress = progress

            # Rebuild UI with new values
            layout = self.layout()
            if layout:
                while layout.count():
                    child = layout.takeAt(0)
                    if child:
                        widget = child.widget()
                        if widget:
                            widget.deleteLater()

            self._setup_ui()

        except Exception as e:
            self.logger.error(f"Failed to update metric: {e}")
