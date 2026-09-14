@echo off
title Legal Case Companion Launcher
cd /d "%~dp0"

echo [INFO] Cleaning up any zombie processes on ports 3000 and 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /F /PID %%a 2>nul
taskkill /F /IM cloudflared.exe 2>nul

if exist "LegalCaseCompanion.exe" (
    start "" "LegalCaseCompanion.exe"
) else (
    echo [ERROR] LegalCaseCompanion.exe not found!
    pause
)
