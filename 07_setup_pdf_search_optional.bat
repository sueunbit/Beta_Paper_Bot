@echo off
cd /d "%~dp0"
call "%~dp0setup_fulltext.bat"
exit /b %errorlevel%
