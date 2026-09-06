@echo off
title Legal Case Companion Launcher
cd /d "%~dp0"
if exist "LegalCaseCompanion.exe" (
    start "" "LegalCaseCompanion.exe"
) else if exist "Legal-Case-Companion-main\LegalCaseCompanion.exe" (
    cd "Legal-Case-Companion-main"
    start "" "LegalCaseCompanion.exe"
) else (
    echo [ERROR] LegalCaseCompanion.exe not found!
    pause
)
