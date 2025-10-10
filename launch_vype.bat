@echo off
REM Vype Launcher
REM This script launches Vype in the background

cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo Error: Virtual environment not found!
    echo Please run: python scripts\setup_dev.py
    pause
    exit /b 1
)

REM Activate venv and launch Vype
echo Starting Vype...
venv\Scripts\python.exe -m vype

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo Vype exited with an error.
    pause
)


