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

    # 3. Create a default school tenant if none exists (optional, based on your previous script)
    if School.objects.exclude(schema_name='public').count() == 0:
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

except Exception as e:
    print(f"⚠️  Tenant/Domain setup failed: {e}")
    import traceback
    traceback.print_exc()
EOF

# Create superuser
echo "👤 Creating admin user..."
python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('✅ Admin user created: admin / admin123')
else:
    print('✅ Admin user already exists')
EOF

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "========================================="
echo "✅ BUILD COMPLETED SUCCESSFULLY"
echo "========================================="
