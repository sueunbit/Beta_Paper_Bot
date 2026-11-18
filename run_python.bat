@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
  if not errorlevel 1 goto use_venv
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 goto use_py
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 goto use_python
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if not errorlevel 1 goto use_python3
echo.
echo Python 3.10 or newer was not found.
echo Install Python for Windows: https://www.python.org/downloads/windows/
echo Ensure Python is available as python or py, then reopen this batch file.
echo If already installed, try: python --version
echo.
exit /b 1
:use_venv
".venv\Scripts\python.exe" %*
exit /b %errorlevel%
:use_py
py -3 %*
exit /b %errorlevel%
:use_python
python %*
exit /b %errorlevel%
:use_python3
python3 %*
exit /b %errorlevel%
