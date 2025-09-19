#!/usr/bin/env python3
"""
Image Validation and Processing Pipeline for Win Sayver
======================================================

Comprehensive image validation, format checking, and processing system
for error screenshot analysis. Provides detailed validation, metadata
extraction, security checking, and format conversion capabilities.
"""

import hashlib
import io
import mimetypes
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from PIL import ExifTags
    from PIL import Image as PILImage
    from PIL import ImageStat
    from PIL.Image import Resampling

    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    # Create type stubs for when PIL is not available
    PILImage = None  # type: ignore
    ImageStat = None  # type: ignore
    ExifTags = None  # type: ignore
    Resampling = None  # type: ignore

try:
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QPixmap

    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    QSize = None
    QPixmap = None

from utils import PerformanceTimer, WinSayverError, safe_execute


class ImageValidationError(WinSayverError):
    """Raised when image validation fails."""

    pass


class ImageProcessingError(WinSayverError):
    """Raised when image processing fails."""

    pass


class SecurityValidationError(ImageValidationError):
    """Raised when image fails security validation."""

    pass


class ValidationLevel(Enum):
    """Image validation levels."""

    BASIC = "basic"  # File existence, extension, size
    STANDARD = "standard"  # + Format validation, basic metadata
    COMPREHENSIVE = "comprehensive"  # + Security checks, detailed analysis
    FORENSIC = "forensic"  # + Advanced security, hash validation


@dataclass
class ImageMetadata:
    """Container for comprehensive image metadata."""

    # File information
    file_path: str
    file_name: str
    file_size: int
    file_modified: datetime
    file_hash_md5: Optional[str] = None
    file_hash_sha256: Optional[str] = None

    # Format information
    format_name: str = "Unknown"
    mime_type: str = "Unknown"
    is_valid: bool = False

    # Image properties
    width: Optional[int] = None
    height: Optional[int] = None
    pixel_count: Optional[int] = None
    color_mode: Optional[str] = None
    bit_depth: Optional[int] = None
    has_transparency: Optional[bool] = None

    # Quality metrics
    compression_ratio: Optional[float] = None
    estimated_quality: Optional[int] = None  # 0-100 for JPEG
    is_progressive: Optional[bool] = None

    # EXIF data
    has_exif: bool = False
    exif_data: Optional[Dict[str, Any]] = None
    camera_info: Optional[Dict[str, str]] = None

    # Analysis results
    is_screenshot: Optional[bool] = None
    confidence_screenshot: Optional[float] = None
    potential_error_indicators: Optional[List[str]] = None

    # Security validation
    is_secure: bool = False
    security_warnings: Optional[List[str]] = None

    # Processing metadata
    validation_level: ValidationLevel = ValidationLevel.BASIC
    processing_time: Optional[float] = None

    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.potential_error_indicators is None:
            self.potential_error_indicators = []
        if self.security_warnings is None:
            self.security_warnings = []


class ImageValidator:
    """
    Comprehensive image validation and processing system.

    Provides multi-level validation from basic file checks to
    comprehensive security and content analysis.
    """

    # Supported image formats with their characteristics
    SUPPORTED_FORMATS = {
        "png": {
            "extensions": [".png"],
            "mime_types": ["image/png"],
            "supports_transparency": True,
            "supports_animation": False,
            "max_size_recommended": 50 * 1024 * 1024,  # 50MB
            "security_risk": "low",
        },
        "jpeg": {
            "extensions": [".jpg", ".jpeg", ".jpe"],
            "mime_types": ["image/jpeg"],
            "supports_transparency": False,
            "supports_animation": False,
            "max_size_recommended": 20 * 1024 * 1024,  # 20MB
            "security_risk": "low",
        },
        "gif": {
            "extensions": [".gif"],
            "mime_types": ["image/gif"],
            "supports_transparency": True,
            "supports_animation": True,
            "max_size_recommended": 10 * 1024 * 1024,  # 10MB
            "security_risk": "medium",
        },
        "bmp": {
            "extensions": [".bmp", ".dib"],
            "mime_types": ["image/bmp", "image/x-ms-bmp"],
            "supports_transparency": False,
            "supports_animation": False,
            "max_size_recommended": 100 * 1024 * 1024,  # 100MB
            "security_risk": "low",
        },
        "webp": {
            "extensions": [".webp"],
            "mime_types": ["image/webp"],
            "supports_transparency": True,
            "supports_animation": True,
            "max_size_recommended": 30 * 1024 * 1024,  # 30MB
            "security_risk": "low",
        },
        "tiff": {
            "extensions": [".tiff", ".tif"],
            "mime_types": ["image/tiff"],
            "supports_transparency": True,
            "supports_animation": False,
            "max_size_recommended": 200 * 1024 * 1024,  # 200MB
            "security_risk": "medium",
        },
    }

    # Maximum dimensions for different use cases
    MAX_DIMENSIONS = {
        "thumbnail": (300, 300),
        "preview": (1920, 1080),
        "analysis": (4096, 4096),
        "absolute_max": (32767, 32767),  # PIL limit
    }

    def __init__(
        self, max_file_size: int = 50 * 1024 * 1024, validation_level: ValidationLevel = ValidationLevel.STANDARD
    ):
        """
        Initialize image validator.

        Args:
            max_file_size: Maximum allowed file size in bytes
            validation_level: Default validation level to use
        """
        self.max_file_size = max_file_size
        self.default_validation_level = validation_level
        self._format_registry = self._build_format_registry()

    def _build_format_registry(self) -> Dict[str, str]:
        """Build registry mapping extensions to format names."""
        registry = {}
        for format_name, info in self.SUPPORTED_FORMATS.items():
            for ext in info["extensions"]:
                registry[ext.lower()] = format_name
        return registry

    def validate_image(
        self, file_path: Union[str, Path], validation_level: Optional[ValidationLevel] = None
    ) -> ImageMetadata:
        """
        Validate image file with comprehensive analysis.

        Args:
            file_path: Path to image file
            validation_level: Validation level to use (defaults to instance level)

        Returns:
            ImageMetadata with validation results

        Raises:
            ImageValidationError: If validation fails
        """
        level = validation_level or self.default_validation_level
        path = Path(file_path)

        with PerformanceTimer(f"Image validation ({level.value})") as timer:
            try:
                # Initialize metadata
                metadata = ImageMetadata(
                    file_path=str(path.absolute()),
                    file_name=path.name,
                    file_size=0,
                    file_modified=datetime.now(),
                    validation_level=level,
                )

                # Perform validation based on level
                if level in [
                    ValidationLevel.BASIC,
                    ValidationLevel.STANDARD,
                    ValidationLevel.COMPREHENSIVE,
                    ValidationLevel.FORENSIC,
                ]:
                    self._validate_file_basics(path, metadata)

                if level in [ValidationLevel.STANDARD, ValidationLevel.COMPREHENSIVE, ValidationLevel.FORENSIC]:
                    self._validate_format_and_structure(path, metadata)
                    self._extract_image_properties(path, metadata)

                if level in [ValidationLevel.COMPREHENSIVE, ValidationLevel.FORENSIC]:
                    self._perform_security_validation(path, metadata)
                    self._analyze_content_characteristics(path, metadata)

                if level == ValidationLevel.FORENSIC:
                    self._perform_forensic_analysis(path, metadata)

                # Set processing time
                metadata.processing_time = timer.duration

                # Determine overall validation status
                self._determine_validation_status(metadata)

                return metadata

            except Exception as e:
                raise ImageValidationError(f"Image validation failed for {path}: {e}")

    def _validate_file_basics(self, path: Path, metadata: ImageMetadata) -> None:
        """Perform basic file validation."""
        # Check file existence
        if not path.exists():
            raise ImageValidationError(f"File does not exist: {path}")

        if not path.is_file():
            raise ImageValidationError(f"Path is not a file: {path}")

        # Get file stats
        try:
            stat = path.stat()
            metadata.file_size = stat.st_size
            metadata.file_modified = datetime.fromtimestamp(stat.st_mtime)
        except Exception as e:
            raise ImageValidationError(f"Cannot access file stats: {e}")

        # Check file size
        if metadata.file_size == 0:
            raise ImageValidationError("File is empty")

        if metadata.file_size > self.max_file_size:
            raise ImageValidationError(
                f"File too large: {metadata.file_size} bytes " f"(max: {self.max_file_size} bytes)"
            )

        # Check extension
        extension = path.suffix.lower()
        if extension not in self._format_registry:
            raise ImageValidationError(f"Unsupported file extension: {extension}")

        # Set expected format based on extension
        metadata.format_name = self._format_registry[extension]

        # Check MIME type
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type:
            metadata.mime_type = mime_type

    def _validate_format_and_structure(self, path: Path, metadata: ImageMetadata) -> None:
        """Validate image format and internal structure."""
        if not PILLOW_AVAILABLE or not PILImage:
            if metadata.security_warnings is None:
                metadata.security_warnings = []
            metadata.security_warnings.append("Pillow not available for format validation")
            return

        try:
            with PILImage.open(path) as img:
                # Verify format matches extension expectation
                detected_format = img.format.lower() if img.format else "unknown"

                # Update metadata with detected format
                metadata.format_name = detected_format

                # Basic format validation
                img.verify()  # This will raise an exception if the image is corrupt

                metadata.is_valid = True

        except Exception as e:
            raise ImageValidationError(f"Invalid image format or corrupted file: {e}")

    def _extract_image_properties(self, path: Path, metadata: ImageMetadata) -> None:
        """Extract comprehensive image properties."""
        if not PILLOW_AVAILABLE or not PILImage:
            return

        try:
            with PILImage.open(path) as img:
                # Basic properties
                metadata.width, metadata.height = img.size
                if metadata.width and metadata.height:
                    metadata.pixel_count = metadata.width * metadata.height
                metadata.color_mode = img.mode

                # Color depth calculation
                # Note: img.bits is not a standard PIL attribute, estimate based on mode
                # if hasattr(img, 'bits'):
                #     metadata.bit_depth = img.bits
                # else:
                # Estimate bit depth based on mode
                mode_bits = {
                    "1": 1,
                    "L": 8,
                    "P": 8,
                    "RGB": 24,
                    "RGBA": 32,
                    "CMYK": 32,
                    "YCbCr": 24,
                    "LAB": 24,
                    "HSV": 24,
                }
                metadata.bit_depth = mode_bits.get(img.mode, 8)

                # Transparency check
                metadata.has_transparency = (
                    img.mode in ("RGBA", "LA")
                    or "transparency" in img.info
                    or img.mode == "P"
                    and "transparency" in img.info
                )

                # Format-specific properties
                if img.format == "JPEG":
                    self._extract_jpeg_properties(img, metadata)
                elif img.format == "PNG":
                    self._extract_png_properties(img, metadata)
                elif img.format == "GIF":
                    self._extract_gif_properties(img, metadata)

                # EXIF data extraction
                self._extract_exif_data(img, metadata)

                # Compression ratio estimation
                if metadata.width and metadata.height and metadata.bit_depth:
                    uncompressed_size = metadata.width * metadata.height * (metadata.bit_depth / 8)
                    if uncompressed_size > 0:
                        metadata.compression_ratio = metadata.file_size / uncompressed_size

        except Exception as e:
            if metadata.security_warnings is None:
                metadata.security_warnings = []
            metadata.security_warnings.append(f"Property extraction failed: {e}")

    def _extract_jpeg_properties(self, img: Any, metadata: ImageMetadata) -> None:
        """Extract JPEG-specific properties."""
        # Progressive JPEG detection
        metadata.is_progressive = img.info.get("progressive", False)

        # Quality estimation (rough approximation)
        if hasattr(img, "quantization"):
            # Estimate quality based on quantization tables
            # This is a simplified estimation
            metadata.estimated_quality = 95  # Placeholder - would need complex analysis

    def _extract_png_properties(self, img: Any, metadata: ImageMetadata) -> None:
        """Extract PNG-specific properties."""
        # PNG-specific information is in img.info
        png_info = img.info

        if "gamma" in png_info:
            metadata.exif_data = metadata.exif_data or {}
            metadata.exif_data["gamma"] = png_info["gamma"]

    def _extract_gif_properties(self, img: Any, metadata: ImageMetadata) -> None:
        """Extract GIF-specific properties."""
        # Animation detection
        try:
            img.seek(1)  # Try to go to second frame
            # If we get here, it's animated
            metadata.exif_data = metadata.exif_data or {}
            metadata.exif_data["animated"] = True
        except EOFError:
            # Single frame GIF
            metadata.exif_data = metadata.exif_data or {}
            metadata.exif_data["animated"] = False
        finally:
            img.seek(0)  # Return to first frame

    def _extract_exif_data(self, img: Any, metadata: ImageMetadata) -> None:
        """Extract EXIF metadata from image."""
        if not hasattr(img, "_getexif") or not ExifTags:
            return

        try:
            exif = img._getexif()
            if exif is None:
                return

            metadata.has_exif = True
            metadata.exif_data = {}
            metadata.camera_info = {}

            for tag_id, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, f"Tag_{tag_id}")

                # Store all EXIF data
                try:
                    # Convert bytes to string if needed
                    if isinstance(value, bytes):
                        value = value.decode("utf-8", errors="ignore")
                    metadata.exif_data[tag_name] = str(value)
                except Exception:
                    metadata.exif_data[tag_name] = "<unparseable>"

                # Extract camera-specific information
                camera_tags = {
                    "Make": "camera_make",
                    "Model": "camera_model",
                    "Software": "software",
                    "DateTime": "date_taken",
                }

                if tag_name in camera_tags:
                    try:
                        if isinstance(value, bytes):
                            value = value.decode("utf-8", errors="ignore")
                        metadata.camera_info[camera_tags[tag_name]] = str(value)
                    except Exception:
                        pass

        except Exception as e:
            if metadata.security_warnings is None:
                metadata.security_warnings = []
            metadata.security_warnings.append(f"EXIF extraction failed: {e}")

    def _perform_security_validation(self, path: Path, metadata: ImageMetadata) -> None:
        """Perform security-focused validation."""
        security_checks = []

        # Check file size against format recommendations
        format_info = self.SUPPORTED_FORMATS.get(metadata.format_name.lower(), {})
        max_recommended = format_info.get("max_size_recommended", self.max_file_size)

        if metadata.file_size > max_recommended:
            security_checks.append(f"File size exceeds recommendation for {metadata.format_name}")

        # Check dimensions for reasonableness
        if metadata.width and metadata.height:
            if (
                metadata.width > self.MAX_DIMENSIONS["absolute_max"][0]
                or metadata.height > self.MAX_DIMENSIONS["absolute_max"][1]
            ):
                security_checks.append("Image dimensions exceed safe limits")

            # Check for extremely high pixel density (potential bomb)
            if metadata.pixel_count and metadata.pixel_count > 100_000_000:  # 100MP
                security_checks.append("Extremely high pixel count - potential decompression bomb")

        # Check for suspicious EXIF data
        if metadata.has_exif and metadata.exif_data:
            suspicious_tags = ["GPSInfo", "UserComment", "ImageDescription"]
            for tag in suspicious_tags:
                if tag in metadata.exif_data:
                    security_checks.append(f"Contains potentially sensitive EXIF tag: {tag}")

        # Format-specific security checks
        security_risk = format_info.get("security_risk", "unknown")
        if security_risk == "medium":
            security_checks.append(f"Format {metadata.format_name} has medium security risk")
        elif security_risk == "high":
            security_checks.append(f"Format {metadata.format_name} has high security risk")

        # Update metadata
        if metadata.security_warnings is None:
            metadata.security_warnings = []
        metadata.security_warnings.extend(security_checks)
        metadata.is_secure = len(security_checks) == 0

    def _analyze_content_characteristics(self, path: Path, metadata: ImageMetadata) -> None:
        """Analyze image content to determine characteristics."""
        if not PILLOW_AVAILABLE or not PILImage:
            return

        try:
            with PILImage.open(path) as img:
                # Screenshot detection heuristics
                screenshot_indicators = []
                confidence_factors = []

                # Check aspect ratio (common screen ratios)
                if metadata.width and metadata.height:
                    aspect_ratio = metadata.width / metadata.height
                    common_ratios = [16 / 9, 16 / 10, 4 / 3, 21 / 9, 3 / 2]

                    if any(abs(aspect_ratio - ratio) < 0.1 for ratio in common_ratios):
                        screenshot_indicators.append("Common screen aspect ratio")
                        confidence_factors.append(0.3)

                # Check for common screenshot dimensions
                common_resolutions = [
                    (1920, 1080),
                    (1366, 768),
                    (1440, 900),
                    (1280, 720),
                    (1680, 1050),
                    (1600, 900),
                    (2560, 1440),
                    (3840, 2160),
                ]

                if (metadata.width, metadata.height) in common_resolutions:
                    screenshot_indicators.append("Standard screen resolution")
                    confidence_factors.append(0.4)

                # Analyze color distribution for UI elements
                if img.mode in ("RGB", "RGBA"):
                    # Convert to RGB if needed
                    if img.mode == "RGBA":
                        background = PILImage.new("RGB", img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[3] if len(img.split()) == 4 else None)
                        img = background

                    # Statistical analysis
                    if ImageStat:
                        stat = ImageStat.Stat(img)
                    else:
                        stat = None

                    # Check for limited color palette (typical of UI screenshots)
                    if metadata.width and metadata.height:
                        palette_threshold = metadata.width * metadata.height * 0.1
                        if len(set(img.getdata())) < palette_threshold:
                            screenshot_indicators.append("Limited color palette")
                            confidence_factors.append(0.2)

                    # Check for high contrast (typical of text/UI)
                    if stat and hasattr(stat, "stddev"):
                        avg_stddev = sum(stat.stddev) / len(stat.stddev)
                        if avg_stddev > 50:  # High contrast
                            screenshot_indicators.append("High contrast content")
                            confidence_factors.append(0.1)

                # Error detection heuristics
                error_indicators = []

                # Check filename for error-related keywords
                filename_lower = path.name.lower()
                error_keywords = ["error", "crash", "exception", "fail", "bug", "issue", "problem", "bsod"]
                for keyword in error_keywords:
                    if keyword in filename_lower:
                        error_indicators.append(f"Error keyword in filename: {keyword}")

                # Check for Windows error dialog dimensions (rough estimates)
                if metadata.width and metadata.height:
                    if 300 <= metadata.width <= 600 and 150 <= metadata.height <= 400:
                        error_indicators.append("Dimensions typical of error dialog")

                # Update metadata
                metadata.potential_error_indicators = error_indicators
                metadata.is_screenshot = len(screenshot_indicators) > 0
                metadata.confidence_screenshot = sum(confidence_factors) if confidence_factors else 0.0

        except Exception as e:
            if metadata.security_warnings is None:
                metadata.security_warnings = []
            metadata.security_warnings.append(f"Content analysis failed: {e}")

    def _perform_forensic_analysis(self, path: Path, metadata: ImageMetadata) -> None:
        """Perform forensic-level analysis including hash calculation."""
        try:
            # Calculate file hashes
            with open(path, "rb") as f:
                content = f.read()

                metadata.file_hash_md5 = hashlib.md5(content).hexdigest()
                metadata.file_hash_sha256 = hashlib.sha256(content).hexdigest()

            # Additional forensic checks could be added here
            # - Steganography detection
            # - Metadata tampering detection
            # - File signature verification

        except Exception as e:
            if metadata.security_warnings is None:
                metadata.security_warnings = []
            metadata.security_warnings.append(f"Forensic analysis failed: {e}")

    def _determine_validation_status(self, metadata: ImageMetadata) -> None:
        """Determine overall validation status based on all checks."""
        # Image is valid if format validation passed and no critical security issues
        if metadata.security_warnings is None:
            metadata.security_warnings = []

        critical_warnings = [
            w
            for w in metadata.security_warnings
            if any(term in w.lower() for term in ["bomb", "exceeds safe limits", "high security risk"])
        ]

        if not metadata.is_valid:
            return  # Already marked invalid

        if critical_warnings:
            metadata.is_valid = False
            metadata.security_warnings.insert(0, "Critical security issues detected")

    def validate_multiple_images(
        self, file_paths: List[Union[str, Path]], validation_level: Optional[ValidationLevel] = None
    ) -> List[ImageMetadata]:
        """
        Validate multiple images efficiently.

        Args:
            file_paths: List of image file paths
            validation_level: Validation level to use

        Returns:
            List of ImageMetadata objects
        """
        results = []

        for file_path in file_paths:
            try:
                metadata = self.validate_image(file_path, validation_level)
                results.append(metadata)
            except ImageValidationError as e:
                # Create metadata with error information
                error_metadata = ImageMetadata(
                    file_path=str(Path(file_path).absolute()),
                    file_name=Path(file_path).name,
                    file_size=0,
                    file_modified=datetime.now(),
                    is_valid=False,
                    validation_level=validation_level or self.default_validation_level,
                    security_warnings=[str(e)],
                )
                results.append(error_metadata)

        return results

    def create_thumbnail(
        self, file_path: Union[str, Path], size: Tuple[int, int] = (150, 150), quality: int = 85
    ) -> Optional[bytes]:
        """
        Create thumbnail image data.

        Args:
            file_path: Path to source image
            size: Thumbnail size (width, height)
            quality: JPEG quality for thumbnail (1-100)

        Returns:
            Thumbnail image data as bytes or None if failed
        """
        if not PILLOW_AVAILABLE or not PILImage:
            return None

        try:
            with PILImage.open(file_path) as img:
                # Convert RGBA to RGB if needed (for JPEG compatibility)
                if img.mode in ("RGBA", "LA", "P"):
                    background = PILImage.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P" and "transparency" in img.info:
                        img = img.convert("RGBA")
                    if img.mode in ("RGBA", "LA"):
                        background.paste(img, mask=img.split()[-1] if len(img.split()) > 3 else None)
                        img = background

                # Create thumbnail
                if Resampling:
                    img.thumbnail(size, Resampling.LANCZOS)
                else:
                    img.thumbnail(size)

                # Save to bytes
                output = io.BytesIO()
                img.save(output, format="JPEG", quality=quality, optimize=True)
                return output.getvalue()

        except Exception:
            return None

    def get_supported_formats(self) -> Dict[str, Dict[str, Any]]:
        """Get information about supported image formats."""
        return self.SUPPORTED_FORMATS.copy()

    def get_format_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        extensions = []
        for format_info in self.SUPPORTED_FORMATS.values():
            extensions.extend(format_info["extensions"])
        return sorted(extensions)
