# digitallibrary/middleware.py

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
        "schoollibrary.onrender.com", # Added for safety
    }

    def process_request(self, request):
        host = request.get_host().split(":")[0].lower()
        public_schema = get_public_schema_name()

        # 1. Force public schema for main/public domain and admin/health routes
        if (
            host in self.PUBLIC_HOSTS
            or request.path.startswith("/admin/")
            or request.path.startswith("/health/")
            or request.path.startswith("/healthz/")
        ):
            self._set_public_schema(request, public_schema)
            return None

        # 2. Path-based tenant routing: /tenant/<schema>/...
        match = re.match(r"^/tenant/([^/]+)/", request.path)
        if match:
            schema_name = match.group(1)
            return self._set_tenant_schema(request, schema_name, public_schema)

        # 3. Normal domain-based django-tenants routing
        return super().process_request(request)

    def _set_public_schema(self, request, public_schema):
        """Sets the connection to the public schema and attempts to find the public tenant record."""
        connection.set_schema(public_schema)
        request.urlconf = getattr(settings, "PUBLIC_SCHEMA_URLCONF", "schoollibrary.urls")

        try:
            from tenants.models import School
            # ROBUST CHECK: Try exact match first, then fallback to any record if public doesn't exist
            request.tenant = School.objects.filter(schema_name=public_schema).first() or School.objects.first()
        except Exception:
            request.tenant = None

    def _set_tenant_schema(self, request, schema_name, public_schema):
        """Sets the connection to a specific tenant schema."""
        try:
            from tenants.models import School
            tenant = School.objects.get(schema_name=schema_name)
            connection.set_tenant(tenant)
            request.tenant = tenant
            request.urlconf = "schoollibrary.urls"
            return None
        except Exception:
            # Fallback to public if tenant not found
            self._set_public_schema(request, public_schema)
            return None


class StripTenantSchemaMiddleware:
    """Removes 'tenant_schema' URL kwarg before reaching view functions."""
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        return self.get_response(request)
    def process_view(self, request, view_func, view_args, view_kwargs):
        view_kwargs.pop("tenant_schema", None)
        return None


class ProgrammingErrorMiddleware:
    """
    Catches ProgrammingError (missing tables) and returns a friendly setup message.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except ProgrammingError as e:
            error_msg = str(e)
            
            # If the error is not about missing tables, re-raise it
            if "does not exist" not in error_msg:
                raise

            # For API/AJAX requests, return JSON
            if (
                request.path.startswith("/api/")
                or request.path.startswith("/app/api/")
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            ):
                return JsonResponse(
                    {
                        "error": "System setup in progress",
                        "message": "The database is still being initialized. Please refresh in a minute.",
                        "setup": True,
                    },
                    status=503,
                )

            # For standard page requests, show a friendly setup template
            # This is MUCH better than a 500 error
            try:
                return render(
                    request,
                    "digitallibrary/setup_required.html",
                    {
                        "message": "The school library system is being initialized. This usually takes about 60 seconds during the first deployment.",
                    },
                    status=503,
                )
            except Exception:
                # If the setup template itself fails (e.g. missing), return a simple response
                from django.http import HttpResponse
                return HttpResponse(
                    "<h1>System Initializing</h1><p>The database tables are being created. Please refresh this page in 1 minute.</p>",
                    status=503
                )
