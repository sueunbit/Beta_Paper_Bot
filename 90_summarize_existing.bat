@echo off
cd /d "%~dp0"
call "%~dp0summarize_existing.bat"
exit /b %errorlevel%
