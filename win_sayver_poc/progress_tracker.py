#!/usr/bin/env python3
"""
Progress Tracking System for Win Sayver GUI
===========================================

Comprehensive progress tracking with thinking process visualization,
token usage monitoring, and real-time analysis status updates.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPalette

# PyQt6 imports - required for Win Sayver GUI
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass
class AnalysisStep:
    """Data class for analysis step tracking."""

    name: str
    status: str  # pending, in_progress, complete, error
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    details: str = ""
    thinking_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ThinkingStep:
    """Data class for AI thinking process steps."""

    step_number: int
    content: str
    timestamp: datetime
    confidence: float = 0.0
    reasoning_type: str = "analysis"  # analysis, hypothesis, validation, conclusion


class ThinkingVisualizationWidget(QWidget):
    """Widget for visualizing AI thinking process in real-time."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.thinking_steps = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup thinking visualization UI."""
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()

        title_label = QLabel("🧠 AI Thinking Process")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Thinking status indicator
        self.thinking_status_label = QLabel("💭 Ready")
        self.thinking_status_label.setStyleSheet("color: #666666; font-weight: bold;")
        header_layout.addWidget(self.thinking_status_label)

        layout.addLayout(header_layout)

        # Thinking steps scroll area
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.thinking_layout = QVBoxLayout(scroll_widget)
        self.thinking_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(200)
        scroll_area.setStyleSheet(
            """
            QScrollArea {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """
        )

        layout.addWidget(scroll_area)

        # Thinking metrics
        metrics_layout = QHBoxLayout()

        self.step_count_label = QLabel("Steps: 0")
        self.step_count_label.setStyleSheet("font-size: 11px; color: #666666;")
        metrics_layout.addWidget(self.step_count_label)

        self.thinking_time_label = QLabel("Duration: 0s")
        self.thinking_time_label.setStyleSheet("font-size: 11px; color: #666666;")
        metrics_layout.addWidget(self.thinking_time_label)

        metrics_layout.addStretch()

        self.token_usage_label = QLabel("Tokens: 0")
        self.token_usage_label.setStyleSheet("font-size: 11px; color: #666666;")
        metrics_layout.addWidget(self.token_usage_label)

        layout.addLayout(metrics_layout)

    def add_thinking_step(self, step: ThinkingStep) -> None:
        """Add a new thinking step to the visualization."""
        self.thinking_steps.append(step)

        # Create step widget
        step_widget = self._create_step_widget(step)
        self.thinking_layout.addWidget(step_widget)

        # Update status and metrics
        self.thinking_status_label.setText("🤔 Thinking...")
        self.step_count_label.setText(f"Steps: {len(self.thinking_steps)}")

        # Scroll to bottom with proper type checking
        parent_widget = self.parent()
        if parent_widget:
            scroll_area = parent_widget.findChild(QScrollArea)
            if scroll_area and isinstance(scroll_area, QScrollArea):
                scroll_bar = scroll_area.verticalScrollBar()
                if scroll_bar:
                    scroll_bar.setValue(scroll_bar.maximum())

    def _create_step_widget(self, step: ThinkingStep) -> QWidget:
        """Create widget for individual thinking step."""
        step_widget = QFrame()
        step_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        step_widget.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                margin: 2px;
                padding: 5px;
            }
        """
        )

        layout = QVBoxLayout(step_widget)
        layout.setContentsMargins(8, 6, 8, 6)

        # Step header
        header_layout = QHBoxLayout()

        step_label = QLabel(f"Step {step.step_number}")
        step_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        header_layout.addWidget(step_label)

        # Reasoning type badge
        type_badge = QLabel(step.reasoning_type.title())
        type_badge.setStyleSheet(
            f"""
            background-color: {self._get_type_color(step.reasoning_type)};
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: bold;
        """
        )
        header_layout.addWidget(type_badge)

        header_layout.addStretch()

        # Timestamp
        time_label = QLabel(step.timestamp.strftime("%H:%M:%S.%f")[:-3])
        time_label.setStyleSheet("font-size: 10px; color: #666666;")
        header_layout.addWidget(time_label)

        layout.addLayout(header_layout)

        # Step content
        content_label = QLabel(step.content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("margin: 4px 0px;")
        layout.addWidget(content_label)

        # Confidence indicator
        if step.confidence > 0:
            confidence_layout = QHBoxLayout()
            confidence_layout.addWidget(QLabel("Confidence:"))

            confidence_bar = QProgressBar()
            confidence_bar.setMaximumHeight(8)
            confidence_bar.setRange(0, 100)
            confidence_bar.setValue(int(step.confidence * 100))
            confidence_bar.setStyleSheet(
                """
                QProgressBar {
                    border: 1px solid #cccccc;
                    border-radius: 3px;
                    background-color: #f0f0f0;
                }
                QProgressBar::chunk {
                    background-color: #4caf50;
                    border-radius: 2px;
                }
            """
            )
            confidence_layout.addWidget(confidence_bar)

            confidence_layout.addWidget(QLabel(f"{step.confidence:.1%}"))
            layout.addLayout(confidence_layout)

        return step_widget

    def _get_type_color(self, reasoning_type: str) -> str:
        """Get color for reasoning type badge."""
        colors = {
            "analysis": "#2196F3",  # Blue
            "hypothesis": "#FF9800",  # Orange
            "validation": "#4CAF50",  # Green
            "conclusion": "#9C27B0",  # Purple
        }
        return colors.get(reasoning_type, "#666666")

    def update_thinking_metrics(self, duration: float, tokens: int) -> None:
        """Update thinking process metrics."""
        self.thinking_time_label.setText(f"Duration: {duration:.1f}s")
        self.token_usage_label.setText(f"Tokens: {tokens:,}")

    def complete_thinking(self) -> None:
        """Mark thinking process as complete."""
        self.thinking_status_label.setText("✅ Complete")
        self.thinking_status_label.setStyleSheet("color: #4caf50; font-weight: bold;")

    def clear_thinking(self) -> None:
        """Clear all thinking steps."""
        self.thinking_steps.clear()

        # Clear layout with proper type handling
        for i in reversed(range(self.thinking_layout.count())):
            layout_item = self.thinking_layout.itemAt(i)
            if layout_item:
                widget = layout_item.widget()
                if widget:
                    # Properly handle setParent with type ignore for Qt compatibility
                    widget.setParent(None)  # type: ignore[arg-type]

        # Reset status
        self.thinking_status_label.setText("💭 Ready")
        self.thinking_status_label.setStyleSheet("color: #666666; font-weight: bold;")
        self.step_count_label.setText("Steps: 0")
        self.thinking_time_label.setText("Duration: 0s")
        self.token_usage_label.setText("Tokens: 0")


class TokenUsageWidget(QWidget):
    """Widget for monitoring token usage and costs."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.total_tokens = 0
        self.thinking_tokens = 0
        self.request_count = 0
        self.estimated_cost = 0.0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup token usage UI."""
        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("💰 Token Usage & Costs")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # Token metrics
        metrics_widget = QFrame()
        metrics_widget.setFrameStyle(QFrame.Shape.StyledPanel)
        metrics_widget.setStyleSheet(
            """
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 10px;
            }
        """
        )

        metrics_layout = QVBoxLayout(metrics_widget)

        # Total tokens
        total_layout = QHBoxLayout()
        total_layout.addWidget(QLabel("Total Tokens:"))
        total_layout.addStretch()
        self.total_tokens_label = QLabel("0")
        self.total_tokens_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        total_layout.addWidget(self.total_tokens_label)
        metrics_layout.addLayout(total_layout)

        # Thinking tokens
        thinking_layout = QHBoxLayout()
        thinking_layout.addWidget(QLabel("Thinking Tokens:"))
        thinking_layout.addStretch()
        self.thinking_tokens_label = QLabel("0")
        self.thinking_tokens_label.setStyleSheet("font-weight: bold; color: #FF9800;")
        thinking_layout.addWidget(self.thinking_tokens_label)
        metrics_layout.addLayout(thinking_layout)

        # Request count
        request_layout = QHBoxLayout()
        request_layout.addWidget(QLabel("API Requests:"))
        request_layout.addStretch()
        self.request_count_label = QLabel("0")
        self.request_count_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        request_layout.addWidget(self.request_count_label)
        metrics_layout.addLayout(request_layout)

        # Estimated cost
        cost_layout = QHBoxLayout()
        cost_layout.addWidget(QLabel("Estimated Cost:"))
        cost_layout.addStretch()
        self.cost_label = QLabel("$0.00")
        self.cost_label.setStyleSheet("font-weight: bold; color: #9C27B0;")
        cost_layout.addWidget(self.cost_label)
        metrics_layout.addLayout(cost_layout)

        layout.addWidget(metrics_widget)

        # Usage chart (placeholder for future implementation)
        chart_label = QLabel("📊 Usage trends chart placeholder")
        chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_label.setStyleSheet("color: #666666; font-style: italic; margin: 20px;")
        layout.addWidget(chart_label)

    def update_usage(self, total_tokens: int, thinking_tokens: int, request_count: int) -> None:
        """Update token usage metrics."""
        self.total_tokens = total_tokens
        self.thinking_tokens = thinking_tokens
        self.request_count = request_count

        # Update labels
        self.total_tokens_label.setText(f"{self.total_tokens:,}")
        self.thinking_tokens_label.setText(f"{self.thinking_tokens:,}")
        self.request_count_label.setText(f"{self.request_count}")

        # Calculate estimated cost (rough estimate for Gemini pricing)
        # This is a simplified calculation - actual pricing may vary
        self.estimated_cost = (self.total_tokens / 1000) * 0.01  # $0.01 per 1K tokens (example)
        self.cost_label.setText(f"${self.estimated_cost:.4f}")

    def reset_usage(self) -> None:
        """Reset usage metrics."""
        self.update_usage(0, 0, 0)


class AnalysisProgressWidget(QWidget):
    """Widget for tracking overall analysis progress."""

    step_completed = pyqtSignal(str)  # step name

    def __init__(self, parent=None):
        super().__init__(parent)

        self.analysis_steps = []
        self.current_step_index = -1
        self.start_time = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup analysis progress UI."""
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()

        title_label = QLabel("📈 Analysis Progress")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Overall progress
        self.overall_progress_label = QLabel("Ready")
        self.overall_progress_label.setStyleSheet("color: #666666; font-weight: bold;")
        header_layout.addWidget(self.overall_progress_label)

        layout.addLayout(header_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 2px solid #cccccc;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2196F3, stop:1 #21CBF3);
                border-radius: 3px;
            }
        """
        )
        layout.addWidget(self.progress_bar)

        # Steps tree
        self.steps_tree = QTreeWidget()
        self.steps_tree.setHeaderLabels(["Step", "Status", "Duration", "Details"])
        self.steps_tree.setAlternatingRowColors(True)
        self.steps_tree.setRootIsDecorated(False)
        self.steps_tree.setMaximumHeight(200)

        # Set column widths
        self.steps_tree.setColumnWidth(0, 200)
        self.steps_tree.setColumnWidth(1, 80)
        self.steps_tree.setColumnWidth(2, 80)

        layout.addWidget(self.steps_tree)

        # Current step details
        self.current_step_label = QLabel("No active analysis")
        self.current_step_label.setStyleSheet(
            """
            background-color: #f0f0f0;
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 8px;
            margin: 5px 0px;
        """
        )
        layout.addWidget(self.current_step_label)

        # Timing information
        timing_layout = QHBoxLayout()

        self.elapsed_time_label = QLabel("Elapsed: 0s")
        self.elapsed_time_label.setStyleSheet("font-size: 11px; color: #666666;")
        timing_layout.addWidget(self.elapsed_time_label)

        timing_layout.addStretch()

        self.eta_label = QLabel("ETA: --")
        self.eta_label.setStyleSheet("font-size: 11px; color: #666666;")
        timing_layout.addWidget(self.eta_label)

        layout.addLayout(timing_layout)

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_timing)
        self.update_timer.start(1000)  # Update every second

    def start_analysis(self, steps: List[str]) -> None:
        """Start analysis with given steps."""
        self.analysis_steps = [AnalysisStep(name=step, status="pending") for step in steps]
        self.current_step_index = -1
        self.start_time = datetime.now()

        # Clear and populate tree
        self.steps_tree.clear()
        for step in self.analysis_steps:
            item = QTreeWidgetItem([step.name, "⏳ Pending", "", ""])
            self.steps_tree.addTopLevelItem(item)

        # Update UI
        self.progress_bar.setValue(0)
        self.overall_progress_label.setText("🚀 Starting...")
        self.current_step_label.setText("Initializing analysis...")

    def start_step(self, step_name: str, details: str = "") -> None:
        """Start a specific analysis step."""
        # Find step index
        step_index = -1
        for i, step in enumerate(self.analysis_steps):
            if step.name == step_name:
                step_index = i
                break

        if step_index == -1:
            return

        # Update step
        step = self.analysis_steps[step_index]
        step.status = "in_progress"
        step.start_time = datetime.now()
        step.details = details

        self.current_step_index = step_index

        # Update tree item
        item = self.steps_tree.topLevelItem(step_index)
        if item:
            item.setText(1, "🔄 Running")
            item.setText(3, details)

        # Update current step display
        self.current_step_label.setText(f"🔄 {step.name}: {details}")

        # Update progress
        progress = int((step_index / len(self.analysis_steps)) * 100)
        self.progress_bar.setValue(progress)
        self.overall_progress_label.setText(f"Step {step_index + 1}/{len(self.analysis_steps)}")

    def complete_step(self, step_name: str, success: bool = True, details: str = "") -> None:
        """Complete a specific analysis step."""
        # Find step
        step_index = -1
        for i, step in enumerate(self.analysis_steps):
            if step.name == step_name:
                step_index = i
                break

        if step_index == -1:
            return

        # Update step
        step = self.analysis_steps[step_index]
        step.status = "complete" if success else "error"
        step.end_time = datetime.now()
        if details:
            step.details = details

        # Calculate duration
        if step.start_time and step.end_time:
            duration = step.end_time - step.start_time
            duration_str = f"{duration.total_seconds():.1f}s"
        else:
            duration_str = ""

        # Update tree item
        item = self.steps_tree.topLevelItem(step_index)
        if item:
            if success:
                item.setText(1, "✅ Done")
                item.setForeground(1, QColor(34, 139, 34))  # Green
            else:
                item.setText(1, "❌ Error")
                item.setForeground(1, QColor(220, 20, 60))  # Red

            item.setText(2, duration_str)
            item.setText(3, step.details)

        # Emit signal
        self.step_completed.emit(step_name)

        # Check if all steps complete
        completed_steps = sum(1 for s in self.analysis_steps if s.status in ["complete", "error"])
        if completed_steps == len(self.analysis_steps):
            self._complete_analysis()
        else:
            # Update progress
            progress = int((completed_steps / len(self.analysis_steps)) * 100)
            self.progress_bar.setValue(progress)

    def _complete_analysis(self) -> None:
        """Complete the overall analysis."""
        self.progress_bar.setValue(100)
        self.overall_progress_label.setText("✅ Complete")
        self.current_step_label.setText("✅ Analysis completed successfully!")

        # Calculate total duration
        if self.start_time:
            total_duration = datetime.now() - self.start_time
            self.elapsed_time_label.setText(f"Total: {total_duration.total_seconds():.1f}s")

        self.eta_label.setText("Complete")

    def _update_timing(self) -> None:
        """Update timing information."""
        if not self.start_time:
            return

        elapsed = datetime.now() - self.start_time
        self.elapsed_time_label.setText(f"Elapsed: {elapsed.total_seconds():.0f}s")

        # Calculate ETA if we have progress
        completed_steps = sum(1 for s in self.analysis_steps if s.status in ["complete", "error"])
        if completed_steps > 0 and completed_steps < len(self.analysis_steps):
            avg_time_per_step = elapsed.total_seconds() / completed_steps
            remaining_steps = len(self.analysis_steps) - completed_steps
            eta_seconds = avg_time_per_step * remaining_steps
            self.eta_label.setText(f"ETA: {eta_seconds:.0f}s")
        else:
            self.eta_label.setText("--")


class ProgressTrackingSystem(QWidget):
    """Main progress tracking system widget."""

    analysis_started = pyqtSignal(list)  # step names
    step_started = pyqtSignal(str, str)  # step name, details
    step_completed = pyqtSignal(str, bool, str)  # step name, success, details
    thinking_step_added = pyqtSignal(object)  # ThinkingStep object

    def __init__(self, parent=None):
        super().__init__(parent)

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Setup progress tracking UI."""
        layout = QVBoxLayout(self)

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side - Analysis progress and token usage
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        # Analysis progress
        self.analysis_progress = AnalysisProgressWidget()
        left_layout.addWidget(self.analysis_progress)

        # Token usage
        self.token_usage = TokenUsageWidget()
        left_layout.addWidget(self.token_usage)

        splitter.addWidget(left_widget)

        # Right side - Thinking visualization
        self.thinking_viz = ThinkingVisualizationWidget()
        splitter.addWidget(self.thinking_viz)

        # Set splitter proportions
        splitter.setSizes([400, 500])

        layout.addWidget(splitter)

        # Control buttons
        button_layout = QHBoxLayout()

        self.clear_btn = QPushButton("🗑️ Clear All")
        self.clear_btn.clicked.connect(self._clear_all)
        button_layout.addWidget(self.clear_btn)

        button_layout.addStretch()

        self.export_btn = QPushButton("📊 Export Progress")
        self.export_btn.clicked.connect(self._export_progress)
        button_layout.addWidget(self.export_btn)

        layout.addLayout(button_layout)

    def _setup_connections(self) -> None:
        """Setup signal connections."""
        # Fix: Explicitly make lambda return None to satisfy signal requirements
        def on_step_completed(step: str) -> None:
            self.step_completed.emit(step, True, "")
        
        self.analysis_progress.step_completed.connect(on_step_completed)

    def start_analysis(self, steps: List[str]) -> None:
        """Start analysis tracking with given steps."""
        self.analysis_progress.start_analysis(steps)
        self.thinking_viz.clear_thinking()
        self.analysis_started.emit(steps)

    def update_step(self, step_name: str, status: str, details: str = "") -> None:
        """Update analysis step status."""
        if status == "start":
            self.analysis_progress.start_step(step_name, details)
            self.step_started.emit(step_name, details)
        elif status == "complete":
            self.analysis_progress.complete_step(step_name, True, details)
            self.step_completed.emit(step_name, True, details)
        elif status == "error":
            self.analysis_progress.complete_step(step_name, False, details)
            self.step_completed.emit(step_name, False, details)

    def add_thinking_step(self, content: str, reasoning_type: str = "analysis", confidence: float = 0.0) -> None:
        """Add AI thinking step."""
        step = ThinkingStep(
            step_number=len(self.thinking_viz.thinking_steps) + 1,
            content=content,
            timestamp=datetime.now(),
            confidence=confidence,
            reasoning_type=reasoning_type,
        )

        self.thinking_viz.add_thinking_step(step)
        self.thinking_step_added.emit(step)

    def update_token_usage(self, total_tokens: int, thinking_tokens: int, request_count: int) -> None:
        """Update token usage metrics."""
        self.token_usage.update_usage(total_tokens, thinking_tokens, request_count)

    def update_thinking_metrics(self, duration: float, tokens: int) -> None:
        """Update thinking process metrics."""
        self.thinking_viz.update_thinking_metrics(duration, tokens)

    def complete_thinking(self) -> None:
        """Mark thinking process as complete."""
        self.thinking_viz.complete_thinking()

    def _clear_all(self) -> None:
        """Clear all progress tracking data."""
        self.thinking_viz.clear_thinking()
        self.token_usage.reset_usage()
        # Reset analysis progress would need to be implemented

    def _export_progress(self) -> None:
        """Export progress data."""
        # TODO: Implement progress export functionality
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.information(
            self, "Export", "Progress export functionality will be implemented in the next version."
        )
