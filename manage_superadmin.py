# manage_superadmin.py
#!/usr/bin/env python

import os
import sys
import django

def setup_superadmin():
    """Interactive script to set up super admin account"""
    
    # Setup Django environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoollibrary.settings')
    django.setup()
    
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django_tenants.utils import schema_context
    
    User = get_user_model()
    
    print("\n" + "="*60)
    print("🔐 SHULEHUB SUPER ADMIN SETUP")
    print("="*60)
    
    # Check if any superuser exists
    with schema_context('public'):
        existing_superusers = User.objects.filter(is_superuser=True)
        
        if existing_superusers.exists():
            print("\n⚠️ Existing superusers found:\n")
            for user in existing_superusers:
                print(f"   • {user.username} ({user.email}) - Last login: {user.last_login or 'Never'}")
            
            print("\nOptions:")
            print("1. Create additional superuser")
            print("2. Reset existing superuser password")
            print("3. Delete existing superuser and create new")
            print("4. Exit")
            
            choice = input("\nEnter choice (1-4): ").strip()
            
            if choice == '4':
                print("\nExiting...")
                return
            elif choice == '2':
                reset_superuser_password(existing_superusers.first())
                return
            elif choice == '3':
                for user in existing_superusers:
                    user.delete()
                    print(f"✓ Deleted user: {user.username}")
        
        # Create new superuser
        create_new_superuser()


def create_new_superuser():
    """Create a new superuser interactively"""
    from django.contrib.auth import get_user_model
    from django_tenants.utils import schema_context
    import re
    
    User = get_user_model()
    
    print("\n📝 Create Super Admin Account")
    print("-" * 40)
    
    # Get username
    while True:
        username = input("Username (required): ").strip()
        if username:
            if not re.match(r'^[\w.@+-]+$', username):
                print("❌ Username contains invalid characters. Use letters, numbers, and @/./+/-/_ only.")
                continue
            with schema_context('public'):
                if User.objects.filter(username=username).exists():
                    print(f"❌ Username '{username}' already exists. Choose another.")
                    continue
            break
        else:
            print("❌ Username is required")
    
    # Get email
    email = input("Email (optional): ").strip()
    
    # Get password
    while True:
        password = input("Password (min 8 characters): ").strip()
        if len(password) < 8:
            print("❌ Password must be at least 8 characters")
            continue
        password2 = input("Confirm password: ").strip()
        if password != password2:
            print("❌ Passwords don't match")
            continue
        break
    
    # Get first name
    first_name = input("First Name (optional): ").strip()
    
    # Get last name
    last_name = input("Last Name (optional): ").strip()
    
    # Get phone number (optional)
    phone = input("Phone Number (optional): ").strip()
    
    print("\n" + "-" * 40)
    print("\n📋 Super Admin Details:")
    print(f"   Username: {username}")
    print(f"   Email: {email or 'Not provided'}")
    print(f"   Name: {first_name} {last_name}".strip())
    print(f"   Phone: {phone or 'Not provided'}")
    print("\n⚠️ Keep these credentials safe!")
    
    confirm = input("\nCreate super admin? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        with schema_context('public'):
            # Create superuser
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Create super admin profile
            try:
                from tenants.models import SuperAdminProfile
                SuperAdminProfile.objects.create(
                    user=user,
                    is_super_admin=True,
                    can_manage_all_tenants=True,
                    can_view_all_data=True
                )
                print("✓ Super admin profile created")
            except ImportError:
                # Profile model might not exist yet
                pass
            
            # Set additional permissions
            user.is_staff = True
            user.is_active = True
            user.save()
            
            print(f"\n✅ SUPER ADMIN CREATED SUCCESSFULLY!")
            print(f"\n🔐 Login credentials:")
            print(f"   Username: {username}")
            print(f"   Password: {password}")
            print(f"\n🌐 Login URL: http://localhost:8000/login/")
    else:
        print("\n❌ Super admin creation cancelled")


def reset_superuser_password(user):
    """Reset superuser password"""
    from django.contrib.auth import get_user_model
    
    print(f"\n🔐 Resetting password for: {user.username}")
    print("-" * 40)
    
    while True:
        new_password = input("New password (min 8 characters): ").strip()
        if len(new_password) < 8:
            print("❌ Password must be at least 8 characters")
            continue
        confirm_password = input("Confirm password: ").strip()
        if new_password != confirm_password:
            print("❌ Passwords don't match")
            continue
        break
    
    user.set_password(new_password)
    user.save()
    
    print(f"\n✅ Password reset successful for {user.username}")
    print(f"   New password: {new_password}")


def list_superusers():
    """List all superusers"""
    from django.contrib.auth import get_user_model
    from django_tenants.utils import schema_context
    
    User = get_user_model()
    
    with schema_context('public'):
        superusers = User.objects.filter(is_superuser=True)
        
        if superusers.exists():
            print("\n👑 Super Admin Users:")
            print("-" * 40)
            for user in superusers:
                print(f"   • {user.username} - {user.email or 'No email'}")
                print(f"     Role: {'Super Admin' if user.is_superuser else 'Admin'}")
                print(f"     Last login: {user.last_login or 'Never'}")
                print()
        else:
            print("\n❌ No super admin users found")


if __name__ == '__main__':
    setup_superadmin()