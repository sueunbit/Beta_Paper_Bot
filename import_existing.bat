@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0run_python.bat" notion_table.py import
set "bot_exit=%errorlevel%"
pause
exit /b %bot_exit%
