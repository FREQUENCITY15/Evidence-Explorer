@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating the Python 3.14 virtual environment...
    py -3.14 -m venv .venv
    if errorlevel 1 goto :error
)

echo Installing Evidence Explorer / Project Mentor packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Setup complete. Double-click start_project_mentor.bat to run the app.
echo The Evidence Explorer pilot is available from the application home page.
pause
exit /b 0

:error
echo.
echo Setup did not complete. Copy the error above and send it to Aster.
pause
exit /b 1
