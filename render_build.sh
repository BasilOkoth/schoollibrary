#!/bin/bash
# build.sh - Render build script for django-tenants

echo "========================================="
echo "  SCHOOL LIBRARY SYSTEM - RENDER BUILD"
echo "========================================="

# Install dependencies
echo "📦 Installing Python packages..."
pip install -r requirements.txt

# Run shared schema migrations (public schema)
echo "🔄 Running shared schema migrations..."
python manage.py migrate_schemas --shared

# Run tenant schema migrations (creates base tables for future tenants)
echo "🏫 Running tenant schema migrations..."
python manage.py migrate_schemas --tenant

# Create default superuser if none exists (optional)
echo "👤 Ensuring admin user exists..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Default admin user created: admin / admin123')
else:
    print('Admin user already exists')
" || true

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Build completed successfully!"