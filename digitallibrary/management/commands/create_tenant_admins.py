# management/commands/create_tenant_admins.py
from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context
from tenants.models import School
from django.contrib.auth import get_user_model
import sys

class Command(BaseCommand):
    help = 'Create admin superusers for all tenants with simple passwords'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            help='Password for all superusers (default: [schoolname]admin123)'
        )
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Username for superusers (default: admin)'
        )
        parser.add_argument(
            '--tenant',
            type=str,
            help='Specific tenant schema to create superuser for (optional)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force creation even if superuser exists (will overwrite password)'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all tenants and exit'
        )
    
    def handle(self, *args, **options):
        # If list option is used, just show tenants
        if options['list']:
            self.list_tenants()
            return
        
        username = options['username']
        custom_password = options.get('password')
        specific_tenant = options.get('tenant')
        force = options['force']
        
        User = get_user_model()
        
        # Get schools to process
        if specific_tenant:
            schools = School.objects.filter(schema_name=specific_tenant)
            if not schools.exists():
                self.stdout.write(self.style.ERROR(f"❌ Tenant with schema '{specific_tenant}' not found"))
                self.list_tenants()
                return
        else:
            schools = School.objects.all()
        
        if not schools.exists():
            self.stdout.write(self.style.ERROR("❌ No tenants found in the database"))
            return
        
        # Confirm with user
        self.stdout.write(self.style.WARNING("\n⚠️  WARNING: This will create admin accounts with simple passwords!"))
        self.stdout.write(self.style.WARNING("   Make sure to change these passwords in production.\n"))
        
        if not specific_tenant:
            self.stdout.write(f"Found {schools.count()} tenants to process:")
            for school in schools:
                self.stdout.write(f"  • {school.name} (schema: {school.schema_name})")
        
        confirm = input("\nContinue? (yes/no): ")
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING("Operation cancelled."))
            return
        
        # Statistics
        stats = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'failed': 0
        }
        
        self.stdout.write("\n" + "=" * 60)
        
        for school in schools:
            self.stdout.write(f"\n📚 Processing: {school.name}")
            self.stdout.write(f"   Schema: {school.schema_name}")
            
            # Generate password for this school
            if custom_password:
                password = custom_password
            else:
                # Create simple password like "olutiadmin123" from schema name
                school_code = school.schema_name.replace('_', '').replace('-', '').lower()
                password = f"{school_code}admin123"
            
            # Generate email
            email = f"admin@{school.schema_name}.edu"
            
            with tenant_context(school):
                try:
                    # Check if user already exists
                    existing_user = User.objects.filter(username=username).first()
                    
                    if existing_user:
                        if force:
                            # Update existing user's password
                            existing_user.set_password(password)
                            existing_user.is_superuser = True
                            existing_user.is_staff = True
                            existing_user.save()
                            self.stdout.write(self.style.SUCCESS(f"   ✅ Updated: {username} (password reset to: {password})"))
                            stats['updated'] += 1
                        else:
                            self.stdout.write(self.style.WARNING(f"   ⏭️ Skipped: User '{username}' already exists (use --force to reset password)"))
                            stats['skipped'] += 1
                    else:
                        # Create new superuser
                        User.objects.create_superuser(
                            username=username,
                            email=email,
                            password=password
                        )
                        self.stdout.write(self.style.SUCCESS(f"   ✅ Created: {username} / {password}"))
                        stats['created'] += 1
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ Failed: {str(e)}"))
                    stats['failed'] += 1
        
        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("📊 SUMMARY:"))
        self.stdout.write(f"   ✅ Created: {stats['created']} new admin accounts")
        self.stdout.write(f"   🔄 Updated: {stats['updated']} existing accounts")
        self.stdout.write(f"   ⏭️ Skipped: {stats['skipped']} accounts")
        if stats['failed'] > 0:
            self.stdout.write(self.style.ERROR(f"   ❌ Failed: {stats['failed']} accounts"))
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("\n🎉 Admin accounts created successfully!"))
        self.stdout.write("\nAccess each school at:")
        for school in schools:
            # Try to find domain for this school
            try:
                domain = school.domains.first()
                if domain:
                    url = f"http://{domain.domain}:8000/admin"
                else:
                    url = f"http://{school.schema_name}.localhost:8000/admin"
            except:
                url = f"http://{school.schema_name}.localhost:8000/admin"
            
            self.stdout.write(f"   • {school.name}: {url}")
    
    def list_tenants(self):
        """List all available tenants"""
        schools = School.objects.all()
        
        self.stdout.write("\n📋 Available Tenants:")
        self.stdout.write("=" * 50)
        
        if not schools.exists():
            self.stdout.write(self.style.WARNING("No tenants found."))
            return
        
        for school in schools:
            # Get domain info
            try:
                domain = school.domains.first()
                domain_str = domain.domain if domain else "No domain set"
            except:
                domain_str = "No domain set"
            
            self.stdout.write(f"\n🏫 {school.name}")
            self.stdout.write(f"   Schema: {school.schema_name}")
            self.stdout.write(f"   Domain: {domain_str}")
            
            # Check if admin exists
            with tenant_context(school):
                User = get_user_model()
                admin_exists = User.objects.filter(is_superuser=True).exists()
                if admin_exists:
                    admins = User.objects.filter(is_superuser=True)
                    self.stdout.write(f"   👤 Admins: {', '.join([a.username for a in admins])}")
                else:
                    self.stdout.write(self.style.Warning("   ⚠️ No admin user found"))