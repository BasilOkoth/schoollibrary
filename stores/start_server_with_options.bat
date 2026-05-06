@echo off
title School Library Server - Multi-Tenant
color 0A

:: Auto-detect location
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:MENU
cls
echo ========================================
echo    School Library Server Launcher
echo    Multi-Tenant Edition
echo ========================================
echo.
echo Script Location: %SCRIPT_DIR%
echo.
echo 1. Start Server (Default - Port 8000)
echo 2. Start Server on Different Port
echo 3. Show IP Address Only
echo 4. List All Tenants
echo 5. Get Tenant Phone URL
echo 6. Open Project Folder
echo 7. Open in Browser
echo 8. Create Phone Access QR Code
echo 9. Install/Update Requirements
echo 10. Run Migrations
echo 11. Add Tenant Domain (localhost/127.0.0.1/IP)
echo 12. Admin Credentials & Superuser Management
echo 13. Exit
echo.
set /p choice="Select option (1-13): "

if "%choice%"=="1" goto START_SERVER
if "%choice%"=="2" goto CUSTOM_PORT
if "%choice%"=="3" goto SHOW_IP
if "%choice%"=="4" goto LIST_TENANTS
if "%choice%"=="5" goto TENANT_URL
if "%choice%"=="6" start explorer "%SCRIPT_DIR%" && goto MENU
if "%choice%"=="7" goto OPEN_BROWSER
if "%choice%"=="8" goto CREATE_QR
if "%choice%"=="9" goto INSTALL_DEPS
if "%choice%"=="10" goto RUN_MIGRATIONS
if "%choice%"=="11" goto ADD_TENANT_DOMAIN
if "%choice%"=="12" goto ADMIN_MANAGEMENT
if "%choice%"=="13" exit
goto MENU

:SHOW_IP
cls
echo ========================================
echo        Getting IP Address...
echo ========================================
echo.
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set "IP=%%a"
)
set "IP=%IP: =%"
echo Your IP Address: %IP%
echo.
echo Phone access URL: http://%IP%:8000/
echo.
echo IP saved to: %SCRIPT_DIR%\last_ip.txt
echo %IP% > "%SCRIPT_DIR%\last_ip.txt"
echo.
pause
goto MENU

:LIST_TENANTS
cls
echo ========================================
echo        Listing All Tenants
echo ========================================
echo.

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo Fetching tenants from database...
echo.
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from tenants.models import School, Domain
print('\n=== AVAILABLE TENANTS ===')
for school in School.objects.all():
    print(f'ID: {school.id} | Name: {school.name} | Schema: {school.schema_name}')
    for domain in school.domains.all():
        print(f'   Domain: {domain.domain} (Primary: {domain.is_primary})')
print('\n=======================')
" 2>nul

if %errorlevel% neq 0 (
    echo.
    echo ⚠ Could not fetch tenants. Make sure:
    echo 1. Database is migrated
    echo 2. Django settings are correct
    echo 3. You have created tenants
)

echo.
pause
goto MENU

:TENANT_URL
cls
echo ========================================
echo        Get Tenant Phone URL
echo ========================================
echo.

:: Get IP address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set "IP=%%a"
)
set "IP=%IP: =%"

echo Enter tenant details:
echo.
set /p tenant_id="Tenant ID (from list): "
set /p port="Port (default 8000): "
if "%port%"=="" set port=8000

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo.
echo Fetching tenant URL...
echo.

python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from tenants.models import School
try:
    school = School.objects.get(id=%tenant_id%)
    print(f'\n=== TENANT ACCESS INFORMATION ===')
    print(f'School: {school.name}')
    print(f'Schema: {school.schema_name}')
    print(f'\n📱 Phone Access URLs:')
    for domain in school.domains.all():
        url = domain.domain
        if not url.startswith('http'):
            if '.' in url:  # Custom domain
                print(f'   🌐 Custom: {url}')
            else:  # Local development
                print(f'   📱 Phone: http://%IP%:%port%/?tenant={url}')
                print(f'   🔗 Local: http://{url}.localhost:%port%/')
                print(f'   📝 Note: Add to hosts file if needed')
    print(f'\n🔑 Admin URL: http://%IP%:%port%/admin')
    print(f'\n================================')
except School.DoesNotExist:
    print(f'❌ Tenant with ID {tenant_id} not found')
except Exception as e:
    print(f'❌ Error: {e}')
"

echo.
echo URLs saved to: %SCRIPT_DIR%\tenant_%tenant_id%_url.txt
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from tenants.models import School
try:
    school = School.objects.get(id=%tenant_id%)
    with open(r'%SCRIPT_DIR%\tenant_%tenant_id%_url.txt', 'w') as f:
        f.write(f'School: {school.name}\n')
        f.write(f'Schema: {school.schema_name}\n\n')
        f.write('Phone Access URLs:\n')
        for domain in school.domains.all():
            url = domain.domain
            if '.' in url:
                f.write(f'Custom: {url}\n')
            else:
                f.write(f'Phone: http://%IP%:%port%/?tenant={url}\n')
                f.write(f'Local: http://{url}.localhost:%port%/\n')
        f.write(f'\nAdmin: http://%IP%:%port%/admin\n')
    print('✅ File saved!')
except:
    pass
" 2>nul

echo.
pause
goto MENU

:ADD_TENANT_DOMAIN
cls
echo ========================================
echo        Add Domain to Tenant
echo ========================================
echo.
echo This adds domain/IP access to a tenant
echo.

:: Get IP address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set "IP=%%a"
)
set "IP=%IP: =%"

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo Select what to add:
echo.
echo 1. Add localhost to Public Tenant
echo 2. Add 127.0.0.1 to Public Tenant
echo 3. Add Current IP (%IP%) to Public Tenant
echo 4. Add Custom Domain to Specific Tenant
echo 5. Add All Common Domains to Public Tenant
echo.
set /p domain_choice="Select option (1-5): "

if "%domain_choice%"=="1" goto ADD_LOCALHOST
if "%domain_choice%"=="2" goto ADD_127
if "%domain_choice%"=="3" goto ADD_IP
if "%domain_choice%"=="4" goto ADD_CUSTOM
if "%domain_choice%"=="5" goto ADD_ALL
goto MENU

:ADD_LOCALHOST
cls
echo.
echo Adding localhost to Public Tenant...
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from tenants.models import Domain, Tenant
try:
    public_tenant = Tenant.objects.get(schema_name='public')
    domain, created = Domain.objects.get_or_create(
        domain='localhost',
        tenant=public_tenant,
        defaults={'is_primary': True}
    )
    if created:
        print('✅ Added localhost to public tenant as PRIMARY')
    else:
        print(f'localhost already exists for {domain.tenant.name}')
except Exception as e:
    print(f'❌ Error: {e}')
"
echo.
pause
goto MENU

:ADD_127
cls
echo.
echo Adding 127.0.0.1 to Public Tenant...
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from tenants.models import Domain, Tenant
try:
    public_tenant = Tenant.objects.get(schema_name='public')
    domain, created = Domain.objects.get_or_create(
        domain='127.0.0.1',
        tenant=public_tenant,
        defaults={'is_primary': False}
    )
    if created:
        print('✅ Added 127.0.0.1 to public tenant')
    else:
        print(f'127.0.0.1 already exists for {domain.tenant.name}')
except Exception as e:
    print(f'❌ Error: {e}')
"
echo.
pause
goto MENU

:ADD_IP
cls
echo.
echo Adding %IP% to Public Tenant...
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from tenants.models import Domain, Tenant
try:
    public_tenant = Tenant.objects.get(schema_name='public')
    domain, created = Domain.objects.get_or_create(
        domain='%IP%',
        tenant=public_tenant,
        defaults={'is_primary': False}
    )
    if created:
        print('✅ Added %IP% to public tenant')
    else:
        print(f'%IP% already exists for {domain.tenant.name}')
except Exception as e:
    print(f'❌ Error: {e}')
"
echo.
pause
goto MENU

:ADD_CUSTOM
cls
echo.
echo List available tenants:
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from tenants.models import Tenant
for tenant in Tenant.objects.all():
    print(f'  ID: {tenant.id} | Name: {tenant.name} | Schema: {tenant.schema_name}')
"
echo.
set /p tenant_id="Enter Tenant ID: "
set /p custom_domain="Enter Domain name (e.g., myschool.localhost or 192.168.1.100): "
set /p is_primary="Is this primary domain? (y/n): "

if /i "%is_primary%"=="y" (
    set primary_flag=True
) else (
    set primary_flag=False
)

echo.
echo Adding %custom_domain% to tenant ID %tenant_id%...
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from tenants.models import Domain, Tenant
try:
    tenant = Tenant.objects.get(id=%tenant_id%)
    domain, created = Domain.objects.get_or_create(
        domain='%custom_domain%',
        tenant=tenant,
        defaults={'is_primary': %primary_flag%}
    )
    if created:
        print(f'✅ Added {domain.domain} to {tenant.name}')
    else:
        print(f'{domain.domain} already exists for {domain.tenant.name}')
except Exception as e:
    print(f'❌ Error: {e}')
"
echo.
pause
goto MENU

:ADD_ALL
cls
echo.
echo Adding all common domains to Public Tenant...
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from tenants.models import Domain, Tenant

try:
    public_tenant = Tenant.objects.get(schema_name='public')
    
    domains_to_add = [
        ('localhost', True),
        ('127.0.0.1', False),
        ('%IP%', False),
    ]
    
    for domain_name, is_primary in domains_to_add:
        domain, created = Domain.objects.get_or_create(
            domain=domain_name,
            tenant=public_tenant,
            defaults={'is_primary': is_primary}
        )
        if created:
            print(f'✅ Added {domain_name} (Primary: {is_primary})')
        else:
            print(f'⚠ {domain_name} already exists')
            
    print('\n🎉 All domains added successfully!')
    print('\nYour SomaZone system is now accessible via:')
    print('  - http://localhost:8000')
    print('  - http://127.0.0.1:8000')
    print('  - http://%IP%:8000')
    
except Exception as e:
    print(f'❌ Error: {e}')
"
echo.
pause
goto MENU

:ADMIN_MANAGEMENT
cls
echo ========================================
echo     Admin Credentials Management
echo ========================================
echo.
echo 1. List All Superusers (Global Admins)
echo 2. Create New Superuser (Global Admin)
echo 3. Change Superuser Password
echo 4. Check if Superuser Exists
echo 5. Create Default Admin (username: somazone_admin)
echo 6. Reset Forgotten Password (Interactive)
echo 7. Tenant Admin Management (Per Tenant)
echo 8. Back to Main Menu
echo.
set /p admin_choice="Select option (1-8): "

if "%admin_choice%"=="1" goto LIST_SUPERUSERS
if "%admin_choice%"=="2" goto CREATE_SUPERUSER
if "%admin_choice%"=="3" goto CHANGE_PASSWORD
if "%admin_choice%"=="4" goto CHECK_SUPERUSER
if "%admin_choice%"=="5" goto CREATE_DEFAULT_ADMIN
if "%admin_choice%"=="6" goto RESET_PASSWORD
if "%admin_choice%"=="7" goto TENANT_ADMIN_MANAGEMENT
if "%admin_choice%"=="8" goto MENU
goto ADMIN_MANAGEMENT

:LIST_SUPERUSERS
cls
echo.
echo ========================================
echo        Listing All Superusers
echo ========================================
echo.

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo.
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from django.contrib.auth.models import User

users = User.objects.filter(is_superuser=True)
if users.exists():
    print('=== GLOBAL SUPERUSERS ===')
    for user in users:
        print(f'  Username: {user.username}')
        print(f'  Email: {user.email}')
        print(f'  Last Login: {user.last_login}')
        print(f'  Date Joined: {user.date_joined}')
        print('  ---')
    print(f'Total: {users.count()} superuser(s)')
else:
    print('⚠ No superuser found. Create one using option 2.')
"
echo.
echo.
echo Credentials saved to: %SCRIPT_DIR%\superusers_list.txt
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from django.contrib.auth.models import User
with open(r'%SCRIPT_DIR%\superusers_list.txt', 'w') as f:
    users = User.objects.filter(is_superuser=True)
    f.write('=== SOMAzone GLOBAL SUPERUSERS ===\n\n')
    for user in users:
        f.write(f'Username: {user.username}\n')
        f.write(f'Email: {user.email}\n')
        f.write(f'Last Login: {user.last_login}\n')
        f.write('-' * 30 + '\n')
    f.write(f'\nTotal: {users.count()} superuser(s)\n')
"
echo.
pause
goto ADMIN_MANAGEMENT

:CREATE_SUPERUSER
cls
echo.
echo ========================================
echo        Create New Superuser
echo ========================================
echo.
set /p new_username="Enter username: "
set /p new_email="Enter email: "
set /p new_password="Enter password: "

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo.
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from django.contrib.auth.models import User

username = '%new_username%'
email = '%new_email%'
password = '%new_password%'

if User.objects.filter(username=username).exists():
    print(f'❌ Username \"{username}\" already exists!')
else:
    User.objects.create_superuser(username, email, password)
    print(f'✅ Superuser \"{username}\" created successfully!')
    print(f'   Email: {email}')
    print(f'   Password: {password}')
"
echo.
pause
goto ADMIN_MANAGEMENT

:CHANGE_PASSWORD
cls
echo.
echo ========================================
echo        Change Superuser Password
echo ========================================
echo.
set /p change_username="Enter username to change password: "
set /p change_password="Enter new password: "

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo.
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from django.contrib.auth.models import User

username = '%change_username%'
new_password = '%change_password%'

try:
    user = User.objects.get(username=username)
    user.set_password(new_password)
    user.save()
    print(f'✅ Password changed for \"{username}\"')
except User.DoesNotExist:
    print(f'❌ User \"{username}\" not found!')
"
echo.
pause
goto ADMIN_MANAGEMENT

:CHECK_SUPERUSER
cls
echo.
echo ========================================
echo        Checking Superuser Exists
echo ========================================
echo.

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo.
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from django.contrib.auth.models import User

if User.objects.filter(is_superuser=True).exists():
    print('✅ Superuser exists in the system!')
    for user in User.objects.filter(is_superuser=True):
        print(f'   → {user.username}')
else:
    print('❌ No superuser found! Please create one using option 2.')
"
echo.
pause
goto ADMIN_MANAGEMENT

:CREATE_DEFAULT_ADMIN
cls
echo.
echo ========================================
echo     Creating Default Admin: somazone_admin
echo ========================================
echo.

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo.
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from django.contrib.auth.models import User

username = 'somazone_admin'
email = 'admin@somazone.com'
password = 'Somazone@2024'

if User.objects.filter(username=username).exists():
    print(f'⚠ User \"{username}\" already exists!')
else:
    User.objects.create_superuser(username, email, password)
    print(f'✅ Default superuser created!')
    print(f'   Username: {username}')
    print(f'   Email: {email}')
    print(f'   Password: {password}')
    print(f'\n🔐 Login at: http://localhost:8000/admin/')
"
echo.
pause
goto ADMIN_MANAGEMENT

:RESET_PASSWORD
cls
echo.
echo ========================================
echo     Reset Forgotten Password
echo ========================================
echo.
set /p reset_username="Enter username to reset password: "

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo.
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from django.contrib.auth.models import User

username = '%reset_username%'

try:
    user = User.objects.get(username=username)
    new_password = 'Somazone@2024'
    user.set_password(new_password)
    user.save()
    print(f'✅ Password reset for \"{username}\"')
    print(f'   New password: {new_password}')
    print(f'\n🔐 Login at: http://localhost:8000/admin/')
except User.DoesNotExist:
    print(f'❌ User \"{username}\" not found!')
"
echo.
pause
goto ADMIN_MANAGEMENT

:TENANT_ADMIN_MANAGEMENT
cls
echo ========================================
echo     Tenant Admin Management
echo ========================================
echo.
echo This creates/views admin users for specific tenants
echo.

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo.
echo Listing available tenants...
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from tenants.models import Tenant
print('\n=== AVAILABLE TENANTS ===')
for tenant in Tenant.objects.all():
    print(f'  ID: {tenant.id} | Name: {tenant.name} | Schema: {tenant.schema_name}')
print('')
"
echo.
echo 1. Create Admin for a Specific Tenant
echo 2. List All Staff/Admins for a Specific Tenant
echo 3. Create Default Admins for ALL Tenants
echo 4. Back to Admin Management
echo.
set /p tenant_admin_choice="Select option (1-4): "

if "%tenant_admin_choice%"=="1" goto CREATE_TENANT_ADMIN
if "%tenant_admin_choice%"=="2" goto LIST_TENANT_ADMINS
if "%tenant_admin_choice%"=="3" goto CREATE_ALL_TENANT_ADMINS
if "%tenant_admin_choice%"=="4" goto ADMIN_MANAGEMENT
goto TENANT_ADMIN_MANAGEMENT

:CREATE_TENANT_ADMIN
cls
echo.
echo ========================================
echo     Create Tenant Admin User
echo ========================================
echo.
set /p tenant_id_for_admin="Enter Tenant ID: "
set /p tenant_admin_username="Enter admin username: "
set /p tenant_admin_email="Enter admin email: "
set /p tenant_admin_password="Enter password (default: Tenant@2024): "
if "%tenant_admin_password%"=="" set tenant_admin_password=Tenant@2024

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo.
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from django.contrib.auth.models import User
from tenants.models import Tenant

username = '%tenant_admin_username%'
email = '%tenant_admin_email%'
password = '%tenant_admin_password%'
tenant_id = %tenant_id_for_admin%

try:
    tenant = Tenant.objects.get(id=tenant_id)
    
    # Check if user exists, create if not
    if not User.objects.filter(username=username).exists():
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_staff = True
        user.save()
        print(f'✅ User \"{username}\" created and set as staff')
    else:
        user = User.objects.get(username=username)
        user.is_staff = True
        user.save()
        print(f'✅ User \"{username}\" already exists, updated to staff')
    
    # Note: In django-tenants, user permissions work across all schemas
    print(f'\n📋 TENANT ADMIN CREDENTIALS:')
    print(f'   Tenant: {tenant.name} (Schema: {tenant.schema_name})')
    print(f'   Username: {username}')
    print(f'   Password: {password}')
    print(f'\n🔐 Login at:')
    print(f'   http://localhost:8000/admin/')
    print(f'   http://{tenant.schema_name}.localhost:8000/admin/')
    
except Tenant.DoesNotExist:
    print(f'❌ Tenant with ID {tenant_id} not found!')
"
echo.
pause
goto TENANT_ADMIN_MANAGEMENT

:LIST_TENANT_ADMINS
cls
echo.
echo ========================================
echo     List Staff/Admins for Tenant
echo ========================================
echo.
set /p tenant_id_for_list="Enter Tenant ID: "

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo.
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from django.contrib.auth.models import User
from tenants.models import Tenant

tenant_id = %tenant_id_for_list%

try:
    tenant = Tenant.objects.get(id=tenant_id)
    print(f'\n=== STAFF/ADMINS FOR TENANT: {tenant.name} ===')
    staff_users = User.objects.filter(is_staff=True)
    if staff_users.exists():
        for user in staff_users:
            role = 'SUPERUSER' if user.is_superuser else 'STAFF'
            print(f'  Username: {user.username} | Email: {user.email} | Role: {role}')
    else:
        print('  No staff/admins found for this tenant')
    print(f'\nTotal: {staff_users.count()} staff user(s)')
    
except Tenant.DoesNotExist:
    print(f'❌ Tenant with ID {tenant_id} not found!')
"
echo.
pause
goto TENANT_ADMIN_MANAGEMENT

:CREATE_ALL_TENANT_ADMINS
cls
echo.
echo ========================================
echo     Creating Default Admins for ALL Tenants
echo ========================================
echo.
echo This will create an admin for each tenant with:
echo   Username: [tenant_schema]_admin
echo   Password: Tenant@2024
echo.

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo.
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from django.contrib.auth.models import User
from tenants.models import Tenant

print('\n=== CREATING TENANT ADMINS ===')
for tenant in Tenant.objects.all():
    username = f'{tenant.schema_name}_admin'
    email = f'admin@{tenant.schema_name}.somazone.com'
    password = 'Tenant@2024'
    
    if not User.objects.filter(username=username).exists():
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_staff = True
        user.save()
        print(f'✅ Created: {username} for {tenant.name}')
    else:
        user = User.objects.get(username=username)
        user.is_staff = True
        user.save()
        print(f'⚠ Already exists: {username} (updated to staff)')
    
    print(f'   → Password: {password}')
    print(f'   → Login: http://localhost:8000/admin/')
    print('')

print('✅ ALL TENANT ADMINS PROCESSED!')
print('\n📋 SUMMARY:')
for tenant in Tenant.objects.all():
    username = f'{tenant.schema_name}_admin'
    print(f'   {tenant.name}: {username} / Tenant@2024')
"
echo.
echo.
echo Credentials saved to: %SCRIPT_DIR%\tenant_admins_list.txt
python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()
from tenants.models import Tenant
with open(r'%SCRIPT_DIR%\tenant_admins_list.txt', 'w') as f:
    f.write('=== SOMAzone TENANT ADMINS ===\n\n')
    f.write('Default Password for all: Tenant@2024\n\n')
    for tenant in Tenant.objects.all():
        username = f'{tenant.schema_name}_admin'
        f.write(f'Tenant: {tenant.name}\n')
        f.write(f'  Username: {username}\n')
        f.write(f'  Email: admin@{tenant.schema_name}.somazone.com\n')
        f.write(f'  Password: Tenant@2024\n')
        f.write('  ---\n')
"
echo.
pause
goto TENANT_ADMIN_MANAGEMENT

:START_SERVER
cls
echo ========================================
echo    Starting Server on Port 8000
echo ========================================
echo.

:: Get IP address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set "IP=%%a"
)
set "IP=%IP: =%"

:: Save IP
echo %IP% > "%SCRIPT_DIR%\last_ip.txt"
echo URL: http://%IP%:8000/ > "%SCRIPT_DIR%\phone_url.txt"
echo Admin URL: http://localhost:8000/admin/ >> "%SCRIPT_DIR%\admin_info.txt"
echo Tenant Admins: see tenant_admins_list.txt >> "%SCRIPT_DIR%\admin_info.txt"

:: Display access info
echo.
echo ========================================
echo        Access Information
echo ========================================
echo.
echo Project: %SCRIPT_DIR%
echo IP:      %IP%
echo.
echo Local:   http://localhost:8000/
echo Local:   http://127.0.0.1:8000/
echo Phone:   http://%IP%:8000/
echo Admin:   http://localhost:8000/admin/
echo.
echo ========================================
echo.
echo Tenant Access:
echo Phone: http://%IP%:8000/?tenant=tenant_name
echo Local: http://tenant_name.localhost:8000/
echo.
echo ========================================

:: Activate venv if it exists
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

:: Start server
python "%SCRIPT_DIR%\manage.py" runserver 0.0.0.0:8000
goto MENU

:CUSTOM_PORT
cls
set /p port="Enter port number (e.g., 8080, 8001): "
echo.

:: Get IP address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set "IP=%%a"
)
set "IP=%IP: =%"

echo.
echo ========================================
echo        Access Information
echo ========================================
echo.
echo Project: %SCRIPT_DIR%
echo IP:      %IP%
echo Port:    %port%
echo.
echo Local:   http://localhost:%port%/
echo Local:   http://127.0.0.1:%port%/
echo Phone:   http://%IP%:%port%/
echo Admin:   http://localhost:%port%/admin/
echo.
echo Tenant Access:
echo Phone: http://%IP%:%port%/?tenant=tenant_name
echo Local: http://tenant_name.localhost:%port%/
echo.
echo ========================================
echo.

:: Activate venv
if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

python "%SCRIPT_DIR%\manage.py" runserver 0.0.0.0:%port%
goto MENU

:OPEN_BROWSER
cls
echo ========================================
echo        Opening in Browser
echo ========================================
echo.
echo 1. Localhost (http://localhost:8000/)
echo 2. Local IP (http://127.0.0.1:8000/)
echo 3. Phone URL (http://%IP%:8000/)
echo 4. Admin Panel (http://localhost:8000/admin/)
echo 5. Tenant with subdomain (tenant_name.localhost:8000)
echo 6. Tenant with query param (http://localhost:8000/?tenant=name)
echo 7. Custom URL
echo.
set /p browse_choice="Select option: "

if "%browse_choice%"=="1" start http://localhost:8000/
if "%browse_choice%"=="2" start http://127.0.0.1:8000/
if "%browse_choice%"=="3" (
    for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
        set "IP=%%a"
    )
    set "IP=%IP: =%"
    start http://%IP%:8000/
)
if "%browse_choice%"=="4" start http://localhost:8000/admin/
if "%browse_choice%"=="5" (
    set /p tenant="Enter tenant name: "
    start http://%tenant%.localhost:8000/
)
if "%browse_choice%"=="6" (
    set /p tenant="Enter tenant name: "
    start http://localhost:8000/?tenant=%tenant%
)
if "%browse_choice%"=="7" (
    set /p custom_url="Enter URL: "
    start %custom_url%
)
goto MENU

:CREATE_QR
cls
echo ========================================
echo        Create Phone Access QR Code
echo ========================================
echo.
echo 1. QR for main site
echo 2. QR for specific tenant
echo.
set /p qr_choice="Select option: "

:: Get IP address
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set "IP=%%a"
)
set "IP=%IP: =%"

if "%qr_choice%"=="1" (
    set "qr_url=http://%IP%:8000/"
    set "qr_file=phone_qr.png"
) else if "%qr_choice%"=="2" (
    set /p tenant="Enter tenant name: "
    set "qr_url=http://%IP%:8000/?tenant=%tenant%"
    set "qr_file=tenant_%tenant%_qr.png"
) else (
    goto MENU
)

echo Phone URL: %qr_url%
echo.

:: Try to create QR code using Python if qrcode is installed
python -c "import qrcode" 2>nulif %errorlevel%==0 (
    python -c "import qrcode; img = qrcode.make('%qr_url%'); img.save('%SCRIPT_DIR%\\%qr_file%')" 2>nul
    if exist "%SCRIPT_DIR%\%qr_file%" (
        echo ✅ QR Code created: %SCRIPT_DIR%\%qr_file%
        start "%SCRIPT_DIR%\%qr_file%"
    ) else (
        echo ⚠ QR code generation failed.
    )
) else (
    echo QR code library not installed.
    echo Install with: pip install qrcode[pil]
    echo.
    echo Or use this URL manually: %qr_url%
)

echo.
pause
goto MENU

:INSTALL_DEPS
cls
echo ========================================
echo     Installing/Updating Requirements
echo ========================================
echo.

if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

if exist "%SCRIPT_DIR%\requirements.txt" (
    echo Installing from requirements.txt...
    pip install -r "%SCRIPT_DIR%\requirements.txt"
) else (
    echo No requirements.txt found.
    echo Installing common packages...
    pip install django django-tenants djangorestframework pillow psycopg2-binary
)

echo.
echo Installing qrcode for QR generation...
pip install qrcode[pil]

echo.
pause
goto MENU

:RUN_MIGRATIONS
cls
echo ========================================
echo        Running Migrations
echo ========================================
echo.

if exist "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
)

echo Running migrations...
python "%SCRIPT_DIR%\manage.py" migrate_schemas

echo.
echo ✅ Migrations complete!
echo.
pause
goto MENU