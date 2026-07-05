@echo off
rem Vype V2 dev launcher — runs from the repo's .venv
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No .venv found. Set it up first:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -e .[ui,parakeet,dev]
    pause
    exit /b 1
)

echo Starting Vype... hold Ctrl+Alt to dictate, tap to lock hands-free.
".venv\Scripts\python.exe" -m vype.app
pause
