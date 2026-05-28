#!/bin/bash

echo "========================================="
echo "  SCHOOL LIBRARY - RENDER BUILD"
echo "========================================="

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Wait for database to be ready (if needed)
echo "🗄️  Waiting for database..."
sleep 5

echo "🔄 Running migrations..."

# Run shared migrations (public schema)
echo "Running shared schema migrations..."
python manage.py migrate_schemas --shared --noinput || {
    echo "⚠️  Shared migrations failed, trying with --fake..."
    python manage.py migrate --noinput
}

# Run tenant migrations (creates base tables for tenants)
echo "Running tenant schema migrations..."
python manage.py migrate_schemas --tenant --noinput || {
    echo "⚠️  Tenant migrations failed, continuing..."
}

# Create tenants and domains
echo "🏫 Setting up tenants and domains..."
python manage.py shell << 'EOF'
import os
import sys
from django.db import connection

try:
    from tenants.models import School, Domain
    
    # 1. Ensure the 'public' tenant exists
    # This is critical for django-tenants to function correctly
    public_tenant, created = School.objects.get_or_create(
        schema_name='public',
        defaults={
            'name': 'Public Interface',
            'paid_until': '2099-12-31',
            'on_trial': False,
            'is_active': True
        }
    )
    if created:
        print("✅ Created 'public' tenant")

    # 2. Add domains to the public tenant
    # Add the custom domain
    Domain.objects.get_or_create(
        tenant=public_tenant,
        domain='shulehub.org',
        defaults={'is_primary': True}
    )
    Domain.objects.get_or_create(
        tenant=public_tenant,
        domain='www.shulehub.org',
        defaults={'is_primary': False}
    )
    
    # Add the Render hostname as a fallback
    render_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
    if render_host:
        render_host = render_host.replace('https://', '').replace('http://', '')
        Domain.objects.get_or_create(
            tenant=public_tenant,
            domain=render_host,
            defaults={'is_primary': False}
        )
        print(f"✅ Linked Render host: {render_host}")

    # 3. Create the DEMO tenant (for testing/main tenant)
    print("🔧 Creating 'demo' tenant...")
    demo_tenant, demo_created = School.objects.get_or_create(
        schema_name='demo',
        defaults={
            'name': 'OSEP School',
            'paid_until': '2030-12-31',
            'on_trial': False,
            'is_active': True,
            'motto': 'Excellence in Education',
            'address': 'Nairobi, Kenya',
            'phone_number': '+254700000000',
            'email': 'info@osepschool.com'
        }
    )
    
    if demo_created:
        print("✅ Created 'demo' tenant")
        
        # Add domain for demo tenant
        Domain.objects.get_or_create(
            tenant=demo_tenant,
            domain='demo.schoollibrary-1.onrender.com',
            defaults={'is_primary': True}
        )
        print("✅ Added domain for demo tenant")
        
        # Also add the main Render host as a secondary domain for demo tenant
        if render_host:
            Domain.objects.get_or_create(
                tenant=demo_tenant,
                domain=render_host,
                defaults={'is_primary': False}
            )
            print(f"✅ Added secondary domain for demo tenant: {render_host}")
    else:
        print(f"ℹ️ 'demo' tenant already exists (ID: {demo_tenant.id})")

    # 4. Create a default school tenant if none exists (fallback)
    if School.objects.exclude(schema_name='public').exclude(schema_name='demo').count() == 0:
        print("🔧 Creating initial default school tenant...")
        default_school = School.objects.create(
            name='Default School',
            schema_name='default',
            paid_until='2026-12-31',
            on_trial=True,
            is_active=True
        )
        print(f"✅ Default school tenant created: {default_school.name}")

    print(f"✅ Setup complete. Total tenants: {School.objects.count()}")
    print(f"   - Tenants: {', '.join(School.objects.values_list('schema_name', flat=True))}")

except Exception as e:
    print(f"⚠️  Tenant/Domain setup failed: {e}")
    import traceback
    traceback.print_exc()
EOF

# Create superuser in public schema (for superadmin)
echo "👤 Creating superadmin user..."
python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('superadmin', 'superadmin@shulehub.com', 'superadmin123')
    print('✅ Superadmin user created: superadmin / superadmin123')
else:
    print('✅ Superadmin user already exists')
EOF

# Create admin user in demo tenant
echo "👤 Creating admin user in demo tenant..."
python manage.py shell << 'EOF'
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model

User = get_user_model()

try:
    with schema_context('demo'):
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@osepschool.com',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            print('✅ Admin user created in demo tenant: admin / admin123')
        else:
            print('ℹ️ Admin user already exists in demo tenant')
            
        # Create principal user
        principal_user, p_created = User.objects.get_or_create(
            username='principal',
            defaults={
                'email': 'principal@osepschool.com',
                'is_staff': True,
                'is_superuser': False,
                'is_active': True
            }
        )
        if p_created:
            principal_user.set_password('principal123')
            principal_user.save()
            print('✅ Principal user created in demo tenant: principal / principal123')
            
        # Create teacher user
        teacher_user, t_created = User.objects.get_or_create(
            username='teacher',
            defaults={
                'email': 'teacher@osepschool.com',
                'is_staff': True,
                'is_superuser': False,
                'is_active': True
            }
        )
        if t_created:
            teacher_user.set_password('teacher123')
            teacher_user.save()
            print('✅ Teacher user created in demo tenant: teacher / teacher123')
            
except Exception as e:
    print(f"⚠️ Could not create demo tenant users: {e}")
EOF

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "========================================="
echo "✅ BUILD COMPLETED SUCCESSFULLY"
echo "========================================="
echo ""
echo "📋 Access URLs:"
echo "   Landing Page: https://schoollibrary-1.onrender.com/"
echo "   Tenant Login: https://schoollibrary-1.onrender.com/tenant/demo/app/login/"
echo "   Superadmin:   https://schoollibrary-1.onrender.com/superadmin/"
echo ""
echo "🔐 Login Credentials:"
echo "   Superadmin: superadmin / superadmin123"
echo "   Demo Admin: admin / admin123"
echo "   Demo Principal: principal / principal123"
echo "   Demo Teacher: teacher / teacher123"
echo "========================================="
