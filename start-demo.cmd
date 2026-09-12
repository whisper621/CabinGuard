@echo off
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Missing .venv. Please create the Python environment first.
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0start_demo.py" %*
if errorlevel 1 pause
