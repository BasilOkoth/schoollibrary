#!/usr/bin/env python
"""
SCHOOL INSTALLER - One Click Setup for New Schools
Run: python school_installer.py
"""

import os
import sys
import subprocess
import secrets
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'

def print_status(message, status="info"):
    if status == "success":
        print(f"{GREEN}✓ {message}{RESET}")
    elif status == "error":
        print(f"{RED}✗ {message}{RESET}")
    elif status == "warning":
        print(f"{YELLOW}⚠ {message}{RESET}")
    else:
        print(f"{BLUE}➜ {message}{RESET}")

def print_header(text):
    print("\n" + "="*60)
    print(f"{CYAN}{text.center(60)}{RESET}")
    print("="*60)

def run_command(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr

def get_school_info():
    """Collect school information"""
    print_header("🏫 NEW SCHOOL SETUP")
    
    school_info = {}
    
    print(f"\n{YELLOW}Please enter the following information:{RESET}\n")
    
    school_info['name'] = input("School Name (e.g., Miyuga Mixed School): ").strip()
    school_info['schema'] = input("School Schema (e.g., miyuga): ").strip().lower().replace(" ", "_")
    school_info['domain'] = input("Domain (e.g., miyuga.school.ke or miyuga.localhost): ").strip()
    school_info['email'] = input("Admin Email: ").strip()
    school_info['phone'] = input("School Phone (e.g., +254700000000): ").strip()
    school_info['address'] = input("School Address: ").strip()
    school_info['motto'] = input("School Motto (optional): ").strip() or "Excellence in Education"
    
    # Admin user
    print(f"\n{YELLOW}Admin Login Credentials:{RESET}")
    school_info['admin_username'] = input("Admin Username (default: admin): ").strip() or "admin"
    school_info['admin_password'] = input("Admin Password (leave empty for auto-generate): ").strip()
    
    if not school_info['admin_password']:
        school_info['admin_password'] = secrets.token_urlsafe(8)
        print(f"{GREEN}Auto-generated password: {school_info['admin_password']}{RESET}")
    
    return school_info

def create_school_tenant(school_info):
    """Create school tenant in database"""
    print_status("Creating school tenant...")
    
    script = f"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
django.setup()

from tenants.models import School, Domain
from django.contrib.auth import get_user_model
from digitallibrary.models import UserProfile, Class, Subject

User = get_user_model()

# Create school tenant
school, created = School.objects.get_or_create(
    schema_name='{school_info['schema']}',
    defaults={{
        'name': '{school_info['name']}',
        'email': '{school_info['email']}',
        'phone': '{school_info['phone']}',
        'address': '{school_info['address']}',
        'motto': '{school_info['motto']}',
        'paid_until': '2026-12-31',
        'on_trial': False
    }}
)

if created:
    print(f"School created: {{school.name}}")
    
    # Add domain
    domain, _ = Domain.objects.get_or_create(
        domain='{school_info['domain']}',
        tenant=school,
        is_primary=True
    )
    print(f"Domain added: {{domain.domain}}")
    
    # Switch to school schema
    from django_tenants.utils import schema_context
    with schema_context(school.schema_name):
        # Create admin user
        admin = User.objects.create_superuser(
            username='{school_info['admin_username']}',
            email='{school_info['email']}',
            password='{school_info['admin_password']}'
        )
        
        # Create user profile
        UserProfile.objects.create(
            user=admin,
            role='admin',
            is_approved=True,
            phone_number='{school_info['phone']}'
        )
        
        # Create default classes
        default_classes = ['Form 1', 'Form 2', 'Form 3', 'Form 4', 'Grade 7', 'Grade 8', 'Grade 9']
        for class_name in default_classes:
            Class.objects.get_or_create(name=class_name, is_active=True)
        
        # Create default subjects
        default_subjects = [
            'Mathematics', 'English', 'Kiswahili', 'Biology', 'Chemistry', 
            'Physics', 'History', 'Geography', 'CRE', 'Computer Studies'
        ]
        for subject_name in default_subjects:
            Subject.objects.get_or_create(name=subject_name, is_active=True)
        
        print("Default classes and subjects created")
        
else:
    print(f"School already exists: {{school.name}}")
"""
    
    # Save and run script
    script_path = Path(__file__).parent / "schoollibrary" / "create_tenant.py"
    with open(script_path, 'w') as f:
        f.write(script)
    
    os.chdir(Path(__file__).parent / "schoollibrary")
    success, stdout, stderr = run_command(f'python create_tenant.py')
    os.chdir(Path(__file__).parent)
    
    if success:
        print_status(f"School '{school_info['name']}' created successfully", "success")
        return True
    else:
        print_status(f"Error: {stderr}", "error")
        return False

def run_migrations_for_school(schema_name):
    """Run migrations for the new school"""
    print_status(f"Running migrations for {schema_name}...")
    
    os.chdir(Path(__file__).parent / "schoollibrary")
    success, stdout, stderr = run_command(f'python manage.py migrate_schemas --tenant')
    os.chdir(Path(__file__).parent)
    
    if success:
        print_status("Migrations completed", "success")
        return True
    else:
        print_status(f"Migration warning: {stderr}", "warning")
        return True  # Non-critical

def generate_access_urls(school_info):
    """Generate access URLs for the school"""
    print_header("🌐 SCHOOL ACCESS URLs")
    
    print(f"\n{GREEN}School Portal Access:{RESET}")
    print(f"  🌐 Web: http://{school_info['domain']}:8000")
    print(f"  📱 Mobile: http://{school_info['domain']}:8000 (same URL)")
    print(f"  🔐 Admin: http://{school_info['domain']}:8000/admin")
    print(f"  📚 Library: http://{school_info['domain']}:8000/app/library/")
    print(f"  📝 Exams: http://{school_info['domain']}:8000/app/exams/")
    print(f"  💰 Fees: http://{school_info['domain']}:8000/app/fees/")
    print(f"  📱 SMS: http://{school_info['domain']}:8000/app/sms/")
    
    print(f"\n{GREEN}Admin Credentials:{RESET}")
    print(f"  👤 Username: {school_info['admin_username']}")
    print(f"  🔑 Password: {school_info['admin_password']}")
    
    return True

def generate_hosts_file():
    """Generate hosts file entries for Windows"""
    print_header("📝 HOSTS FILE CONFIGURATION")
    
    print(f"{YELLOW}For local development, add these lines to your hosts file:{RESET}")
    print(f"\n{CYAN}C:\\Windows\\System32\\drivers\\etc\\hosts{RESET}\n")
    print("127.0.0.1       miyuga.localhost")
    print("127.0.0.1       orero.localhost")
    print("127.0.0.1       oluti.localhost")
    print("127.0.0.1       daraja.localhost")
    print("127.0.0.1       springfield.localhost")
    
    print(f"\n{YELLOW}For production, configure DNS:{RESET}")
    print("  *.schoollibrary.com  →  your-server-ip")
    
    return True

def create_school_start_script(school_info):
    """Create a start script for the school"""
    script_content = f"""@echo off
title {school_info['name']} - School Library System
color 0A

echo ========================================
echo   {school_info['name']}
echo   School Library Management System
echo ========================================
echo.
echo 🌐 Web Access: http://{school_info['domain']}:8000
echo 📱 Mobile: http://{school_info['domain']}:8000
echo 🔑 Login: {school_info['admin_username']} / {school_info['admin_password']}
echo.
echo Press any key to open the portal...
pause > nul

start http://{school_info['domain']}:8000
"""
    
    script_path = Path(__file__).parent / f"start_{school_info['schema']}.bat"
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    print_status(f"Start script created: start_{school_info['schema']}.bat", "success")
    return True

def main():
    print_header("🏫 SCHOOL LIBRARY SYSTEM - SCHOOL INSTALLER")
    
    # Get school information
    school_info = get_school_info()
    
    print("\n" + "="*60)
    print(f"{YELLOW}Review Information:{RESET}")
    print(f"  School: {school_info['name']}")
    print(f"  Schema: {school_info['schema']}")
    print(f"  Domain: {school_info['domain']}")
    print(f"  Admin: {school_info['admin_username']}")
    print("="*60)
    
    confirm = input(f"\n{YELLOW}Proceed with installation? (y/N): {RESET}").strip().lower()
    if confirm != 'y':
        print_status("Installation cancelled", "warning")
        sys.exit(0)
    
    # Steps
    steps = [
        ("Creating school tenant", lambda: create_school_tenant(school_info)),
        ("Running migrations", lambda: run_migrations_for_school(school_info['schema'])),
        ("Creating start script", lambda: create_school_start_script(school_info)),
    ]
    
    for step_name, step_func in steps:
        print(f"\n{BLUE}▶ {step_name}{RESET}")
        if not step_func():
            print_status(f"Failed at: {step_name}", "error")
            sys.exit(1)
    
    # Show results
    generate_access_urls(school_info)
    generate_hosts_file()
    
    print_header("✅ INSTALLATION COMPLETE!")
    print(f"""
    {GREEN}School '{school_info['name']}' has been successfully installed!{RESET}
    
    Access URLs:
    {CYAN}Web Portal:{RESET}     http://{school_info['domain']}:8000
    {CYAN}Admin Panel:{RESET}    http://{school_info['domain']}:8000/admin
    {CYAN}Library:{RESET}        http://{school_info['domain']}:8000/app/library/
    {CYAN}Exams:{RESET}          http://{school_info['domain']}:8000/app/exams/
    {CYAN}Fees:{RESET}           http://{school_info['domain']}:8000/app/fees/
    {CYAN}SMS:{RESET}            http://{school_info['domain']}:8000/app/sms/
    
    {YELLOW}Login Credentials:{RESET}
    Username: {school_info['admin_username']}
    Password: {school_info['admin_password']}
    
    {YELLOW}Next Steps:{RESET}
    1. Login to the admin panel
    2. Create fee structures for each class
    3. Add more teachers and students
    4. Start entering exam results
    
    {GREEN}To start the server (if not already running):{RESET}
    cd E:\\schoollibrary\\schoollibrary
    ..\\venv\\Scripts\\activate
    waitress-serve --port=8000 --threads=8 schoollibrary.wsgi:application
    """)

if __name__ == "__main__":
    main()