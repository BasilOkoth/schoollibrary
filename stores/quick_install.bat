@echo off
title School Library System - Quick Installer
color 0A

echo ========================================
echo   SCHOOL LIBRARY SYSTEM
echo   QUICK INSTALLER
echo ========================================
echo.

:: Check Python
echo [1/6] Checking Python installation...
python --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.11 or higher from python.org
    pause
    exit /b 1
)
echo [OK] Python found
echo.

:: Create virtual environment
echo [2/6] Creating virtual environment...
if not exist "venv" (
    python -m venv venv
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)
echo.

:: Activate environment
echo [3/6] Activating virtual environment...
call venv\Scripts\activate
echo [OK] Environment activated
echo.

:: Install dependencies
echo [4/6] Installing dependencies (this may take a few minutes)...
pip install --upgrade pip > nul
pip install -r requirements.txt
echo [OK] Dependencies installed
echo.

:: Run migrations
echo [5/6] Setting up database...
cd schoollibrary
python manage.py migrate
echo [OK] Database ready
echo.

:: Create admin user
echo [6/6] Creating admin user...
python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); User.objects.create_superuser('admin', 'admin@school.com', 'admin123') if not User.objects.filter(username='admin').exists() else None"
echo [OK] Admin user: admin / admin123
echo.

:: Create .env file
if not exist ".env" (
    echo Creating .env file...
    echo SECRET_KEY=production-secret-key-2026 > .env
    echo DEBUG=False >> .env
    echo ALLOWED_HOSTS=localhost,127.0.0.1 >> .env
    echo DB_ENGINE=django.db.backends.sqlite3 >> .env
    echo DB_NAME=db.sqlite3 >> .env
    echo MOCK_SMS_MODE=True >> .env
)

cd ..

echo.
echo ========================================
echo   INSTALLATION COMPLETE!
echo ========================================
echo.
echo To start the server:
echo   cd E:\schoollibrary\schoollibrary
echo   call ..\venv\Scripts\activate
echo   python manage.py runserver
echo.
echo Or run: start_server.bat
echo.
pause