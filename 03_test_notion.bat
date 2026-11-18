@echo off
cd /d "%~dp0"
call "%~dp0test_notion.bat"
exit /b %errorlevel%
