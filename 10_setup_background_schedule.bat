@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "%~dp0run_python.bat" (
  echo Copy these add-on files into your existing Paper Bot folder first.
  pause
  exit /b 1
)
call "%~dp0run_python.bat" background_tasks.py install
set "bot_exit=%errorlevel%"
pause
exit /b %bot_exit%
