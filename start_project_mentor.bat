@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Evidence Explorer / Project Mentor is not set up yet.
    echo Run setup_project.bat first.
    pause
    exit /b 1
)

echo Starting Evidence Explorer / Project Mentor...
echo Project Mentor home: http://127.0.0.1:8000
echo Evidence Explorer: http://127.0.0.1:8000/evidence/QWEN-VSCODE-MCP-ECHO-001
echo Press Ctrl+C in this window when you want to stop the app.
echo.

".venv\Scripts\python.exe" -m uvicorn project_mentor.main:app --host 127.0.0.1 --port 8000

echo.
echo Evidence Explorer / Project Mentor has stopped.
pause
