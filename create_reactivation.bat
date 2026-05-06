@echo off
title Reactivate School Library
color 0A

echo ========================================
echo   REACTIVATE SCHOOL LIBRARY
echo ========================================
echo.
echo Use this if hardware changed or computer was replaced.
echo.

set /p school_name="Enter school name: "
set /p old_key="Enter original hardware key (from Hardware_Info file): "

:: Get new hardware key
for /f "tokens=2 delims==" %%a in ('wmic csproduct get uuid /value ^| find "="') do set NEW_ID=%%a
for /f "tokens=2 delims==" %%a in ('wmic bios get serialnumber /value ^| find "="') do set NEW_BIOS=%%a
for /f "tokens=2 delims==" %%a in ('wmic baseboard get serialnumber /value ^| find "="') do set NEW_MB=%%a
set NEW_KEY=%NEW_ID%-%NEW_BIOS:~0,8%-%NEW_MB:~0,8%
set NEW_KEY=%NEW_KEY: =%

echo.
echo Old Key: %old_key%
echo New Key: %NEW_KEY%
echo.

set /p confirm="Update hardware key? (y/n): "
if /i not "%confirm%"=="y" exit

:: Update hardware key
echo %NEW_KEY% > "C:\SchoolLibrary\%school_name%\hardware.key"

:: Restart service
sc stop "SchoolLibrary_%school_name%"
timeout /t 3 /nobreak > nul
sc start "SchoolLibrary_%school_name%"

echo.
echo ✅ Hardware key updated!
echo ✅ Service restarted!
echo.
pause