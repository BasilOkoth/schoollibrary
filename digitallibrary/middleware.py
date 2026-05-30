# digitallibrary/middleware.py - COMPLETE REPLACEMENT

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
    Tenant routing middleware
    """

    PUBLIC_HOSTS = {
        "shulehub.org",
        "www.shulehub.org",
        "localhost",
        "127.0.0.1",
    }

    def process_request(self, request):
        host = request.get_host().split(":")[0].lower()
        public_schema = get_public_schema_name()

        # Force public schema for public domains and admin routes
        if (host in self.PUBLIC_HOSTS or 
            request.path.startswith("/admin/") or
            request.path.startswith("/health/") or
            request.path.startswith("/healthz/")):
            self._set_public_schema(request, public_schema)
            return None

        # Path-based tenant routing
        match = re.match(r"^/tenant/([^/]+)/", request.path)
        if match:
            schema_name = match.group(1)
            return self._set_tenant_schema(request, schema_name, public_schema)

        # Default to parent class behavior
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
            
            # Store in session
            if hasattr(request, 'session'):
                request.session['tenant_schema'] = schema_name
            
            logger.info(f"Set tenant schema: {schema_name}")
            return None
            
        except School.DoesNotExist:
            logger.error(f"Tenant not found: {schema_name}")
            self._set_public_schema(request, public_schema)
            return None
        except Exception as e:
            logger.error(f"Error: {e}")
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
