# digitallibrary/context_processors.py

import re as _re
import logging
from django_tenants.utils import get_tenant

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
    elif hasattr(request, 'session'):
        # Try to get from session as fallback
        schema_name = request.session.get('tenant_schema', 'public')

    # Check if we are on a public domain
    host = request.get_host().split(':')[0].lower()
    public_domains = [
        'shulehub.org', 
        'www.shulehub.org', 
        'schoollibrary.onrender.com',
        'schoollibrary-1.onrender.com',
        'localhost',
        '127.0.0.1'
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
    Enhanced context processor for path-based routing helpers.
    Provides all tenant-aware URLs and variables for templates.
    """
    host = request.get_host().split(':')[0].lower()
    public_domains = [
        'shulehub.org', 
        'www.shulehub.org', 
        'schoollibrary.onrender.com',
        'schoollibrary-1.onrender.com',
        'localhost',
        '127.0.0.1'
    ]
    is_public_domain = host in public_domains

    # Get tenant schema
    schema_name = 'public'
    tenant = None
    
    if hasattr(request, 'tenant') and request.tenant:
        tenant = request.tenant
        schema_name = tenant.schema_name
    elif hasattr(request, 'session'):
        # Try to get from session as fallback
        schema_name = request.session.get('tenant_schema', 'public')
        if schema_name != 'public':
            try:
                from tenants.models import School
                tenant = School.objects.get(schema_name=schema_name)
            except:
                pass

    # A request is considered "public" if it's in the public schema OR on the landing page domain
    is_public = (schema_name == 'public' or is_public_domain)

    # Extract the tenant prefix for URL building
    tenant_prefix = ''
    m = _re.match(r'^/tenant/([^/]+)/', request.path)
    if m:
        tenant_prefix = m.group(1)
    elif schema_name != 'public' and not is_public:
        tenant_prefix = schema_name
    
    # Build tenant-aware URLs
    if tenant_prefix:
        base_url = f'/tenant/{tenant_prefix}/app'
        
        # Dashboard URLs
        dashboard_url = f'/tenant/{tenant_prefix}/app/dashboard/'
        home_url = f'/tenant/{tenant_prefix}/app/'
        
        # Auth URLs
        login_url = f'/tenant/{tenant_prefix}/app/login/'
        logout_url = f'/tenant/{tenant_prefix}/app/logout/'
        
        # Fees Module URLs
        fees_base = f'/tenant/{tenant_prefix}/app/fees'
        fees_dashboard_url = f'{fees_base}/dashboard/'
        fees_defaulters_url = f'{fees_base}/defaulters/'
        fees_payment_url = f'{fees_base}/payment/record/'
        fees_structure_url = f'{fees_base}/structure/'
        fees_collection_url = f'{fees_base}/collection-report/'
        fees_students_url = f'{fees_base}/students/'
        
        # TV Module URLs
        tv_base = f'/tenant/{tenant_prefix}/app/tv'
        tv_display_url = f'{tv_base}/'
        tv_dashboard_url = f'{tv_base}/dashboard/'
        tv_content_add_url = f'{tv_base}/content/add/'
        tv_settings_url = f'{tv_base}/settings/'
        
        # Library URLs
        library_url = f'/tenant/{tenant_prefix}/app/library/'
        upload_url = f'/tenant/{tenant_prefix}/app/upload/'
        
        # Performance/Results URLs
        performance_url = f'/tenant/{tenant_prefix}/app/performance/'
        results_url = f'/tenant/{tenant_prefix}/app/results/'
        exams_url = f'/tenant/{tenant_prefix}/app/exams/'
        
        # SMS URLs
        sms_url = f'/tenant/{tenant_prefix}/app/sms/'
        
        # Feedback URLs
        feedback_url = f'/tenant/{tenant_prefix}/app/feedback/'
        
        # Parent Portal URLs
        parent_url = f'/tenant/{tenant_prefix}/app/parent/'
        parent_login_url = f'/tenant/{tenant_prefix}/app/parent/login/'
        parent_dashboard_url = f'/tenant/{tenant_prefix}/app/parent/dashboard/'
        
        # Student URLs
        students_url = f'/tenant/{tenant_prefix}/app/students/'
        
    else:
        # Public schema or no tenant prefix
        base_url = '/app'
        
        dashboard_url = '/app/dashboard/'
        home_url = '/app/'
        login_url = '/app/login/'
        logout_url = '/app/logout/'
        
        fees_base = '/app/fees'
        fees_dashboard_url = f'{fees_base}/dashboard/'
        fees_defaulters_url = f'{fees_base}/defaulters/'
        fees_payment_url = f'{fees_base}/payment/record/'
        fees_structure_url = f'{fees_base}/structure/'
        fees_collection_url = f'{fees_base}/collection-report/'
        fees_students_url = f'{fees_base}/students/'
        
        tv_base = '/app/tv'
        tv_display_url = f'{tv_base}/'
        tv_dashboard_url = f'{tv_base}/dashboard/'
        tv_content_add_url = f'{tv_base}/content/add/'
        tv_settings_url = f'{tv_base}/settings/'
        
        library_url = '/app/library/'
        upload_url = '/app/upload/'
        performance_url = '/app/performance/'
        results_url = '/app/results/'
        exams_url = '/app/exams/'
        sms_url = '/app/sms/'
        feedback_url = '/app/feedback/'
        parent_url = '/app/parent/'
        parent_login_url = '/app/parent/login/'
        parent_dashboard_url = '/app/parent/dashboard/'
        students_url = '/app/students/'
    
    # Get user role if authenticated
    user_role = None
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        user_role = request.user.profile.role
    
    context = {
        # Basic tenant info
        'is_public_schema': is_public,
        'is_tenant_schema': not is_public,
        'current_host': host,
        'current_schema': schema_name,
        'tenant_prefix': tenant_prefix,
        'tenant': tenant,
        'base_url': base_url,
        'app_prefix': f'/tenant/{tenant_prefix}/app' if tenant_prefix else '/app',
        
        # User info
        'user_role': user_role,
        'is_authenticated': request.user.is_authenticated,
        
        # Dashboard URLs
        'dashboard_url': dashboard_url,
        'home_url': home_url,
        
        # Auth URLs
        'login_url': login_url,
        'logout_url': logout_url,
        
        # Fees URLs
        'fees_base': fees_base,
        'fees_dashboard_url': fees_dashboard_url,
        'fees_defaulters_url': fees_defaulters_url,
        'fees_payment_url': fees_payment_url,
        'fees_structure_url': fees_structure_url,
        'fees_collection_url': fees_collection_url,
        'fees_students_url': fees_students_url,
        
        # TV URLs
        'tv_base': tv_base,
        'tv_display_url': tv_display_url,
        'tv_dashboard_url': tv_dashboard_url,
        'tv_content_add_url': tv_content_add_url,
        'tv_settings_url': tv_settings_url,
        
        # Library URLs
        'library_url': library_url,
        'upload_url': upload_url,
        
        # Performance URLs
        'performance_url': performance_url,
        'results_url': results_url,
        'exams_url': exams_url,
        
        # SMS URLs
        'sms_url': sms_url,
        
        # Feedback URLs
        'feedback_url': feedback_url,
        
        # Parent URLs
        'parent_url': parent_url,
        'parent_login_url': parent_login_url,
        'parent_dashboard_url': parent_dashboard_url,
        
        # Student URLs
        'students_url': students_url,
    }
    
    return context


def tenant_urls(request):
    """
    Context processor that provides a dictionary of all tenant-aware URLs.
    Useful for JavaScript and complex templates.
    """
    from django.urls import reverse
    
    tenant_prefix = request.session.get('tenant_schema', '')
    if not tenant_prefix:
        m = _re.match(r'^/tenant/([^/]+)/', request.path)
        if m:
            tenant_prefix = m.group(1)
    
    urls = {
        'tenant_prefix': tenant_prefix,
    }
    
    # Define common URL patterns
    url_patterns = [
        'dashboard', 'login', 'logout', 'fees_dashboard', 'fees_defaulters',
        'fees_payment', 'fees_structure', 'fees_collection', 'tv_display',
        'tv_dashboard', 'library', 'upload', 'performance', 'results',
        'exams', 'sms', 'feedback', 'parent_dashboard', 'students'
    ]
    
    for pattern in url_patterns:
        if tenant_prefix:
            urls[pattern] = f'/tenant/{tenant_prefix}/app/{pattern.replace("_", "/")}/'
        else:
            urls[pattern] = f'/app/{pattern.replace("_", "/")}/'
    
    return {'tenant_urls': urls}
