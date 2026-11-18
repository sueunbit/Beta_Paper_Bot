@echo off
cd /d "%~dp0"
call "%~dp0run_basic.bat"
exit /b %errorlevel%
