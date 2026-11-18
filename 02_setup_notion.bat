@echo off
cd /d "%~dp0"
call "%~dp0setup_notion.bat"
exit /b %errorlevel%
