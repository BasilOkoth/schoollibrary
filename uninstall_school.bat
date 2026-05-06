@echo off
title Uninstall School Library
color 0C

:: Run as Administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell start -verb runas '%0'
    exit
)

echo ========================================
echo   UNINSTALL SCHOOL LIBRARY
echo ========================================
echo.

set /p school_name="Enter school name to uninstall: "

echo.
echo Stopping service...
sc stop "SchoolLibrary_%school_name%" > nul 2>&1
sc delete "SchoolLibrary_%school_name%" > nul 2>&1

echo Removing files...
rmdir /s /q "C:\SchoolLibrary\%school_name%" 2>nul

echo Removing desktop shortcuts...
del "%USERPROFILE%\Desktop\%school_name% Library.url" 2>nul
del "%USERPROFILE%\Desktop\%school_name% QR Code.png" 2>nul
del "%USERPROFILE%\Desktop\Restart %school_name% Library.bat" 2>nul
del "%USERPROFILE%\Desktop\%school_name% Access.txt" 2>nul

echo.
echo ✅ %school_name% uninstalled!
pause