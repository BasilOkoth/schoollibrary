# digitallibrary/context_processors.py

from django.db import ProgrammingError, connection
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
        # Check by schema OR by hostname
        host = request.get_host().split(':')[0]
        is_public_by_host = host in ['shulehub.org', 'www.shulehub.org']
        
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
            if is_public_by_host or ('localhost' in host and 'orero' not in host and 'miyuga' not in host):
                is_public = True
                context['is_public_schema'] = True
                context['current_schema'] = 'public'
            else:
                context['is_tenant_schema'] = True
                context['current_schema'] = 'tenant'
        
        # Force public schema for shulehub.org
        if is_public_by_host:
            is_public = True
            context['is_public_schema'] = True
            context['is_tenant_schema'] = False
            context['current_schema'] = 'public'
        
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
            # Public schema - show portal title for shulehub.org
            if is_public_by_host:
                context['school_name'] = 'ShuleHub'
                context['school_motto'] = 'Digital Library Platform for Kenyan Schools'
            else:
                context['school_name'] = 'School Library Admin Portal'
                context['school_motto'] = 'Administration Dashboard'
            
    except Exception as e:
        # Log error but don't crash
        logger.error(f"Error in school_settings context processor: {e}")
        context['school_name'] = 'ShuleHub'
        context['school_motto'] = ''
    
    # Add a helpful message for public schema
    if context['is_public_schema']:
        context['public_warning'] = "You are on ShuleHub public portal. Use a school subdomain to access the school portal."
    else:
        context['public_warning'] = None
    
    return context


def tenant_context(request):
    """
    Makes tenant information available to all templates.
    This is needed for the templates to know which schema they're in.
    """
    host = request.get_host().split(':')[0]
    is_public_by_host = host in ['shulehub.org', 'www.shulehub.org']
    
    context = {
        'is_public_schema': is_public_by_host,
        'is_tenant_schema': not is_public_by_host,
        'current_host': host,
    }
    
    try:
        # Check via request.tenant if available
        if hasattr(request, 'tenant') and request.tenant:
            if request.tenant.schema_name == 'public' or is_public_by_host:
                context['is_public_schema'] = True
                context['is_tenant_schema'] = False
            else:
                context['is_public_schema'] = False
                context['is_tenant_schema'] = True
        else:
            # Fallback: use hostname detection
            context['is_public_schema'] = is_public_by_host
            context['is_tenant_schema'] = not is_public_by_host
            
    except Exception as e:
        # If anything fails, check by hostname
        logger.warning(f"Error in tenant_context: {e}")
        context['is_public_schema'] = is_public_by_host
        context['is_tenant_schema'] = not is_public_by_host
    
    return context