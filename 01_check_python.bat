@echo off
cd /d "%~dp0"
call "%~dp0run_python.bat" --version
set "bot_exit=%errorlevel%"
pause
exit /b %bot_exit%
