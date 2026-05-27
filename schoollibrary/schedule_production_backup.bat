@echo off
title Schedule Production Backup
color 0A

echo ========================================
echo   Schedule Production Backup
echo ========================================
echo.

set SCRIPT_DIR=E:\schoollibrary\schoollibrary

:: Remove existing task if exists
schtasks /delete /tn "SchoolLibraryProductionBackup" /f 2>nul

:: Create new scheduled task
schtasks /create ^
    /tn "SchoolLibraryProductionBackup" ^
    /tr "%SCRIPT_DIR%\backup_production.bat" ^
    /sc daily ^
    /st 02:00 ^
    /ru "SYSTEM" ^
    /rl HIGHEST ^
    /f

echo.
echo ✅ Production backup scheduled!
echo    Task: SchoolLibraryProductionBackup
echo    Time: Daily at 2:00 AM
echo.
echo To test immediately, run: backup_production.bat
echo.
pause