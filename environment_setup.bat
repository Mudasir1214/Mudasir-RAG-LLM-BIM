@echo off
REM ============================================================
REM BIM Safety Analysis System - Setup and Launch Script
REM ============================================================
REM This script installs all dependencies and launches the GUI
REM Run this file by double-clicking or from command prompt
REM ============================================================

title BIM Safety Analysis System - Setup
color 0A

echo.
echo ============================================================
echo    BIM SAFETY ANALYSIS SYSTEM - SETUP
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.9+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.

REM Check pip
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip is not available!
    echo Please reinstall Python with pip included.
    pause
    exit /b 1
)

echo [OK] pip found:
pip --version
echo.

REM Create virtual environment (optional but recommended)
echo ============================================================
echo Do you want to create a virtual environment? (Recommended)
echo This keeps dependencies isolated from your system Python.
echo ============================================================
echo.
set /p VENV_CHOICE="Create virtual environment? (Y/N): "

if /i "%VENV_CHOICE%"=="Y" (
    echo.
    echo Creating virtual environment...
    python -m venv venv

    if exist "venv\Scripts\activate.bat" (
        echo [OK] Virtual environment created.
        echo Activating virtual environment...
        call venv\Scripts\activate.bat
        echo [OK] Virtual environment activated.
    ) else (
        echo [WARNING] Could not create virtual environment. Continuing with system Python.
    )
    echo.
)

REM Upgrade pip
echo ============================================================
echo Upgrading pip...
echo ============================================================
python -m pip install --upgrade pip
echo.

REM Install dependencies
echo ============================================================
echo Installing dependencies from requirements.txt...
echo This may take several minutes on first run.
echo ============================================================
echo.

pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Some packages may have failed to install.
    echo Trying to install core packages individually...
    echo.

    pip install ifcopenshell
    pip install numpy scipy
    pip install pandas matplotlib tqdm
    pip install openai requests
    pip install sentence-transformers
    pip install torch
)

echo.
echo ============================================================
echo [OK] Dependencies installed successfully!
echo ============================================================
echo.

REM Launch the GUI
echo ============================================================
echo Launching BIM Safety Analysis GUI...
echo ============================================================
echo.

cd GUI_Application
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to launch GUI. Check the error messages above.
    echo.
    echo Common fixes:
    echo   1. Ensure all dependencies installed correctly
    echo   2. Check that Python version is 3.9 or higher
    echo   3. Try running: pip install tk (if tkinter is missing)
    echo.
)

pause
