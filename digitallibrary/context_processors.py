# digitallibrary/context_processors.py

from django.db import connection
import logging

logger = logging.getLogger(__name__)

def school_settings(request):
    """
    Provides school settings to all templates with tenant/public schema awareness.
    """
    # 1. Detect schema name reliably
    schema_name = 'public'
    if hasattr(request, 'tenant') and request.tenant:
        schema_name = request.tenant.schema_name
    
    # 2. Hardcoded check for shulehub.org (your public domain)
    host = request.get_host().split(':')[0].lower()
    is_public_domain = host in ['shulehub.org', 'www.shulehub.org', 'schoollibrary.onrender.com']
    
    # 3. Define the base context
    context = {
        'school': None,
        'school_name': 'ShuleHub',
        'school_logo': None,
        'school_motto': 'Digital Library Platform for Kenyan Schools',
        'is_public_schema': True,
        'is_tenant_schema': False,
        'current_schema': 'public',
        'public_warning': "You are on ShuleHub public portal. Use a school subdomain to access the school portal."
    }

    # 4. If we are NOT in the public schema, try to fetch real school settings
    if schema_name != 'public' and not is_public_domain:
        try:
            # We import models inside the function to avoid circular imports
            # and only when we are sure we are in a tenant schema.
            from .models import SchoolSetting
            
            school = SchoolSetting.objects.first()
            if school:
                context.update({
                    'school': school,
                    'school_name': school.name or 'School System',
                    'school_logo': school.logo.url if school.logo else None,
                    'school_motto': school.motto or '',
                    'is_public_schema': False,
                    'is_tenant_schema': True,
                    'current_schema': schema_name,
                    'public_warning': None
                })
            else:
                # Fallback if tenant exists but settings aren't configured
                context.update({
                    'school_name': request.tenant.name if hasattr(request.tenant, 'name') else schema_name.title(),
                    'is_public_schema': False,
                    'is_tenant_schema': True,
                    'current_schema': schema_name,
                    'public_warning': None
                })
        except Exception as e:
            # If the table doesn't exist yet or any other DB error, 
            # we keep the default public context but mark it as tenant.
            logger.warning(f"Tenant context error: {e}")
            context['is_tenant_schema'] = True
            context['is_public_schema'] = False
            context['current_schema'] = schema_name

    return context

def tenant_context(request):
    """
    Makes basic tenant information available to all templates.
    """
    host = request.get_host().split(':')[0].lower()
    is_public_domain = host in ['shulehub.org', 'www.shulehub.org', 'schoollibrary.onrender.com']
    
    schema_name = 'public'
    if hasattr(request, 'tenant') and request.tenant:
        schema_name = request.tenant.schema_name

    is_public = (schema_name == 'public' or is_public_domain)

    return {
        'is_public_schema': is_public,
        'is_tenant_schema': not is_public,
        'current_host': host,
        'current_schema': schema_name,
    }
