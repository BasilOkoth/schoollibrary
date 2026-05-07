#!/bin/bash
# render_build.sh

echo "🚀 Starting Render build process..."

# Install dependencies
pip install -r requirements.txt

# Run shared migrations
echo "Running shared migrations..."
python manage.py migrate_schemas --shared

# Run tenant migrations
echo "Running tenant migrations..."
python manage.py migrate_schemas --tenant

# Create default tenant (only if no tenants exist)
echo "Creating default tenant..."
python manage.py shell << EOF
from tenants.models import School, Domain
import os

if School.objects.count() == 0:
    print("No tenants found. Creating default tenant...")
    
    school = School.objects.create(
        name='Default School',
        schema_name='default',
        paid_until='2026-12-31',
        on_trial=True,
        created_on='2024-01-01',
        is_active=True
    )
    
    # Get domain from environment
    domain = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')
    domain = domain.replace('https://', '').replace('http://', '')
    
    Domain.objects.create(
        tenant=school,
        domain=domain,
        is_primary=True
    )
    
    print(f"✅ Default tenant created: {school.name} (schema: {school.schema_name})")
else:
    print(f"Found {School.objects.count()} existing tenant(s)")
EOF

# Create superuser
echo "Creating default admin user..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('✅ Default admin created: admin / admin123')
" || true

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Build completed successfully!"