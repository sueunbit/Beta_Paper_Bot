@echo off
cd /d "%~dp0"
call "%~dp0migrate_table.bat"
exit /b %errorlevel%
