#!/usr/bin/env python3
"""
Image Widgets for Win Sayver GUI
================================

Professional image handling widgets with drag & drop support,
thumbnail generation, and comprehensive validation.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal
    from PyQt6.QtGui import (
        QDragEnterEvent,
        QDragLeaveEvent,
        QDragMoveEvent,
        QDropEvent,
        QPixmap,
    )
    from PyQt6.QtWidgets import (
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

try:
    from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal
    from PyQt6.QtGui import (
        QDragEnterEvent,
        QDragLeaveEvent,
        QDragMoveEvent,
        QDropEvent,
        QPixmap,
    )
    from PyQt6.QtWidgets import (
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


# Simple placeholder for image validation
class ImageMetadata:
    def __init__(
        self,
        file_path: str,
        file_name: str,
        file_size: int,
        file_modified,
        is_valid: bool = True,
        is_secure: bool = True,
        is_screenshot: bool = False,
    ):
        self.file_path = file_path
        self.file_name = file_name
        self.file_size = file_size
        self.file_modified = file_modified
        self.is_valid = is_valid
        self.is_secure = is_secure
        self.is_screenshot = is_screenshot


class ImageThumbnail(QFrame):  # type: ignore
    """Widget for displaying image thumbnail with controls."""

    remove_requested = pyqtSignal(str)  # type: ignore # file_path

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)

        self.file_path = file_path
        self.file_name = Path(file_path).name

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup thumbnail UI."""
        self.setFrameStyle(QFrame.Shape.StyledPanel)  # type: ignore
        self.setFixedSize(180, 200)

        # Main vertical layout
        layout = QVBoxLayout(self)  # type: ignore
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        # Image container with remove button overlay
        image_container = QWidget()  # type: ignore
        image_container.setFixedSize(164, 140)

        # Image display
        self.image_label = QLabel(image_container)  # type: ignore
        self.image_label.setGeometry(0, 0, 164, 120)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        self.image_label.setStyleSheet(
            """
            QLabel {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #f9f9f9;
            }
        """
        )
        self.image_label.setText("📷\nLoading...")

        # Remove button positioned at top-right corner
        self.remove_btn = QPushButton("✕", image_container)  # type: ignore
        self.remove_btn.setGeometry(140, 5, 20, 20)  # Top-right corner
        self.remove_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(255, 68, 68, 200);
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(255, 102, 102, 255);
            }
        """
        )
        # Fix: Create proper slot method to ensure None return type
        def on_remove_clicked() -> None:
            self.remove_requested.emit(self.file_path)
        
        self.remove_btn.clicked.connect(on_remove_clicked)

        layout.addWidget(image_container)

        # File name
        display_name = self.file_name
        if len(display_name) > 20:
            display_name = display_name[:17] + "..."

        self.name_label = QLabel(display_name)  # type: ignore
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("font-size: 11px; color: #555;")
        layout.addWidget(self.name_label)

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        """Set thumbnail image."""
        if pixmap and not pixmap.isNull():
            # Scale image to fit in the label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                160,
                120,
                Qt.AspectRatioMode.KeepAspectRatio,  # type: ignore
                Qt.TransformationMode.SmoothTransformation,  # type: ignore
            )
            self.image_label.setPixmap(scaled_pixmap)

            # Update image label style to remove placeholder styling
            self.image_label.setStyleSheet(
                """
                QLabel {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    background-color: #ffffff;
                }
            """
            )
        else:
            self.set_error("Failed to load")

    def set_error(self, error_message: str) -> None:
        """Set error state."""
        self.image_label.clear()  # Clear any existing pixmap
        self.image_label.setText(f"❌\n{error_message}")
        self.image_label.setStyleSheet(
            """
            QLabel {
                border: 1px solid #ff4444;
                border-radius: 4px;
                background-color: #ffeeee;
                color: #ff4444;
                font-size: 12px;
            }
        """
        )


class MultiImageDropArea(QWidget):  # type: ignore
    """Professional multi-image drag & drop area with validation."""

    images_added = pyqtSignal(list)  # type: ignore # List of file paths
    images_removed = pyqtSignal(list)  # type: ignore # List of file paths
    selection_changed = pyqtSignal(int)  # type: ignore # Number of selected images

    def __init__(self, parent=None):
        super().__init__(parent)

        self.selected_images = []
        self.thumbnail_widgets = {}
        self.image_metadata = {}

        self._setup_ui()
        self._setup_drag_drop()

    def _setup_ui(self) -> None:
        """Setup the drop area UI."""
        main_layout = QVBoxLayout(self)  # type: ignore
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header with instructions and buttons
        header_layout = QHBoxLayout()  # type: ignore

        # Instructions label
        self.instructions_label = QLabel("📁 Drag & drop images here or click 'Select Images'")  # type: ignore
        self.instructions_label.setStyleSheet(
            """
            QLabel {
                color: #666666;
                font-size: 14px;
                padding: 20px;
                border: 2px dashed #cccccc;
                border-radius: 8px;
                background-color: #f9f9f9;
            }
        """
        )

        # Action buttons
        button_layout = QHBoxLayout()  # type: ignore

        self.select_btn = QPushButton("📁 Select Images")  # type: ignore
        self.select_btn.clicked.connect(self._select_images_dialog)

        self.clear_btn = QPushButton("🗑️ Clear All")  # type: ignore
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self._clear_all_images)

        button_layout.addWidget(self.select_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()

        header_layout.addWidget(self.instructions_label, 1)
        header_layout.addLayout(button_layout)

        main_layout.addLayout(header_layout)

        # Thumbnail gallery
        self.gallery_scroll = QScrollArea()  # type: ignore
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setMinimumHeight(200)

        self.gallery_widget = QWidget()  # type: ignore
        self.gallery_layout = QGridLayout(self.gallery_widget)  # type: ignore
        self.gallery_layout.setContentsMargins(10, 10, 10, 10)
        self.gallery_layout.setSpacing(15)

        self.gallery_scroll.setWidget(self.gallery_widget)
        main_layout.addWidget(self.gallery_scroll)

        self._update_display()

    def _setup_drag_drop(self) -> None:
        """Setup drag and drop functionality."""
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # type: ignore
        """Handle drag enter event."""
        if event.mimeData().hasUrls():  # type: ignore
            # Check if any URLs are image files
            image_files = self._filter_image_files([url.toLocalFile() for url in event.mimeData().urls()])  # type: ignore
            if image_files:
                event.acceptProposedAction()
                self._set_drag_style(True)
                return

        event.ignore()

    def dragMoveEvent(self, a0) -> None:  # type: ignore
        """Handle drag move event."""
        if a0.mimeData().hasUrls():  # type: ignore
            a0.acceptProposedAction()  # type: ignore
        else:
            a0.ignore()  # type: ignore

    def dragLeaveEvent(self, event) -> None:  # type: ignore
        """Handle drag leave event."""
        self._set_drag_style(False)
        event.accept()  # type: ignore

    def dropEvent(self, event) -> None:  # type: ignore
        """Handle drop event."""
        self._set_drag_style(False)

        if event.mimeData().hasUrls():  # type: ignore
            file_paths = [url.toLocalFile() for url in event.mimeData().urls()]  # type: ignore
            image_files = self._filter_image_files(file_paths)

            if image_files:
                self._add_images(image_files)
                event.acceptProposedAction()  # type: ignore
            else:
                QMessageBox.warning(  # type: ignore
                    self, "Invalid Files", "No valid image files found in the dropped items."
                )
        else:
            event.ignore()  # type: ignore

    def _set_drag_style(self, dragging: bool) -> None:
        """Update visual style during drag operation."""
        if dragging:
            self.instructions_label.setStyleSheet(
                """
                QLabel {
                    color: #2196F3;
                    font-size: 14px;
                    font-weight: 500;
                    padding: 20px;
                    border: 2px dashed #2196F3;
                    border-radius: 8px;
                    background-color: #e3f2fd;
                }
            """
            )
            self.instructions_label.setText("📁 Drop images here!")
        else:
            self.instructions_label.setStyleSheet(
                """
                QLabel {
                    color: #666666;
                    font-size: 14px;
                    padding: 20px;
                    border: 2px dashed #cccccc;
                    border-radius: 8px;
                    background-color: #f9f9f9;
                }
            """
            )
            if self.selected_images:
                self.instructions_label.setText(f"📁 {len(self.selected_images)} images selected")
            else:
                self.instructions_label.setText("📁 Drag & drop images here or click 'Select Images'")

    def _filter_image_files(self, file_paths: List[str]) -> List[str]:
        """Filter and validate image files."""
        valid_files = []
        valid_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

        for file_path in file_paths:
            try:
                path = Path(file_path)

                # Basic checks
                if not path.exists() or not path.is_file():
                    continue

                # Check extension
                if path.suffix.lower() not in valid_extensions:
                    continue

                # Check if already selected
                if file_path in self.selected_images:
                    continue

                # Check file size (max 20MB)
                file_size = path.stat().st_size
                if file_size > 20 * 1024 * 1024:
                    continue

                valid_files.append(file_path)

                # Create simple metadata
                from datetime import datetime

                self.image_metadata[file_path] = ImageMetadata(
                    file_path=file_path,
                    file_name=path.name,
                    file_size=file_size,
                    file_modified=datetime.fromtimestamp(path.stat().st_mtime),
                    is_valid=True,
                    is_secure=True,
                    is_screenshot=True,  # Assume screenshots for now
                )

            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue

        return valid_files

    def _select_images_dialog(self) -> None:
        """Open file dialog to select images."""
        file_dialog = QFileDialog()  # type: ignore
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)  # type: ignore
        file_dialog.setNameFilter("Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
        file_dialog.setWindowTitle("Select Error Screenshot Images")

        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            valid_files = self._filter_image_files(selected_files)

            if valid_files:
                self._add_images(valid_files)
            elif selected_files:
                QMessageBox.warning(  # type: ignore
                    self,
                    "Invalid Selection",
                    "Some files were not added because they are either:\\n"
                    "• Not supported image formats\\n"
                    "• Too large (max 20MB)\\n"
                    "• Already selected",
                )

    def _load_thumbnail(self, thumbnail: ImageThumbnail, file_path: str) -> None:
        """Load actual thumbnail from image file."""
        try:
            # Load image using QPixmap
            pixmap = QPixmap(file_path)  # type: ignore

            if pixmap.isNull():
                # If QPixmap fails, create error placeholder
                thumbnail.set_error("Invalid image")
            else:
                # Successfully loaded, set thumbnail
                thumbnail.set_thumbnail(pixmap)

        except Exception as e:
            print(f"Error loading thumbnail for {file_path}: {e}")
            thumbnail.set_error("Load failed")

    def _add_images(self, file_paths: List[str]) -> None:
        """Add images to the selection."""
        if not file_paths:
            return

        # Add to selected images list
        self.selected_images.extend(file_paths)

        # Create thumbnail widgets
        for file_path in file_paths:
            thumbnail = ImageThumbnail(file_path)
            thumbnail.remove_requested.connect(self._remove_image)
            self.thumbnail_widgets[file_path] = thumbnail

            # Load actual thumbnail from image file
            self._load_thumbnail(thumbnail, file_path)

        # Update UI
        self._update_display()

        # Emit signals
        self.images_added.emit(file_paths)
        self.selection_changed.emit(len(self.selected_images))

    def _remove_image(self, file_path: str) -> None:
        """Remove image from selection."""
        if file_path not in self.selected_images:
            return

        # Remove from lists
        self.selected_images.remove(file_path)

        # Remove thumbnail widget
        if file_path in self.thumbnail_widgets:
            self.thumbnail_widgets[file_path].deleteLater()
            del self.thumbnail_widgets[file_path]

        # Remove metadata
        if file_path in self.image_metadata:
            del self.image_metadata[file_path]

        # Update UI
        self._update_display()

        # Emit signals
        self.images_removed.emit([file_path])
        self.selection_changed.emit(len(self.selected_images))

    def _clear_all_images(self) -> None:
        """Clear all selected images."""
        if not self.selected_images:
            return

        removed_images = self.selected_images.copy()
        self.selected_images.clear()

        # Remove all thumbnail widgets
        for thumbnail in self.thumbnail_widgets.values():
            thumbnail.deleteLater()
        self.thumbnail_widgets.clear()
        self.image_metadata.clear()

        # Update UI
        self._update_display()

        # Emit signals
        self.images_removed.emit(removed_images)
        self.selection_changed.emit(0)

    def _update_display(self) -> None:
        """Update the gallery display."""
        # Update instructions
        if self.selected_images:
            self.instructions_label.setText(f"📁 {len(self.selected_images)} images selected")
            self.clear_btn.setEnabled(True)
        else:
            self.instructions_label.setText("📁 Drag & drop images here or click 'Select Images'")
            self.clear_btn.setEnabled(False)

        # Update gallery layout
        self._update_gallery_layout()

    def _update_gallery_layout(self) -> None:
        """Update the thumbnail gallery layout."""
        # Clear existing layout with proper type handling
        for i in reversed(range(self.gallery_layout.count())):
            child = self.gallery_layout.itemAt(i).widget()  # type: ignore
            if child:
                child.setParent(None)  # type: ignore[arg-type]

        # Add thumbnails in grid layout
        if self.thumbnail_widgets:
            row, col = 0, 0
            max_cols = 4  # Maximum thumbnails per row

            for thumbnail in self.thumbnail_widgets.values():
                self.gallery_layout.addWidget(thumbnail, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

    def get_selected_images(self) -> List[str]:
        """Get list of selected image file paths."""
        return self.selected_images.copy()

    def clear_selection(self) -> None:
        """Clear all selected images."""
        self._clear_all_images()

    def add_images(self, file_paths: List[str]) -> None:
        """Add images programmatically."""
        valid_files = self._filter_image_files(file_paths)
        if valid_files:
            self._add_images(valid_files)

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation results for all images."""
        total_images = len(self.selected_images)
        if total_images == 0:
            return {"total_images": 0}

        valid_images = sum(
            1 for path in self.selected_images if self.image_metadata.get(path, {}).get("is_valid", False)
        )
        secure_images = sum(
            1 for path in self.selected_images if self.image_metadata.get(path, {}).get("is_secure", False)
        )
        screenshot_likely = sum(
            1 for path in self.selected_images if self.image_metadata.get(path, {}).get("is_screenshot", False)
        )

        total_size = sum(
            self.image_metadata.get(path, ImageMetadata("", "", 0, None)).file_size for path in self.selected_images
        )

        return {
            "total_images": total_images,
            "valid_images": valid_images,
            "secure_images": secure_images,
            "screenshot_likely": screenshot_likely,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
        }
