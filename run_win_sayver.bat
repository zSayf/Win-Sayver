@echo off
title Win Sayver - AI-Powered Windows Troubleshooting Assistant

echo.
echo ============================================
echo    Win Sayver v3.0 - Startup Script
echo    AI-Powered Windows Troubleshooting
echo ============================================
echo.

REM Change to the project directory
cd /d "%~dp0win_sayver_poc"

REM Check if Python is installed
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)
echo     ✓ Python found

REM Check if virtual environment exists, create if not
echo [2/4] Setting up virtual environment...
if exist "venv\Scripts\activate.bat" (
    echo     ✓ Virtual environment found, activating...
    call venv\Scripts\activate.bat >nul
) else (
    echo     Creating new virtual environment...
    python -m venv venv >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        echo Using system Python instead...
    ) else (
        echo     ✓ Virtual environment created, activating...
        call venv\Scripts\activate.bat >nul
    )
)

REM Install/upgrade required packages
echo [3/4] Installing required packages...
pip install "PyQt6>=6.4.0" "wmi>=1.5.1" "psutil>=5.9.0" "google-genai>=1.0.0" "Pillow>=10.0.0" "cryptography>=41.0.0" "requests>=2.31.0" "colorama>=0.4.6" --upgrade >nul 2>&1

echo [4/4] Starting Win Sayver application...
echo.

REM Run the main application
python main_gui.py

REM Check if application exited with error
if %errorlevel% neq 0 (
    echo.
    echo Application exited with error code: %errorlevel%
    echo Check the logs for more details.
) else (
    echo.
    echo Application closed successfully.
)

echo.
pause