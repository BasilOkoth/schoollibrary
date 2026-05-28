import re
import logging
from django.conf import settings
from django.db import ProgrammingError, connection
from django.http import JsonResponse, HttpResponse
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
    - /app/ as default tenant (demo) - NEW!
    - /tenant/<schema>/... as path-based tenant access
    - other domains using normal django-tenants domain routing
    """

    PUBLIC_HOSTS = {
        "shulehub.org",
        "www.shulehub.org",
        "localhost",
        "127.0.0.1",
    }
    
    # Default tenant to use when accessing /app/
    DEFAULT_TENANT_SCHEMA = "demo"  # Change this to your default tenant

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
        path = request.path

        # 1. Admin/health paths always use public schema (regardless of host)
        if (
            path.startswith("/admin/")
            or path.startswith("/health/")
            or path.startswith("/healthz/")
        ):
            self._set_public_schema(request, public_schema)
            return None

        # 2. Path-based tenant routing wins over host-based routing
        #    e.g. schoollibrary-1.onrender.com/tenant/demo/app/ → demo schema
        match = re.match(r"^/tenant/([^/]+)/", path)
        if match:
            schema_name = match.group(1)
            return self._set_tenant_schema(request, schema_name, public_schema)

        # 3. NEW: /app/ path uses default tenant (demo)
        #    This makes https://schoollibrary-1.onrender.com/app/ open the tenant dashboard
        if path == "/app/" or path.startswith("/app/"):
            # If we're already in a tenant context, don't override
            if hasattr(request, 'tenant') and request.tenant:
                return None
            # Set to default tenant
            return self._set_tenant_schema(request, self.DEFAULT_TENANT_SCHEMA, public_schema)

        # 4. Public hosts always use public schema
        if self._is_public_host(host):
            self._set_public_schema(request, public_schema)
            return None

        # 5. Normal domain-based django-tenants routing (subdomains)
        return super().process_request(request)

    def _set_public_schema(self, request, public_schema):
        """Sets the connection to the public schema and attempts to find the public tenant record."""
        connection.set_schema(public_schema)
        request.urlconf = getattr(settings, "PUBLIC_SCHEMA_URLCONF", "schoollibrary.urls")

        try:
            from tenants.models import School
            # ROBUST CHECK: Try exact match first, then fallback to any record if public doesn't exist
            request.tenant = School.objects.filter(schema_name=public_schema).first() or School.objects.first()
        except Exception as e:
            logger.warning(f"Could not set public tenant: {e}")
            request.tenant = None

    def _set_tenant_schema(self, request, schema_name, public_schema):
        """Sets the connection to a specific tenant schema."""
        try:
            from tenants.models import School
            tenant = School.objects.get(schema_name=schema_name)
            connection.set_tenant(tenant)
            request.tenant = tenant
            request.urlconf = "schoollibrary.urls"
            logger.info(f"Set tenant schema to: {schema_name}")
            return None
        except School.DoesNotExist:
            logger.warning(f"Tenant '{schema_name}' not found, falling back to public schema")
            self._set_public_schema(request, public_schema)
            return None
        except Exception as e:
            logger.error(f"Error setting tenant schema '{schema_name}': {e}")
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
                # If the setup template itself fails, return a simple response
                return HttpResponse(
                    "<h1>System Initializing</h1><p>The database tables are being created. Please refresh this page in 1 minute.</p>",
                    status=503
                )
