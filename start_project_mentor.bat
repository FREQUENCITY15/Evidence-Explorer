@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Project Mentor is not set up yet.
    echo Run setup_project.bat first.
    pause
    exit /b 1
)

echo Starting Project Mentor...
echo Open http://127.0.0.1:8000 in your browser.
echo Press Ctrl+C in this window when you want to stop the app.
echo.

".venv\Scripts\python.exe" -m uvicorn project_mentor.main:app --host 127.0.0.1 --port 8000

echo.
echo Project Mentor has stopped.
pause
