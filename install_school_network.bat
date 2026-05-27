@echo off
setlocal enabledelayedexpansion

title SOMAZONE PRODUCTION INSTALLER
color 0A

:: Check admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell start -verb runas '%0'
    exit
)

echo ========================================
echo   SOMAZONE PRODUCTION INSTALLER
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not installed.
    pause
    exit /b 1
)

:: Inputs
set /p school_name="Enter School Name: "
set /p school_code="Enter School Code (no spaces): "
set /p admin_password="Enter strong admin password: "

set school_port=8000

:: Get IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set server_ip=%%a
    set server_ip=!server_ip:~1!
    goto :ip_found
)
:ip_found

echo.
echo URL: http://%server_ip%:%school_port%/app/
pause

:: Folders
echo [1/7] Creating folders...
mkdir "C:\Somazone\%school_code%\data" 2>nul
mkdir "C:\Somazone\%school_code%\media" 2>nul
mkdir "C:\Somazone\%school_code%\logs" 2>nul
echo OK

:: Copy app
echo [2/7] Copying app...
cd /d "%~dp0"
xcopy /E /I /Y "schoollibrary" "C:\Somazone\%school_code%\app\" >nul
if %errorlevel% neq 0 (
    echo ERROR copying files
    pause
    exit /b 1
)
echo OK

:: Create venv
echo [3/7] Creating virtual environment...
cd "C:\Somazone\%school_code%"
python -m venv venv
echo OK

:: Define venv python
set VENV_PYTHON=C:\Somazone\%school_code%\venv\Scripts\python.exe

if not exist "%VENV_PYTHON%" (
    echo ERROR: Venv Python not found
    pause
    exit /b 1
)

:: Install deps
echo [4/7] Installing dependencies...

cd "C:\Somazone\%school_code%\app"

"%VENV_PYTHON%" -m pip install --upgrade pip

if not exist requirements.txt (
    echo ERROR: requirements.txt missing
    pause
    exit /b 1
)

"%VENV_PYTHON%" -m pip install -r requirements.txt > "C:\Somazone\%school_code%\logs\install.log" 2>&1

echo OK

:: Create .env
echo [5/7] Creating environment file...

set secret=%random%%random%%random%%random%%random%%random%

(
echo SECRET_KEY=%secret%
echo DEBUG=False
echo ALLOWED_HOSTS=localhost,127.0.0.1,%server_ip%
echo DB_ENGINE=django.db.backends.sqlite3
echo DB_NAME=C:/Somazone/%school_code%/data/db.sqlite3
echo STATIC_ROOT=C:/Somazone/%school_code%/staticfiles
echo MEDIA_ROOT=C:/Somazone/%school_code%/media
echo SCHOOL_NAME=%school_name%
echo SCHOOL_ID=%school_code%
) > .env

echo OK

:: Migrate
echo [6/7] Setting up database...

"%VENV_PYTHON%" manage.py migrate --noinput > "C:\Somazone\%school_code%\logs\migrate.log" 2>&1
"%VENV_PYTHON%" manage.py collectstatic --noinput > "C:\Somazone\%school_code%\logs\static.log" 2>&1

"%VENV_PYTHON%" manage.py shell -c "from django.contrib.auth import get_user_model;User=get_user_model();User.objects.create_superuser('admin','admin@somazone.local','%admin_password%') if not User.objects.filter(username='admin').exists() else None"

echo OK

:: Start script
echo [7/7] Creating startup...

(
echo @echo off
echo cd /d "C:\Somazone\%school_code%\app"
echo "C:\Somazone\%school_code%\venv\Scripts\python.exe" -m waitress --host=0.0.0.0 --port=%school_port% schoollibrary.wsgi:application
) > "C:\Somazone\%school_code%\start.bat"

:: Desktop shortcuts
(
echo [InternetShortcut]
echo URL=http://%server_ip%:%school_port%/app/
) > "%USERPROFILE%\Desktop\Somazone Library.url"

(
echo [InternetShortcut]
echo URL=http://%server_ip%:%school_port%/admin/
) > "%USERPROFILE%\Desktop\Somazone Admin.url"

(
echo @echo off
echo start "" "C:\Somazone\%school_code%\start.bat"
) > "%USERPROFILE%\Desktop\Start Somazone.bat"

echo.
echo ========================================
echo   INSTALL COMPLETE
echo ========================================
echo.
echo Start server: Desktop → Start Somazone.bat
echo Access: http://%server_ip%:%school_port%/app/
echo Admin: admin / %admin_password%
echo.

pause