@echo off
cd /d "%~dp0"
call "%~dp0run_demo.bat"
exit /b %errorlevel%
