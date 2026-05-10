# digitallibrary/context_processors.py

from django.db import ProgrammingError
from django.core.exceptions import ImproperlyConfigured
import logging

logger = logging.getLogger(__name__)

def school_settings(request):
    """
    Provides school settings to all templates with tenant/public schema awareness.
    Returns different data based on whether we're in public schema or tenant schema.
    """
    context = {
        'school': None,
        'school_name': 'School System',
        'school_logo': None,
        'school_motto': None,
        'is_public_schema': False,
        'is_tenant_schema': False,
        'current_schema': 'public',
    }
    
    try:
        # Check if we're in public schema
        is_public = False
        current_schema = 'public'
        
        if hasattr(request, 'tenant'):
            if request.tenant and request.tenant.schema_name == 'public':
                is_public = True
                current_schema = 'public'
                context['current_schema'] = 'public'
                context['is_public_schema'] = True
            elif request.tenant:
                current_schema = request.tenant.schema_name
                context['current_schema'] = current_schema
                context['is_tenant_schema'] = True
        else:
            # Fallback: check hostname
            host = request.get_host()
            if 'localhost' in host and 'orero' not in host and 'miyuga' not in host:
                is_public = True
                context['is_public_schema'] = True
                context['current_schema'] = 'public'
            else:
                context['is_tenant_schema'] = True
                context['current_schema'] = 'tenant'
        
        # Try to get school settings (only works in tenant schema)
        if not is_public and current_schema != 'public':
            try:
                # Import here to avoid circular imports
                from .models import SchoolSetting
                
                school = SchoolSetting.objects.first()
                if school:
                    context['school'] = school
                    context['school_name'] = school.name or 'School System'
                    context['school_logo'] = school.logo.url if school.logo else None
                    context['school_motto'] = school.motto or ''
                else:
                    # Fallback school name from tenant if available
                    if hasattr(request, 'tenant') and request.tenant and request.tenant.schema_name != 'public':
                        context['school_name'] = request.tenant.name if hasattr(request.tenant, 'name') else request.tenant.schema_name.title()
            except ProgrammingError as e:
                # Table doesn't exist in this schema - expected for new tenants
                logger.warning(f"SchoolSetting table doesn't exist in schema {current_schema}: {e}")
                # Use tenant name as fallback
                if hasattr(request, 'tenant') and request.tenant and request.tenant.schema_name != 'public':
                    context['school_name'] = request.tenant.name if hasattr(request.tenant, 'name') else request.tenant.schema_name.title()
            except Exception as e:
                logger.error(f"Error querying SchoolSetting: {e}")
        else:
            # Public schema - show admin title
            context['school_name'] = 'School Library Admin Portal'
            context['school_motto'] = 'Administration Dashboard'
            
    except Exception as e:
        # Log error but don't crash
        logger.error(f"Error in school_settings context processor: {e}")
        context['school_name'] = 'School System'
        context['school_motto'] = ''
    
    # Add a helpful message for public schema
    if context['is_public_schema']:
        context['public_warning'] = "You are in Admin mode. Use orero.localhost to access the school portal."
    else:
        context['public_warning'] = None
    
    return context


def tenant_context(request):
    """
    Makes tenant information available to all templates.
    This is needed for the templates to know which schema they're in.
    """
    context = {
        'is_public_schema': False,
        'is_tenant_schema': False,
        'current_host': request.get_host(),
    }
    
    try:
        # Check via request.tenant if available
        if hasattr(request, 'tenant') and request.tenant:
            if request.tenant.schema_name == 'public':
                context['is_public_schema'] = True
            else:
                context['is_tenant_schema'] = True
        else:
            # Fallback: check hostname
            host = request.get_host()
            if 'localhost' in host and 'orero' not in host and 'miyuga' not in host:
                context['is_public_schema'] = True
            else:
                context['is_tenant_schema'] = True
    except Exception as e:
        # If anything fails, assume public schema
        logger.warning(f"Error in tenant_context: {e}")
        context['is_public_schema'] = True
        context['is_tenant_schema'] = False
    
    return context
