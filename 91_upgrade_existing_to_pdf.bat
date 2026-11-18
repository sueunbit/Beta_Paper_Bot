@echo off
cd /d "%~dp0"
call "%~dp0upgrade_fulltext.bat"
exit /b %errorlevel%
