#!/usr/bin/env python3
"""
AI Analysis Workflow Integration for Win Sayver GUI
==================================================

Complete AI analysis workflow that integrates rich text editor,
system specs viewer, AI configuration, and progress tracking
for comprehensive Windows troubleshooting analysis.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ai_client import AIClient, AIClientError, APIKeyError
from ai_config_panel import AIConfiguration, AIConfigurationPanel
from image_widgets import MultiImageDropArea
from progress_tracker import ProgressTrackingSystem, ThinkingStep
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from rich_text_editor import RichTextEditor
from specs_collector import SystemSpecsCollector
from utils import PerformanceTimer


@dataclass
class AnalysisRequest:
    """Data class for analysis request."""

    images: List[str] = field(default_factory=list)
    error_description: str = ""
    system_specs: Optional[Dict[str, Any]] = None
    ai_config: Optional[AIConfiguration] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class AnalysisResult:
    """Data class for analysis result."""

    success: bool
    confidence_score: float = 0.0
    problem_summary: str = ""
    solutions: List[Dict[str, Any]] = field(default_factory=list)
    risk_assessment: str = ""
    thinking_process: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""


class AIAnalysisWorker(QThread):
    """Background worker for AI analysis processing."""

    # Signals
    analysis_started = pyqtSignal()
    step_started = pyqtSignal(str, str)  # step name, details
    step_completed = pyqtSignal(str, bool, str)  # step name, success, details
    thinking_step = pyqtSignal(str, str, float)  # content, type, confidence
    progress_updated = pyqtSignal(int)  # percentage
    token_usage_updated = pyqtSignal(int, int, int)  # total, thinking, requests
    analysis_completed = pyqtSignal(object)  # AnalysisResult
    analysis_error = pyqtSignal(str)  # error message

    def __init__(self, request: AnalysisRequest):
        super().__init__()
        self.request = request
        self.ai_client = None
        self.should_stop = False
        self.logger = logging.getLogger(__name__)

    def run(self) -> None:
        """Run the complete AI analysis workflow."""
        try:
            self.analysis_started.emit()

            # Initialize AI client
            self.step_started.emit("Initialize AI Client", "Setting up AI connection...")
            self._initialize_ai_client()
            self.step_completed.emit("Initialize AI Client", True, "AI client ready")
            self.progress_updated.emit(20)

            if self.should_stop:
                return

            # Validate inputs
            self.step_started.emit("Validate Inputs", "Checking analysis inputs...")
            self._validate_inputs()
            self.step_completed.emit("Validate Inputs", True, "Inputs validated")
            self.progress_updated.emit(30)

            if self.should_stop:
                return

            # Process images (if any)
            image_analysis_results = []
            if self.request.images:
                self.step_started.emit("Process Images", f"Analyzing {len(self.request.images)} images...")
                image_analysis_results = self._process_images()
                self.step_completed.emit("Process Images", True, f"Processed {len(self.request.images)} images")
                self.progress_updated.emit(60)
            else:
                self.step_completed.emit("Process Images", True, "No images to process")
                self.progress_updated.emit(50)

            if self.should_stop:
                return

            # Perform text-based analysis
            self.step_started.emit("AI Analysis", "Running AI diagnostic analysis...")
            text_analysis_result = self._perform_text_analysis()
            self.step_completed.emit("AI Analysis", True, "AI analysis completed")
            self.progress_updated.emit(80)

            if self.should_stop:
                return

            # Synthesize results
            self.step_started.emit("Synthesize Results", "Combining analysis results...")
            final_result = self._synthesize_results(image_analysis_results, text_analysis_result)
            self.step_completed.emit("Synthesize Results", True, "Results synthesized")
            self.progress_updated.emit(100)

            # Emit final result
            self.analysis_completed.emit(final_result)

        except Exception as e:
            error_msg = f"Analysis failed: {str(e)}"
            self.analysis_error.emit(error_msg)
            self.step_completed.emit("Analysis", False, error_msg)

    def _initialize_ai_client(self) -> None:
        """Initialize AI client with configuration."""
        try:
            if not self.request.ai_config:
                raise ValueError("AI configuration is required")

            # Log the configuration being used for debugging
            self.logger.info(f"Initializing AI client with model: {self.request.ai_config.model}")
            self.logger.info(
                f"Request contains {len(self.request.images)} images and system specs: {bool(self.request.system_specs)}"
            )

            self.ai_client = AIClient(
                api_key=self.request.ai_config.api_key,
                model_name=self.request.ai_config.model,
                thinking_budget=self.request.ai_config.thinking_budget,
                enable_streaming=self.request.ai_config.enable_streaming,
            )

            # Test connection
            connection_result = self.ai_client.test_connection()
            if not connection_result.get("success", False):
                raise AIClientError(f"Connection test failed: {connection_result.get('error', 'Unknown error')}")

        except Exception as e:
            raise AIClientError(f"Failed to initialize AI client: {e}")

    def _validate_inputs(self) -> None:
        """Validate analysis inputs."""
        if not self.request.ai_config or not self.request.ai_config.api_key:
            raise ValueError("API key is required")

        if not self.request.error_description and not self.request.images:
            raise ValueError("Either error description or images are required")

        if not self.request.system_specs:
            raise ValueError("System specifications are required")

    def _process_images(self) -> List[Dict[str, Any]]:
        """Process images through AI analysis."""
        results = []

        for i, image_path in enumerate(self.request.images):
            if self.should_stop:
                break

            try:
                self.thinking_step.emit(
                    f"Analyzing image {i+1}/{len(self.request.images)}: {Path(image_path).name}", "analysis", 0.0
                )

                # Perform image analysis
                with PerformanceTimer(f"Image analysis {i+1}") as timer:
                    if not self.ai_client:
                        raise RuntimeError("AI client not initialized")
                    if not self.request.system_specs:
                        raise ValueError("System specs are required")

                    result = self.ai_client.analyze_error_screenshot(
                        image_path=image_path,
                        system_specs=self.request.system_specs,
                        error_type="system_diagnostic",
                        additional_context=self.request.error_description,
                    )

                # Update token usage
                if self.ai_client:
                    stats = self.ai_client.get_usage_stats()
                    self.token_usage_updated.emit(
                        stats.get("total_tokens_used", 0),
                        stats.get("thinking_tokens_used", 0),
                        stats.get("request_count", 0),
                    )

                if result.get("success", False):
                    analysis_data = result.get("analysis", {})
                    results.append({"image_path": image_path, "analysis": analysis_data, "duration": timer.duration})

                    # Add thinking steps
                    thinking_process = analysis_data.get("thinking_process", [])
                    if isinstance(thinking_process, list):
                        for insight in thinking_process:
                            if isinstance(insight, str) and insight.strip():
                                self.thinking_step.emit(insight.strip(), "hypothesis", 0.8)
                    elif isinstance(thinking_process, str) and thinking_process.strip():
                        self.thinking_step.emit(thinking_process.strip(), "hypothesis", 0.8)
                else:
                    results.append(
                        {
                            "image_path": image_path,
                            "error": result.get("error", "Analysis failed"),
                            "duration": timer.duration,
                        }
                    )

            except Exception as e:
                results.append({"image_path": image_path, "error": str(e), "duration": None})

        return results

    def _perform_text_analysis(self) -> Dict[str, Any]:
        """Perform text-based analysis using error description and system specs."""
        try:
            self.thinking_step.emit("Analyzing error description and system specifications", "analysis", 0.0)

            with PerformanceTimer("Text analysis") as timer:
                if not self.ai_client:
                    raise RuntimeError("AI client not initialized")
                if not self.request.system_specs:
                    raise ValueError("System specs are required")

                result = self.ai_client.analyze_text_only(
                    error_description=self.request.error_description,
                    system_specs=self.request.system_specs,
                    error_type="system_diagnostic",
                )

            # Update token usage
            if self.ai_client:
                stats = self.ai_client.get_usage_stats()
                self.token_usage_updated.emit(
                    stats.get("total_tokens_used", 0),
                    stats.get("thinking_tokens_used", 0),
                    stats.get("request_count", 0),
                )

            if result.get("success", False):
                analysis_data = result.get("analysis", {})

                # Add thinking steps from analysis
                thinking_process = analysis_data.get("thinking_process", [])
                if isinstance(thinking_process, list):
                    for insight in thinking_process:
                        if isinstance(insight, str) and insight.strip():
                            self.thinking_step.emit(insight.strip(), "conclusion", 0.9)
                elif isinstance(thinking_process, str) and thinking_process.strip():
                    self.thinking_step.emit(thinking_process.strip(), "conclusion", 0.9)

                return {"success": True, "analysis": analysis_data, "duration": timer.duration}
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Text analysis failed"),
                    "duration": timer.duration,
                }

        except Exception as e:
            return {"success": False, "error": str(e), "duration": None}

    def _synthesize_results(self, image_results: List[Dict[str, Any]], text_result: Dict[str, Any]) -> AnalysisResult:
        """Synthesize all analysis results into final result, prioritizing image analysis."""
        try:
            # Prioritize image analyses over text analysis
            successful_image_analyses = []
            successful_text_analysis = None

            # Collect successful image analyses
            for img_result in image_results:
                if "analysis" in img_result:
                    successful_image_analyses.append(img_result["analysis"])

            # Collect text analysis if successful
            if text_result.get("success", False):
                successful_text_analysis = text_result["analysis"]

            # Determine primary analysis source
            if successful_image_analyses:
                # Use image analysis as primary (more specific)
                primary_analysis = successful_image_analyses[0]  # Use first image analysis
                secondary_analyses = successful_image_analyses[1:]
                if successful_text_analysis:
                    secondary_analyses.append(successful_text_analysis)

                # Debug logging to verify image analysis prioritization
                image_summary = primary_analysis.get("problem_summary", "No summary")[:100]
                self.step_started.emit("Synthesis", f"Using image analysis as primary source: {image_summary}...")

            elif successful_text_analysis:
                # Use text analysis as fallback
                primary_analysis = successful_text_analysis
                secondary_analyses = []

                self.step_started.emit("Synthesis", "Using text analysis as primary source...")

            else:
                return AnalysisResult(success=False, error_message="No successful analyses to synthesize")

            # Extract solutions from primary analysis
            solutions = primary_analysis.get("solutions", [])

            # Enhance solutions with insights from secondary analyses
            for secondary in secondary_analyses:
                secondary_solutions = secondary.get("solutions", [])
                # Add unique solutions from secondary analyses
                for sec_solution in secondary_solutions:
                    sec_title = sec_solution.get("title", "").lower()
                    # Only add if not already present
                    if not any(sec_title in sol.get("title", "").lower() for sol in solutions):
                        solutions.append(sec_solution)

            # Extract thinking process from primary analysis
            thinking_process = primary_analysis.get("thinking_process", [])

            # Add insights from secondary analyses
            for secondary in secondary_analyses:
                secondary_thinking = secondary.get("thinking_process", [])
                if isinstance(secondary_thinking, list):
                    thinking_process.extend(secondary_thinking)
                elif isinstance(secondary_thinking, str):
                    thinking_process.append(secondary_thinking)

            # Create final result based on primary analysis
            result = AnalysisResult(
                success=True,
                confidence_score=primary_analysis.get("confidence_score", 0.0),
                problem_summary=primary_analysis.get("problem_summary", "Analysis completed"),
                solutions=solutions[:10],  # Limit to top 10 solutions
                risk_assessment=primary_analysis.get("risk_assessment", "Low risk"),
                thinking_process=thinking_process,
                metadata={
                    "total_analyses": len(successful_image_analyses) + (1 if successful_text_analysis else 0),
                    "image_analyses": len(successful_image_analyses),
                    "text_analysis": successful_text_analysis is not None,
                    "primary_source": "image" if successful_image_analyses else "text",
                    "processing_time": datetime.now().isoformat(),
                    "model_used": self.request.ai_config.model if self.request.ai_config else "unknown",
                    "thinking_budget": self.request.ai_config.thinking_budget if self.request.ai_config else "unknown",
                    "debug_primary_summary": primary_analysis.get("problem_summary", "No summary")[:200],
                },
            )

            # Emit synthesis debug info
            self.step_started.emit("Synthesis", f"Final result summary: {result.problem_summary[:100]}...")

            return result

        except Exception as e:
            return AnalysisResult(success=False, error_message=f"Failed to synthesize results: {e}")

    def stop(self) -> None:
        """Stop the analysis workflow."""
        self.should_stop = True


class AIWorkflowIntegration(QWidget):
    """Main AI workflow integration widget."""

    analysis_completed = pyqtSignal(object)  # AnalysisResult
    analysis_error = pyqtSignal(str)  # error message

    def __init__(self, parent=None):
        super().__init__(parent)

        self.analysis_worker = None
        self.current_request = None
        self.system_specs = {}

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Setup the workflow integration UI."""
        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("🤖 AI Analysis Workflow")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # Main content tabs
        self.tab_widget = QTabWidget()

        # Input tab
        input_tab = self._create_input_tab()
        self.tab_widget.addTab(input_tab, "📝 Input")

        # Configuration tab
        config_tab = self._create_config_tab()
        self.tab_widget.addTab(config_tab, "⚙️ Config")

        # Progress tab
        progress_tab = self._create_progress_tab()
        self.tab_widget.addTab(progress_tab, "📊 Progress")

        layout.addWidget(self.tab_widget)

        # Control buttons
        button_layout = QHBoxLayout()

        self.collect_specs_btn = QPushButton("🔍 Collect System Specs")
        self.collect_specs_btn.clicked.connect(self._collect_system_specs)
        button_layout.addWidget(self.collect_specs_btn)

        button_layout.addStretch()

        self.analyze_btn = QPushButton("🚀 Start AI Analysis")
        self.analyze_btn.setMinimumHeight(35)
        self.analyze_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """
        )
        self.analyze_btn.clicked.connect(self._start_analysis)
        self.analyze_btn.setEnabled(False)
        button_layout.addWidget(self.analyze_btn)

        self.stop_btn = QPushButton("⏹️ Stop Analysis")
        self.stop_btn.clicked.connect(self._stop_analysis)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setVisible(False)
        button_layout.addWidget(self.stop_btn)

        layout.addLayout(button_layout)

        # Status bar
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_layout = QHBoxLayout(status_frame)

        self.status_label = QLabel("Ready - Configure settings and collect system specs to begin")
        status_layout.addWidget(self.status_label)

        layout.addWidget(status_frame)

    def _create_input_tab(self) -> QWidget:
        """Create input configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Images section
        images_group = QGroupBox("📸 Error Screenshots")
        images_layout = QVBoxLayout(images_group)

        self.image_drop_area = MultiImageDropArea()
        self.image_drop_area.images_added.connect(self._on_images_changed)
        self.image_drop_area.images_removed.connect(self._on_images_changed)
        images_layout.addWidget(self.image_drop_area)

        layout.addWidget(images_group)

        # Error description section
        description_group = QGroupBox("📝 Error Description")
        description_layout = QVBoxLayout(description_group)

        self.rich_text_editor = RichTextEditor()
        self.rich_text_editor.text_changed.connect(self._validate_inputs)
        description_layout.addWidget(self.rich_text_editor)

        layout.addWidget(description_group)

        return tab

    def _create_config_tab(self) -> QWidget:
        """Create AI configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.ai_config_panel = AIConfigurationPanel()
        self.ai_config_panel.configuration_changed.connect(self._on_config_changed)
        layout.addWidget(self.ai_config_panel)

        return tab

    def _create_progress_tab(self) -> QWidget:
        """Create progress tracking tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.progress_tracker = ProgressTrackingSystem()
        layout.addWidget(self.progress_tracker)

        return tab

    def _setup_connections(self) -> None:
        """Setup signal connections."""
        pass

    def _collect_system_specs(self) -> None:
        """Collect system specifications."""
        self.collect_specs_btn.setEnabled(False)
        self.status_label.setText("Collecting system specifications...")

        # Use QTimer to run collection in next event loop iteration
        QTimer.singleShot(100, self._run_specs_collection)

    def _run_specs_collection(self) -> None:
        """Run specs collection."""
        try:
            collector = SystemSpecsCollector()

            with PerformanceTimer("System specs collection") as timer:
                self.system_specs = collector.collect_all_specs()

            self.status_label.setText(f"✅ System specs collected ({timer.duration:.1f}s)")
            self._validate_inputs()

        except Exception as e:
            self.status_label.setText(f"❌ Failed to collect specs: {e}")
            QMessageBox.critical(self, "Collection Error", f"Failed to collect system specs:\n\n{e}")
        finally:
            self.collect_specs_btn.setEnabled(True)

    def _on_images_changed(self, images: List[str]) -> None:
        """Handle image selection changes."""
        self._validate_inputs()

    def _on_config_changed(self, config) -> None:
        """Handle AI configuration changes."""
        self._validate_inputs()

    def _validate_inputs(self) -> None:
        """Validate all inputs and update analysis button state."""
        try:
            # Get current inputs
            images = self.image_drop_area.get_selected_images()
            error_text = self.rich_text_editor.get_plain_text().strip()
            config = self.ai_config_panel.get_configuration()

            # Check requirements
            has_content = len(images) > 0 or len(error_text) > 0
            has_specs = bool(self.system_specs)
            has_api_key = bool(config.api_key)

            # Enable analysis if all requirements met
            can_analyze = has_content and has_specs and has_api_key
            self.analyze_btn.setEnabled(can_analyze)

            # Update status
            if can_analyze:
                self.status_label.setText(
                    f"✅ Ready for analysis - {len(images)} images, {len(error_text)} chars, specs collected"
                )
            else:
                missing = []
                if not has_content:
                    missing.append("images or error description")
                if not has_specs:
                    missing.append("system specs")
                if not has_api_key:
                    missing.append("API key")

                self.status_label.setText(f"Missing: {', '.join(missing)}")

        except Exception as e:
            self.status_label.setText(f"Validation error: {e}")

    def _start_analysis(self) -> None:
        """Start AI analysis workflow."""
        try:
            # Create analysis request
            request = AnalysisRequest(
                images=self.image_drop_area.get_selected_images(),
                error_description=self.rich_text_editor.get_plain_text().strip(),
                system_specs=self.system_specs,
                ai_config=self.ai_config_panel.get_configuration(),
            )

            self.current_request = request

            # Setup UI for analysis
            self.analyze_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.stop_btn.setVisible(True)
            self.tab_widget.setCurrentIndex(2)  # Switch to progress tab

            # Start analysis workflow
            self.analysis_worker = AIAnalysisWorker(request)
            self._connect_worker_signals()

            # Initialize progress tracking
            analysis_steps = [
                "Initialize AI Client",
                "Validate Inputs",
                "Process Images",
                "AI Analysis",
                "Synthesize Results",
            ]

            self.progress_tracker.start_analysis(analysis_steps)
            self.analysis_worker.start()

            self.status_label.setText("🚀 Analysis started...")

        except Exception as e:
            self._handle_analysis_error(f"Failed to start analysis: {e}")

    def _connect_worker_signals(self) -> None:
        """Connect analysis worker signals."""
        if not self.analysis_worker:
            return

        self.analysis_worker.step_started.connect(self.progress_tracker.update_step)
        self.analysis_worker.step_completed.connect(
            lambda name, success, details: self.progress_tracker.update_step(
                name, "complete" if success else "error", details
            )
        )
        self.analysis_worker.thinking_step.connect(self.progress_tracker.add_thinking_step)
        self.analysis_worker.token_usage_updated.connect(self.progress_tracker.update_token_usage)
        self.analysis_worker.analysis_completed.connect(self._on_analysis_completed)
        self.analysis_worker.analysis_error.connect(self._handle_analysis_error)

    def _stop_analysis(self) -> None:
        """Stop current analysis."""
        if self.analysis_worker:
            self.analysis_worker.stop()
            self.analysis_worker.wait(5000)  # Wait up to 5 seconds

        self._reset_analysis_ui()
        self.status_label.setText("Analysis stopped by user")

    def _on_analysis_completed(self, result: AnalysisResult) -> None:
        """Handle analysis completion."""
        self._reset_analysis_ui()

        if result.success:
            self.status_label.setText(f"✅ Analysis completed - Confidence: {result.confidence_score:.1%}")
            self.analysis_completed.emit(result)
        else:
            self.status_label.setText(f"❌ Analysis failed: {result.error_message}")
            self.analysis_error.emit(result.error_message)

    def _handle_analysis_error(self, error_msg: str) -> None:
        """Handle analysis errors."""
        self._reset_analysis_ui()
        self.status_label.setText(f"❌ Analysis error: {error_msg}")
        self.analysis_error.emit(error_msg)

        QMessageBox.critical(
            self,
            "Analysis Error",
            f"AI analysis failed:\n\n{error_msg}\n\nPlease check your configuration and try again.",
        )

    def _reset_analysis_ui(self) -> None:
        """Reset analysis UI to ready state."""
        self.analyze_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setVisible(False)
        self._validate_inputs()

    def get_current_analysis_request(self) -> Optional[AnalysisRequest]:
        """Get current analysis request."""
        return self.current_request

    def set_system_specs(self, specs: Dict[str, Any]) -> None:
        """Set system specifications externally."""
        self.system_specs = specs
        self._validate_inputs()
