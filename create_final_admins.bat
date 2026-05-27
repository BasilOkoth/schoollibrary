@echo off
echo CREATING ADMINS FOR ALL SCHOOLS...
echo.

cd /d E:\schoollibrary\schoollibrary
call venv\Scripts\activate.bat

python manage.py create_tenant_admins --force

pause