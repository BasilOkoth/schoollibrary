import re as _re
import logging

logger = logging.getLogger(__name__)


def school_settings(request):
    from django.db import connection
    schema_name = 'public'
    if hasattr(request, 'tenant') and request.tenant:
        schema_name = request.tenant.schema_name

    host = request.get_host().split(':')[0].lower()
    is_public_domain = host in ['shulehub.org', 'www.shulehub.org', 'schoollibrary.onrender.com']

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

    if schema_name != 'public' and not is_public_domain:
        try:
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
                    'public_warning': None,
                })
            else:
                context.update({
                    'school_name': request.tenant.name if hasattr(request.tenant, 'name') else schema_name.title(),
                    'is_public_schema': False,
                    'is_tenant_schema': True,
                    'current_schema': schema_name,
                    'public_warning': None,
                })
        except Exception as e:
            logger.warning(f"Tenant context error: {e}")
            context.update({
                'is_tenant_schema': True,
                'is_public_schema': False,
                'current_schema': schema_name,
            })

    return context


def tenant_context(request):
    host = request.get_host().split(':')[0].lower()
    is_public_domain = host in ['shulehub.org', 'www.shulehub.org', 'schoollibrary.onrender.com']

    schema_name = 'public'
    if hasattr(request, 'tenant') and request.tenant:
        schema_name = request.tenant.schema_name

    is_public = (schema_name == 'public' or is_public_domain)

    m = _re.match(r'^(/tenant/[^/]+/app)', request.path)
    app_prefix = m.group(1) if m else '/app'

    return {
        'is_public_schema': is_public,
        'is_tenant_schema': not is_public,
        'current_host': host,
        'current_schema': schema_name,
        'app_prefix': app_prefix,
    }
