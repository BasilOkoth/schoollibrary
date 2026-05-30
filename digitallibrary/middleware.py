# digitallibrary/middleware.py - SIMPLIFIED WORKING VERSION

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
    Handles tenant routing for both domain and path-based access
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

        # 1. Public schema for public domains and admin/health routes
        if (
            host in self.PUBLIC_HOSTS
            or request.path.startswith("/admin/")
            or request.path.startswith("/health/")
            or request.path.startswith("/healthz/")
            or request.path.startswith("/smart-login/")
        ):
            self._set_public_schema(request, public_schema)
            return None

        # 2. Path-based tenant routing
        match = re.match(r"^/tenant/([^/]+)/", request.path)
        if match:
            schema_name = match.group(1)
            return self._set_tenant_schema(request, schema_name, public_schema)

        # 3. Domain-based routing
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
        """Set connection to tenant schema"""
        try:
            from tenants.models import School
            
            # Ensure we're in public schema to query School model
            connection.set_schema(public_schema)
            
            # Get the tenant
            tenant = School.objects.get(schema_name=schema_name)
            
            # Switch to tenant schema
            connection.set_tenant(tenant)
            
            request.tenant = tenant
            request.urlconf = "schoollibrary.urls"
            
            # Store tenant in session for persistence
            if hasattr(request, 'session'):
                request.session['tenant_schema'] = schema_name
            
            logger.info(f"✅ Set tenant schema: {schema_name}")
            return None
            
        except School.DoesNotExist:
            logger.error(f"❌ Tenant not found: {schema_name}")
            self._set_public_schema(request, public_schema)
            return None
        except Exception as e:
            logger.exception(f"Error setting tenant schema {schema_name}: {e}")
            self._set_public_schema(request, public_schema)
            return None


class StripTenantSchemaMiddleware:
    """Removes 'tenant_schema' URL kwarg before reaching views."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        return self.get_response(request)
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        view_kwargs.pop("tenant_schema", None)
        return None


class ProgrammingErrorMiddleware:
    """Handles database not ready errors gracefully"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except ProgrammingError as e:
            error_msg = str(e)
            if "does not exist" not in error_msg:
                raise
            
            if request.path.startswith("/api/") or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "error": "System setup in progress",
                        "message": "Database still initializing. Refresh in a minute.",
                        "setup": True,
                    },
                    status=503,
                )
            
            try:
                return render(
                    request,
                    "digitallibrary/setup_required.html",
                    {"message": "The school library system is being initialized."},
                    status=503,
                )
            except Exception:
                from django.http import HttpResponse
                return HttpResponse(
                    "<h1>System Initializing</h1><p>Refresh in 1 minute.</p>",
                    status=503
                )
