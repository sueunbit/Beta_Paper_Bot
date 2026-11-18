@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0run_python.bat" ai_tools.py existing
set "bot_exit=%errorlevel%"
pause
exit /b %bot_exit%
