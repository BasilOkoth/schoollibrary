# digitallibrary/context_processors.py

from django.db import connection
import logging

logger = logging.getLogger(__name__)

def school_settings(request):
    """
    Provides school settings to all templates with tenant/public schema awareness.
    """
    # Default context
    context = {
        'school': None,
        'school_name': 'ShuleHub',
        'school_logo': None,
        'school_motto': 'Digital Library Platform for Kenyan Schools',
        'is_public_schema': True,
        'is_tenant_schema': False,
        'current_schema': 'public',
    }

    # Check if we have a tenant
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
        schema_name = tenant.schema_name
        
        context['current_schema'] = schema_name
        
        # Public schema
        if schema_name == 'public':
            context['is_public_schema'] = True
            context['is_tenant_schema'] = False
            context['school_name'] = 'ShuleHub'
            return context
        
        # Tenant schema
        context['is_public_schema'] = False
        context['is_tenant_schema'] = True
        
        # Try to get SchoolSetting from database
        try:
            from .models import SchoolSetting
            school = SchoolSetting.objects.first()
            
            if school:
                context['school'] = school
                context['school_name'] = school.name
                context['school_motto'] = school.motto or ''
                context['school_logo'] = school.logo.url if school.logo else None
                logger.info(f"Loaded school setting: {school.name} for schema {schema_name}")
            else:
                # No SchoolSetting record, use tenant name
                context['school_name'] = tenant.name if hasattr(tenant, 'name') else schema_name.title()
                context['school_motto'] = f'Welcome to {context["school_name"]}'
                # Create a dummy school object for template compatibility
                context['school'] = type('obj', (object,), {
                    'name': context['school_name'],
                    'motto': context['school_motto'],
                    'logo': None
                })()
                logger.warning(f"No SchoolSetting found for {schema_name}, using tenant name")
                
        except Exception as e:
            logger.error(f"Error loading school settings for {schema_name}: {e}")
            context['school_name'] = tenant.name if hasattr(tenant, 'name') else schema_name.title()
            context['school'] = type('obj', (object,), {
                'name': context['school_name'],
                'motto': '',
                'logo': None
            })()
    
    return context


def tenant_context(request):
    """
    Makes basic tenant information available to all templates.
    """
    host = request.get_host().split(':')[0].lower()
    
    schema_name = 'public'
    if hasattr(request, 'tenant') and request.tenant:
        schema_name = request.tenant.schema_name

    is_public = (schema_name == 'public')

    return {
        'is_public_schema': is_public,
        'is_tenant_schema': not is_public,
        'current_host': host,
        'current_schema': schema_name,
    }