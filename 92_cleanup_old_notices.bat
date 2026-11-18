@echo off
cd /d "%~dp0"
call "%~dp0cleanup_pages.bat"
exit /b %errorlevel%
