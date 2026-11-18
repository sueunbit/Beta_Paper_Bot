@echo off
cd /d "%~dp0"
call "%~dp0import_existing.bat"
exit /b %errorlevel%
