# digitallibrary/middleware.py - MERGED WORKING VERSION

import re
import logging
from django.conf import settings
from django.db import ProgrammingError, connection
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name

logger = logging.getLogger(__name__)


class PublicAdminMiddleware(TenantMainMiddleware):
    """
    Handles:
    - shulehub.org and www.shulehub.org as public schema
    - /admin/ always as public schema
    - /health/ and /healthz/ always as public schema
    - /tenant/<schema>/... as path-based tenant access
    - other domains using normal django-tenants domain routing
    """

    PUBLIC_HOSTS = {
        "shulehub.org",
        "www.shulehub.org",
        "localhost",
        "127.0.0.1",
    }

    def _is_public_host(self, host):
        if host in self.PUBLIC_HOSTS:
            return True
        if host.endswith(".onrender.com"):
            return True
        if host.endswith(".replit.dev") or host.endswith(".replit.app") or host.endswith(".repl.co"):
            return True
        return False

    def process_request(self, request):
        host = request.get_host().split(":")[0].lower()
        public_schema = get_public_schema_name()

        # 1. Force public schema for main/public domain and admin/health routes
        if (
            host in self.PUBLIC_HOSTS
            or request.path.startswith("/admin/")
            or request.path.startswith("/health/")
            or request.path.startswith("/healthz/")
            or request.path.startswith("/smart-login/")
        ):
            self._set_public_schema(request, public_schema)
            return None

        # 2. Path-based tenant routing: /tenant/<schema>/...
        match = re.match(r"^/tenant/([^/]+)/", request.path)
        if match:
            schema_name = match.group(1)
            # Store tenant in session for persistence (minimal change)
            if hasattr(request, 'session'):
                request.session['tenant_schema'] = schema_name
            return self._set_tenant_schema(request, schema_name, public_schema)

        # 3. REMOVED: /app/ redirect logic - this breaks login
        # Let the normal flow handle it

        # 4. Public hosts use public schema
        if self._is_public_host(host):
            self._set_public_schema(request, public_schema)
            return None

        # 5. REMOVED: Use session tenant logic - this creates loops

        # 6. Normal domain-based django-tenants routing
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
            tenant = School.objects.get(schema_name=schema_name)
            connection.set_tenant(tenant)
            request.tenant = tenant
            request.urlconf = "schoollibrary.urls"
            request.current_app = 'digitallibrary'
            return None
        except School.DoesNotExist:
            logger.error(f"Tenant not found: {schema_name}")
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
            
            # API endpoints return JSON
            if (
                request.path.startswith("/api/")
                or request.path.startswith("/app/api/")
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            ):
                return JsonResponse(
                    {
                        "error": "System setup in progress",
                        "message": "Database still initializing. Refresh in a minute.",
                        "setup": True,
                    },
                    status=503,
                )
            
            # Regular pages show friendly error
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
