@echo off
title School Library - Production Backup System
color 0A

:: ============================================================
:: PRODUCTION BACKUP LAUNCHER
:: ============================================================

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

:: Activate virtual environment
if exist "%SCRIPT_DIR%venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%venv\Scripts\activate.bat"
)

:: Create logs directory
mkdir logs 2>nul

:: Run production backup
echo.
echo ========================================
echo   School Library Production Backup
echo ========================================
echo.
echo Starting backup at %date% %time%
echo.

python production_backup.py

:: Check exit code
if %errorlevel% equ 0 (
    echo.
    echo ✅ Backup completed successfully!
    echo.
) else (
    echo.
    echo ❌ Backup failed! Check logs/backup.log
    echo.
)

echo Press any key to exit...
pause >nul