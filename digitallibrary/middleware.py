import re
import logging
from django.conf import settings
from django.db import ProgrammingError, connection
from django.http import JsonResponse
from django.shortcuts import render
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name

logger = logging.getLogger(__name__)


class PublicAdminMiddleware(TenantMainMiddleware):
    """
    Tenant routing middleware - UPDATED ORDER
    """

    PUBLIC_HOSTS = {
        "shulehub.org",
        "www.shulehub.org",
        "localhost",
        "127.0.0.1",
        "schoollibrary-1.onrender.com", # Added Render domain
    }

    def process_request(self, request):
        host = request.get_host().split(":")[0].lower()
        public_schema = get_public_schema_name()

        # 1. PRIORITY: Path-based tenant routing
        # Check this first so that /tenant/schema/... always works even on public hosts
        match = re.match(r"^/tenant/([^/]+)/", request.path)
        if match:
            schema_name = match.group(1)
            return self._set_tenant_schema(request, schema_name, public_schema)

        # 2. Public domains and explicit public routes
        if (host in self.PUBLIC_HOSTS or 
            request.path.startswith("/admin/") or
            request.path.startswith("/health/") or
            request.path.startswith("/healthz/") or
            request.path == "/"):
            self._set_public_schema(request, public_schema)
            return None

        # 3. Default to parent class behavior (domain-based lookup)
        return super().process_request(request)

    def _set_public_schema(self, request, public_schema):
        connection.set_schema(public_schema)
        request.urlconf = getattr(settings, "PUBLIC_SCHEMA_URLCONF", "schoollibrary.urls")
        try:
            from tenants.models import School
            request.tenant = School.objects.filter(schema_name=public_schema).first()
        except Exception:
            request.tenant = None

    def _set_tenant_schema(self, request, schema_name, public_schema):
        try:
            from tenants.models import School
            
            # Force public schema to query School
            connection.set_schema(public_schema)
            
            # Get the tenant
            tenant = School.objects.get(schema_name=schema_name)
            
            # Switch to tenant schema
            connection.set_tenant(tenant)
            
            request.tenant = tenant
            request.urlconf = "schoollibrary.urls"
            
            # Store in session (requires SessionMiddleware to be before this in settings.py)
            if hasattr(request, 'session'):
                request.session['tenant_schema'] = schema_name
            
            logger.info(f"Set tenant schema: {schema_name}")
            return None
            
        except School.DoesNotExist:
            logger.error(f"Tenant not found: {schema_name}")
            self._set_public_schema(request, public_schema)
            return None
        except Exception as e:
            logger.error(f"Error setting tenant: {e}")
            self._set_public_schema(request, public_schema)
            return None


class StripTenantSchemaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        return self.get_response(request)
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        view_kwargs.pop("tenant_schema", None)
        return None


class ProgrammingErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except ProgrammingError as e:
            if "does not exist" not in str(e):
                raise
            return JsonResponse({
                "error": "System setup in progress",
                "message": "Database initializing. Refresh in a minute.",
            }, status=503)

# Add this at the end of the file

class ForceSessionMiddleware:
    """Force session to be saved on every request"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Ensure session is saved
        if hasattr(request, 'session') and request.session and request.session.modified:
            request.session.save()
        
        return response
