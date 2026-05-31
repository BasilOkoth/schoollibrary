import re as _re
import logging

logger = logging.getLogger(__name__)


def school_settings(request):
    """
    Context processor to provide school-specific settings to all templates.
    Handles the case where a tenant might not have a SchoolSetting record yet.
    """
    from django.db import connection
    
    # Determine the current schema
    schema_name = 'public'
    if hasattr(request, 'tenant') and request.tenant:
        schema_name = request.tenant.schema_name

    # Check if we are on a public domain
    host = request.get_host().split(':')[0].lower()
    public_domains = [
        'shulehub.org', 
        'www.shulehub.org', 
        'schoollibrary.onrender.com',
        'schoollibrary-1.onrender.com' # Added the -1 variant
    ]
    is_public_domain = host in public_domains

    # Default context (Public Schema / Landing Page)
    context = {
        'school': None,
        'school_name': 'ShuleHub',
        'school_logo': None,
        'school_motto': 'Digital Library Platform for Kenyan Schools',
        'is_public_schema': True,
        'is_tenant_schema': False,
        'current_schema': 'public',
        'public_warning': "You are on ShuleHub public portal.",
    }

    # If we are in a tenant schema and NOT on the main landing page domain
    if schema_name != 'public' and not is_public_domain:
        try:
            from .models import SchoolSetting
            # Get the first (and usually only) setting record for this tenant
            school_setting = SchoolSetting.objects.first()
            
            if school_setting:
                # Use settings from the database
                context.update({
                    'school': school_setting,
                    'school_name': school_setting.name or 'School System',
                    'school_logo': school_setting.logo.url if school_setting.logo else None,
                    'school_motto': school_setting.motto or '',
                    'is_public_schema': False,
                    'is_tenant_schema': True,
                    'current_schema': schema_name,
                    'public_warning': None,
                })
            else:
                # Fallback: Record doesn't exist yet, use tenant name from the School model
                tenant_name = getattr(request.tenant, 'name', schema_name.title())
                context.update({
                    'school': None,
                    'school_name': tenant_name,
                    'school_logo': None,
                    'school_motto': '',
                    'is_public_schema': False,
                    'is_tenant_schema': True,
                    'current_schema': schema_name,
                    'public_warning': "Settings not configured. Please visit the admin panel.",
                })
        except Exception as e:
            logger.warning(f"Tenant context error for schema {schema_name}: {e}")
            context.update({
                'is_tenant_schema': True,
                'is_public_schema': False,
                'current_schema': schema_name,
            })

    return context


def tenant_context(request):
    """
    Simpler context processor for path-based routing helpers.
    """
    host = request.get_host().split(':')[0].lower()
    public_domains = [
        'shulehub.org', 
        'www.shulehub.org', 
        'schoollibrary.onrender.com',
        'schoollibrary-1.onrender.com'
    ]
    is_public_domain = host in public_domains

    schema_name = 'public'
    if hasattr(request, 'tenant') and request.tenant:
        schema_name = request.tenant.schema_name

    # A request is considered "public" if it's in the public schema OR on the landing page domain
    is_public = (schema_name == 'public' or is_public_domain)

    # Extract the tenant prefix for URL building (e.g., /tenant/demo/app)
    m = _re.match(r'^(/tenant/[^/]+/app)', request.path)
    app_prefix = m.group(1) if m else '/app'

    return {
        'is_public_schema': is_public,
        'is_tenant_schema': not is_public,
        'current_host': host,
        'current_schema': schema_name,
        'app_prefix': app_prefix,
    }
