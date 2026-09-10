@echo off
title Build LegalCaseCompanion.exe
cd /d "%~dp0\.."

set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" (
    set CSC=csc.exe
)

echo [BUILD] Compiling launcher with embedded logo icon...
"%CSC%" /target:exe /out:LegalCaseCompanion.exe /win32icon:LegalCaseCompanion.ico scripts\launcher.cs

if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] LegalCaseCompanion.exe built successfully with embedded icon!
) else (
    echo [ERROR] Build failed with exit code %ERRORLEVEL%
)
