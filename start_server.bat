@echo off
title SCHOOL LIBRARY SYSTEM - PRODUCTION
color 0A
setlocal enabledelayedexpansion

echo ========================================
echo   SCHOOL LIBRARY SYSTEM - PRODUCTION
echo ========================================
echo.

cd /d F:\somazone\schoollibrary\schoollibrary
call venv\Scripts\activate

echo [OK] Environment ready
echo.
echo 🚀 Starting PRODUCTION server...
echo.
echo    Local Access:    http://localhost:8000
echo    Phone Access:    http://192.168.1.101:8000 (change to your IP)
echo    Admin Panel:     http://localhost:8000/admin
echo    Login:           admin / admin123
echo.
echo    Press Ctrl+C to stop
echo ========================================
echo.

:: Get local IP for phone access
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4"') do (
    set LOCAL_IP=%%a
    set LOCAL_IP=!LOCAL_IP:~1!
)

:: Start server accessible from network
waitress-serve --port=8000 --host=0.0.0.0 --threads=8 --connection-limit=1000 schoollibrary.wsgi:application

pause