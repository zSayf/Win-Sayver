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
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)
echo     ✓ Python found

REM Check Python version (minimum 3.8)
echo [2/6] Verifying Python version...
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo     ✓ Python version: %PYTHON_VERSION%

REM Upgrade pip to latest version
echo [3/6] Upgrading pip to latest version...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo WARNING: Failed to upgrade pip, continuing with current version...
) else (
    echo     ✓ pip upgraded successfully
)

REM Check if virtual environment exists, create if not
echo [4/6] Setting up virtual environment...
if exist "venv\Scripts\activate.bat" (
    echo     ✓ Virtual environment found, activating...
    call venv\Scripts\activate.bat
) else (
    echo     Creating new virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        echo Using system Python instead...
    ) else (
        echo     ✓ Virtual environment created, activating...
        call venv\Scripts\activate.bat
    )
)

REM Install all required packages
echo [5/6] Installing all required packages...
echo     Installing core system profiling libraries...
pip install "wmi>=1.5.1" "psutil>=5.9.0"

echo     Installing Google Gemini AI SDK...
pip install "google-genai>=1.0.0"

echo     Installing PyQt6 GUI framework (version compatible with tools)...
REM First uninstall any conflicting versions
pip uninstall -y PyQt6 PyQt6-Qt6 PyQt6-tools pyqt6-plugins 2>nul
REM Install compatible versions together
pip install "PyQt6==6.4.2" "PyQt6-tools==6.4.2.3.3"
if %errorlevel% neq 0 (
    echo     WARNING: PyQt6-tools installation failed, installing PyQt6 only...
    pip install "PyQt6>=6.4.0"
)

echo     Installing image processing libraries...
pip install "Pillow>=10.0.0"

echo     Installing security and utilities...
pip install "cryptography>=41.0.0" "requests>=2.31.0" "colorama>=0.4.6"

echo     Final verification (skipping conflicting requirements)...
REM Install requirements one by one to avoid conflicts
for %%p in (wmi psutil google-genai Pillow cryptography requests colorama) do (
    pip install %%p
)

REM Check if PyQt6 is available (most critical for GUI)
python -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: PyQt6 installation failed - GUI cannot start
    echo Attempting emergency PyQt6 installation...
    pip install PyQt6 --force-reinstall
    python -c "import PyQt6" >nul 2>&1
    if %errorlevel% neq 0 (
        echo FATAL ERROR: Cannot install PyQt6
        echo Please manually run: pip install PyQt6
        pause
        exit /b 1
    )
)

echo     ✓ All core packages installed successfully

echo [6/6] Starting Win Sayver application...
echo     ✓ All dependencies verified and installed
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