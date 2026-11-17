@echo off
cd /d "%~dp0"
py -3.12 --version >nul 2>&1
if errorlevel 1 (
  py -3.11 --version >nul 2>&1
  if errorlevel 1 (
    echo Please install Python 3.12 or 3.11 64-bit with the Python Launcher.
    pause
    exit /b 1
  )
  py -3.11 -m venv .venv
) else (
  py -3.12 -m venv .venv
)
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Run run_windows.bat or press F5 in VS Code.
pause
exit /b 0
:failed
echo Setup failed. See README.md for troubleshooting.
pause
exit /b 1
