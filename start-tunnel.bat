@echo off
title Legal Case Companion - Instant Public Tunnel
cd /d "%~dp0"

echo ======================================================================
echo           Legal Case Companion - Public Tunnel Launcher
echo ======================================================================
echo.
echo Starting Cloudflare Tunnel for http://localhost:3000 ...
echo A public HTTPS URL (https://*.trycloudflare.com) will be generated.
echo Share this URL to access the application from any mobile or laptop!
echo.
echo Press Ctrl+C at any time to stop the tunnel.
echo ======================================================================
echo.

if exist "cloudflared.exe" (
    .\cloudflared.exe tunnel --url http://localhost:3000
) else (
    echo [ERROR] cloudflared.exe not found in this directory!
    pause
)
