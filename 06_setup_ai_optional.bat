@echo off
cd /d "%~dp0"
call "%~dp0setup_ai.bat"
exit /b %errorlevel%
