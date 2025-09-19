#!/usr/bin/env python3
"""
Win Sayver - Main GUI Application
=================================

Professional PyQt6 desktop interface for AI-powered Windows troubleshooting.
Supports multiple image analysis, error description input, and real-time 
AI analysis with Gemini 2.5 Pro thinking capabilities.
"""

import sys
import os
import logging
from pathlib import Path
from typing import Optional

# Check for PyQt6 availability
try:
    from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel
    from PyQt6.QtCore import Qt
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    print("❌ PyQt6 not available. Install with: pip install PyQt6")


class WinSayverGUI(QMainWindow):  # type: ignore
    """
    Main GUI application for Win Sayver.
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Win Sayver v3.1.0 - AI-Powered Windows Troubleshooting")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        central_widget = QLabel("Win Sayver GUI - Ready for AI-powered troubleshooting!")  # type: ignore
        central_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore
        self.setCentralWidget(central_widget)


def main():
    """
    Main entry point for Win Sayver application.
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    if not PYQT6_AVAILABLE:
        logger.error("PyQt6 is required but not available")
        sys.exit(1)
    
    # Create QApplication
    app = QApplication(sys.argv)
    
    # Create main window
    window = WinSayverGUI()
    window.show()
    
    logger.info("Win Sayver GUI started successfully")
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()