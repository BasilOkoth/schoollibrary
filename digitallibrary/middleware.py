# digitallibrary/middleware.py

import re
from django.db import connection
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class ProgrammingErrorMiddleware(MiddlewareMixin):
    """Handle programming errors gracefully"""
    
    def process_exception(self, request, exception):
        from django.db import ProgrammingError
        if isinstance(exception, ProgrammingError):
            logger.error(f"ProgrammingError: {exception}")
            from django.http import HttpResponse
            return HttpResponse(
                "<h1>Database Error</h1><p>Please try again later.</p>", 
                status=500
            )
        return None


class PublicAdminMiddleware(MiddlewareMixin):
    """Handle admin access on public schema"""
    
    def process_request(self, request):
        from django.db import connection
        if request.path.startswith('/admin/'):
            if connection.schema_name == 'public':
                return None
        return None


class StripTenantSchemaMiddleware(MiddlewareMixin):
    """Strip tenant schema from URLs for proper routing"""
    
    def process_request(self, request):
        path_parts = request.path.split('/')
        if len(path_parts) > 2 and path_parts[1] == 'tenant':
            tenant_schema = path_parts[2]
            request.tenant_schema = tenant_schema
            request.session['tenant_schema'] = tenant_schema
        return None


class ForceSessionMiddleware(MiddlewareMixin):
    """Ensure session is always saved"""
    
    def process_response(self, request, response):
        if hasattr(request, 'session') and request.session.modified:
            request.session.save()
        return response


class TenantSessionMiddleware(MiddlewareMixin):
    """Middleware to maintain tenant session across requests"""
    
    def process_request(self, request):
        tenant_schema = request.session.get('tenant_schema')
        
        if tenant_schema and not hasattr(request, 'tenant'):
            try:
                from tenants.models import School
                tenant = School.objects.get(schema_name=tenant_schema)
                request.tenant = tenant
                connection.set_tenant(tenant)
                logger.debug(f"TenantSessionMiddleware set tenant: {tenant_schema}")
            except Exception as e:
                logger.error(f"TenantSessionMiddleware error: {e}")
        return None
    
    def process_response(self, request, response):
        if hasattr(request, 'tenant_schema'):
            request.session['tenant_schema'] = request.tenant_schema
        elif hasattr(request, 'tenant') and request.tenant:
            request.session['tenant_schema'] = request.tenant.schema_name
        return response


class ForceTenantMiddleware(MiddlewareMixin):
    """Force tenant to be set from session or URL"""
    
    def process_request(self, request):
        tenant_schema = request.session.get('tenant_schema')
        
        if not tenant_schema:
            path_parts = request.path.split('/')
            if len(path_parts) > 2 and path_parts[1] == 'tenant':
                tenant_schema = path_parts[2]
                request.session['tenant_schema'] = tenant_schema
        
        if tenant_schema and not hasattr(request, 'tenant'):
            try:
                from tenants.models import School
                tenant = School.objects.get(schema_name=tenant_schema)
                request.tenant = tenant
                connection.set_tenant(tenant)
                logger.info(f"ForceTenantMiddleware set tenant: {tenant_schema}")
            except Exception as e:
                logger.error(f"ForceTenantMiddleware error: {e}")
        return None


class EnsureTenantMiddleware(MiddlewareMixin):
    """Ensure tenant is set for all tenant requests"""
    
    def process_request(self, request):
        public_paths = ['/admin/', '/static/', '/media/', '/login/', '/logout/']
        if any(request.path.startswith(path) for path in public_paths):
            return None
        
        if '/tenant/' in request.path:
            tenant_schema = request.session.get('tenant_schema')
            
            if not tenant_schema:
                path_parts = request.path.split('/')
                if len(path_parts) > 2 and path_parts[1] == 'tenant':
                    tenant_schema = path_parts[2]
                    request.session['tenant_schema'] = tenant_schema
            
            if tenant_schema and not hasattr(request, 'tenant'):
                try:
                    from tenants.models import School
                    tenant = School.objects.get(schema_name=tenant_schema)
                    request.tenant = tenant
                    connection.set_tenant(tenant)
                except Exception as e:
                    logger.error(f"EnsureTenantMiddleware error: {e}")
        return None
