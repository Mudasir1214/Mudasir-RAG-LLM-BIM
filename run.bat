@echo off
REM ============================================================
REM BIM Safety Analysis System - Quick Launch
REM ============================================================
REM Use this after running setup.bat once to quickly launch the GUI
REM ============================================================

title BIM Safety Analysis System

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

cd GUI_Application
python main.py

pause
