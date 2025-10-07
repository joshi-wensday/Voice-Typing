@echo off
REM Voice Typing Launcher
REM This script launches Voice Typing in the background

cd /d "%~dp0"

REM Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo Error: Virtual environment not found!
    echo Please run: python scripts\setup_dev.py
    pause
    exit /b 1
)

REM Activate venv and launch Voice Typing
echo Starting Voice Typing...
venv\Scripts\python.exe -m voice_typing

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo Voice Typing exited with an error.
    pause
)

