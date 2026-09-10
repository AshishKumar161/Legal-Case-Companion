@echo off
title Legal Case Companion Launcher
cd /d "%~dp0"
if exist "LegalCaseCompanion.exe" (
    start "" "LegalCaseCompanion.exe"
) else (
    echo [ERROR] LegalCaseCompanion.exe not found!
    pause
)
