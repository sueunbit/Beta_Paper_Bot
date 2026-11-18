@echo off
cd /d "%~dp0"
call "%~dp0setup_table.bat"
exit /b %errorlevel%
