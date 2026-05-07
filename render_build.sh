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

# Create default tenant if none exists
echo "🏫 Creating default tenant..."
python manage.py shell << 'EOF'
import os
import sys
from django.db import connection

try:
    from tenants.models import School, Domain
    
    # Check if tables exist
    with connection.cursor() as cursor:
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='tenants_school');")
        tables_exist = cursor.fetchone()[0]
    
    if not tables_exist:
        print("⚠️  Tables not ready yet, skipping tenant creation")
        sys.exit(0)
    
    if School.objects.count() == 0:
        print("🔧 No tenants found. Creating default tenant...")
        
        school = School.objects.create(
            name='Default School',
            schema_name='default',
            paid_until='2026-12-31',
            on_trial=True,
            created_on='2024-01-01',
            is_active=True
        )
        
        domain = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')
        domain = domain.replace('https://', '').replace('http://', '')
        
        Domain.objects.create(
            tenant=school,
            domain=domain,
            is_primary=True
        )
        
        print(f"✅ Default tenant created: {school.name}")
        print(f"   Domain: {domain}")
    else:
        print(f"✅ Found {School.objects.count()} tenant(s)")
except Exception as e:
    print(f"⚠️  Tenant creation skipped: {e}")
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