#!/usr/bin/env python3
"""
Responsive System Info Widget
============================

Container widget that handles adaptive layout for system information cards.
Provides responsive behavior that adapts to different window sizes with
1-3 column layouts and proper scrolling support.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QFont, QResizeEvent
    from PyQt6.QtWidgets import (
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QScrollArea,
        QSizePolicy,
        QSpacerItem,
        QVBoxLayout,
        QWidget,
    )

# PyQt6 imports
try:
    from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QFont, QResizeEvent
    from PyQt6.QtWidgets import (
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QScrollArea,
        QSizePolicy,
        QSpacerItem,
        QVBoxLayout,
        QWidget,
    )

    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

from system_info_cards import InfoCard, MetricWidget
from system_info_formatter import SystemInfoFormatter


class ResponsiveGridLayout(QGridLayout):  # type: ignore
    """Custom grid layout that adapts number of columns based on available width."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the responsive grid layout."""
        super().__init__(parent)

        self.logger = logging.getLogger(__name__)
        self.min_card_width = 300
        self.max_card_width = 500
        self.card_spacing = 16
        self.current_columns = 1

        # Set layout properties
        self.setSpacing(self.card_spacing)
        self.setContentsMargins(16, 16, 16, 16)

    def calculate_optimal_columns(self, available_width: int) -> int:
        """Calculate optimal number of columns based on available width."""
        try:
            # Account for margins and spacing
            usable_width = available_width - (self.contentsMargins().left() + self.contentsMargins().right())

            # Start with maximum columns and work down
            for columns in range(3, 0, -1):
                # Calculate width per column including spacing
                spacing_width = (columns - 1) * self.card_spacing
                width_per_column = (usable_width - spacing_width) / columns

                # Check if cards fit comfortably
                if width_per_column >= self.min_card_width:
                    return columns

            return 1  # Fallback to single column

        except Exception as e:
            self.logger.warning(f"Failed to calculate optimal columns: {e}")
            return 1

    def relayout_cards(self, available_width: int) -> None:
        """Relayout cards based on available width."""
        try:
            optimal_columns = self.calculate_optimal_columns(available_width)

            if optimal_columns != self.current_columns:
                self.current_columns = optimal_columns
                self._reorganize_items()

        except Exception as e:
            self.logger.error(f"Failed to relayout cards: {e}")

    def _reorganize_items(self) -> None:
        """Reorganize items in the grid based on current column count."""
        try:
            # Check if layout is still valid
            try:
                current_count = self.count()
            except RuntimeError:
                self.logger.warning("Layout has been deleted, cannot reorganize")
                return

            # Collect all widgets currently in the layout
            widgets = []
            while self.count() > 0:
                item = self.takeAt(0)
                if item and item.widget():
                    widget = item.widget()
                    if widget:
                        widgets.append(widget)

            # Re-add widgets in new grid layout
            for i, widget in enumerate(widgets):
                try:
                    row = i // self.current_columns
                    col = i % self.current_columns
                    self.addWidget(widget, row, col)
                except RuntimeError:
                    self.logger.warning(f"Failed to add widget {i} to layout (widget may be deleted)")
                    continue

            # Ensure equal column stretching
            for col in range(self.current_columns):
                try:
                    self.setColumnStretch(col, 1)
                except RuntimeError:
                    pass  # Layout may be deleted

            self.logger.debug(f"Reorganized {len(widgets)} cards into {self.current_columns} columns")

        except Exception as e:
            self.logger.error(f"Failed to reorganize items: {e}")


class SystemInfoHeader(QWidget):  # type: ignore
    """Header widget for the system info display."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the header widget."""
        super().__init__(parent)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the header UI."""
        layout = QHBoxLayout(self)  # type: ignore
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Title
        title_label = QLabel("System Information")  # type: ignore
        title_font = QFont()  # type: ignore
        title_font.setPointSize(16)
        title_font.setWeight(QFont.Weight.Bold)  # type: ignore
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #333333;")

        layout.addWidget(title_label)
        layout.addStretch()

        # Status label (for showing refresh status, etc.)
        self.status_label = QLabel("")  # type: ignore
        status_font = QFont()  # type: ignore
        status_font.setPointSize(10)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet("color: #666666;")

        layout.addWidget(self.status_label)

    def set_status(self, status: str) -> None:
        """Set the status text."""
        self.status_label.setText(status)

    def clear_status(self) -> None:
        """Clear the status text."""
        self.status_label.setText("")


class ResponsiveSystemInfoWidget(QWidget):  # type: ignore
    """
    Main responsive container for system information display.

    Features:
    - Adaptive grid layout (1-3 columns based on width)
    - Smooth scrolling support
    - Real-time data updates
    - Modern card-based design
    """

    # Signals
    refresh_requested = pyqtSignal()  # type: ignore
    card_clicked = pyqtSignal(str)  # type: ignore  # Card category

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the responsive system info widget."""
        super().__init__(parent)

        self.logger = logging.getLogger(__name__)
        self.formatter = SystemInfoFormatter()
        self.cards: List[InfoCard] = []
        self.current_data: Dict[str, Any] = {}

        # Resize timer to avoid excessive layout updates
        self.resize_timer = QTimer()  # type: ignore
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._handle_delayed_resize)

        # Setup UI
        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self) -> None:
        """Setup the main UI layout."""
        try:
            # Main layout
            main_layout = QVBoxLayout(self)  # type: ignore
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)

            # Header
            self.header = SystemInfoHeader()
            main_layout.addWidget(self.header)

            # Scroll area for cards
            self.scroll_area = QScrollArea()  # type: ignore
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # type: ignore
            self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # type: ignore
            self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)  # type: ignore

            # Container widget for cards
            self.cards_container = QWidget()  # type: ignore
            self.cards_layout = ResponsiveGridLayout(self.cards_container)
            self.cards_container.setLayout(self.cards_layout)

            # Set container in scroll area
            self.scroll_area.setWidget(self.cards_container)
            main_layout.addWidget(self.scroll_area)

            # No data placeholder
            self._create_placeholder()

        except Exception as e:
            self.logger.error(f"Failed to setup ResponsiveSystemInfoWidget UI: {e}")

    def _create_placeholder(self) -> None:
        """Create placeholder for when no data is available."""
        self.placeholder_widget = QWidget()  # type: ignore
        placeholder_layout = QVBoxLayout(self.placeholder_widget)  # type: ignore
        placeholder_layout.setContentsMargins(40, 40, 40, 40)
        placeholder_layout.setSpacing(16)

        # Icon/emoji
        icon_label = QLabel("🖥️")  # type: ignore
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        icon_font = QFont()  # type: ignore
        icon_font.setPointSize(48)
        icon_label.setFont(icon_font)

        # Message
        message_label = QLabel("No system information available")  # type: ignore
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        message_font = QFont()  # type: ignore
        message_font.setPointSize(14)
        message_font.setWeight(QFont.Weight.Medium)  # type: ignore
        message_label.setFont(message_font)
        message_label.setStyleSheet("color: #666666;")

        # Instruction
        instruction_label = QLabel("Click 'Collect System Specs' to gather system information")  # type: ignore
        instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        instruction_label.setWordWrap(True)
        instruction_font = QFont()  # type: ignore
        instruction_font.setPointSize(12)
        instruction_label.setFont(instruction_font)
        instruction_label.setStyleSheet("color: #999999;")

        placeholder_layout.addStretch()
        placeholder_layout.addWidget(icon_label)
        placeholder_layout.addWidget(message_label)
        placeholder_layout.addWidget(instruction_label)
        placeholder_layout.addStretch()

        # Initially show placeholder
        self.scroll_area.setWidget(self.placeholder_widget)

    def _apply_styling(self) -> None:
        """Apply styling to the widget."""
        try:
            style = """
            ResponsiveSystemInfoWidget {
                background-color: #f8f9fa;
                border: none;
            }
            QScrollArea {
                background-color: #f8f9fa;
                border: none;
            }
            """
            self.setStyleSheet(style)

        except Exception as e:
            self.logger.warning(f"Failed to apply styling: {e}")

    def update_system_data(self, system_specs: Dict[str, Any]) -> None:
        """Update the display with new system data."""
        try:
            self.current_data = system_specs
            self.header.set_status("Formatting data...")

            # Format data into cards
            card_data_list = self.formatter.format_system_data(system_specs)

            # Clear existing cards
            self._clear_cards()

            # Create new cards
            self.cards = []
            for card_data in card_data_list:
                card = InfoCard(card_data)
                self.cards.append(card)
                self.cards_layout.addWidget(card)

            # Switch from placeholder to cards container
            if self.cards:
                self.scroll_area.setWidget(self.cards_container)
                self.header.set_status(f"Showing {len(self.cards)} information categories")

                # Trigger initial layout
                self._handle_delayed_resize()
            else:
                self.scroll_area.setWidget(self.placeholder_widget)
                self.header.set_status("No system information to display")

            self.logger.info(f"Updated system info display with {len(self.cards)} cards")

        except Exception as e:
            self.logger.error(f"Failed to update system data: {e}")
            self.header.set_status("Error formatting system data")

    def _clear_cards(self) -> None:
        """Clear all existing cards from the layout."""
        try:
            # Clear cards list first
            self.cards.clear()

            # Check if layout still exists and is valid
            if not hasattr(self, "cards_layout") or self.cards_layout is None:
                self.logger.debug("Cards layout not available for clearing")
                return

            # Check if layout is still valid (not deleted by Qt)
            try:
                count = self.cards_layout.count()
                self.logger.debug(f"Clearing {count} widgets from layout")
            except RuntimeError:
                self.logger.info("Cards layout was deleted, recreating...")
                self._recreate_cards_layout()
                return

            # Safely remove all widgets from layout
            widgets_to_delete = []
            while self.cards_layout.count() > 0:
                item = self.cards_layout.takeAt(0)
                if item and hasattr(item, "widget") and item.widget():
                    widget = item.widget()
                    if widget:
                        widgets_to_delete.append(widget)

            # Delete widgets after removing from layout
            for widget in widgets_to_delete:
                try:
                    widget.setParent(None)
                    widget.deleteLater()
                except RuntimeError:
                    pass  # Widget already deleted

        except Exception as e:
            self.logger.error(f"Failed to clear cards: {e}")
            # Only recreate if absolutely necessary
            if not hasattr(self, "cards_layout") or self.cards_layout is None:
                self._recreate_cards_layout()

    def _recreate_cards_layout(self) -> None:
        """Recreate the cards layout if it becomes corrupted."""
        try:
            # Create new container and layout
            self.cards_container = QWidget()  # type: ignore
            self.cards_layout = ResponsiveGridLayout(self.cards_container)
            self.cards_container.setLayout(self.cards_layout)

            # Set container in scroll area
            self.scroll_area.setWidget(self.cards_container)

            self.logger.info("Cards layout recreated successfully")

        except Exception as e:
            self.logger.error(f"Failed to recreate cards layout: {e}")

    def refresh_data(self) -> None:
        """Request a data refresh."""
        try:
            self.header.set_status("Refreshing system information...")
            self.refresh_requested.emit()

        except Exception as e:
            self.logger.error(f"Failed to refresh data: {e}")

    def get_card_count(self) -> int:
        """Get the current number of cards."""
        return len(self.cards)

    def get_current_columns(self) -> int:
        """Get the current number of columns."""
        return self.cards_layout.current_columns

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore
        """Handle widget resize events."""
        super().resizeEvent(event)

        # Use timer to debounce resize events
        self.resize_timer.stop()
        self.resize_timer.start(100)  # 100ms delay

    def _handle_delayed_resize(self) -> None:
        """Handle delayed resize to update layout."""
        try:
            if self.cards:
                viewport = self.scroll_area.viewport()
                if viewport:
                    available_width = viewport.width()
                    self.cards_layout.relayout_cards(available_width)

                    # Update status with layout info
                    columns = self.cards_layout.current_columns
                    self.header.set_status(
                        f"Showing {len(self.cards)} categories in {columns} column{'s' if columns != 1 else ''}"
                    )

        except Exception as e:
            self.logger.error(f"Failed to handle delayed resize: {e}")

    def set_loading_state(self, loading: bool, message: str = "") -> None:
        """Set the loading state of the widget."""
        try:
            if loading:
                self.header.set_status(message or "Loading system information...")
                # Could add a loading spinner here
            else:
                self.header.clear_status()

        except Exception as e:
            self.logger.error(f"Failed to set loading state: {e}")

    def export_data(self) -> Dict[str, Any]:
        """Export current system data for saving/sharing."""
        return self.current_data.copy()

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics about the displayed data."""
        try:
            stats = {
                "total_cards": len(self.cards),
                "current_columns": self.cards_layout.current_columns,
                "widget_width": self.width(),
                "has_data": bool(self.current_data),
                "categories": [],
            }

            # Add category information
            for card in self.cards:
                category = card.card_data.get("category", "unknown")
                title = card.card_data.get("title", "Unknown")
                item_count = len(card.card_data.get("items", []))

                stats["categories"].append({"category": category, "title": title, "item_count": item_count})

            return stats

        except Exception as e:
            self.logger.error(f"Failed to get summary stats: {e}")
            return {"error": str(e)}
