@echo off
cd /d "%~dp0"
if not exist "config.json" copy "config.example.json" "config.json" >nul
if not exist "config.json" (
  echo Could not create config.json. Check folder permissions.
  pause
  exit /b 1
)
start "" notepad.exe "%~dp0config.json"
