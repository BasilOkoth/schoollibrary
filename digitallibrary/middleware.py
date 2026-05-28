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
    - /app/ as default tenant (demo)
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
    DEFAULT_TENANT_SCHEMA = "demo"

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

        # Debug logging
        logger.info(f"===== Middleware Debug =====")
        logger.info(f"Path: {path}")
        logger.info(f"Method: {request.method}")
        logger.info(f"Host: {host}")

        # 1. Admin/health paths always use public schema
        if (
            path.startswith("/admin/")
            or path.startswith("/health/")
            or path.startswith("/healthz/")
        ):
            logger.info(f"Admin/health path -> using public schema")
            self._set_public_schema(request, public_schema)
            return None

        # 2. Path-based tenant routing (MUST come first)
        match = re.match(r"^/tenant/([^/]+)/", path)
        if match:
            schema_name = match.group(1)
            logger.info(f"Found tenant in path: {schema_name}")
            return self._set_tenant_schema(request, schema_name, public_schema)

        # 3. /app/ path uses default tenant
        if path == "/app/" or path.startswith("/app/"):
            logger.info(f"/app/ path detected, using default tenant: {self.DEFAULT_TENANT_SCHEMA}")
            if hasattr(request, 'tenant') and request.tenant:
                logger.info(f"Already have tenant: {request.tenant.schema_name}")
                return None
            return self._set_tenant_schema(request, self.DEFAULT_TENANT_SCHEMA, public_schema)

        # 4. Public hosts always use public schema
        if self._is_public_host(host):
            logger.info(f"Public host: {host} -> using public schema")
            self._set_public_schema(request, public_schema)
            return None

        # 5. Normal domain-based routing
        logger.info(f"No match, using parent middleware")
        return super().process_request(request)

    def _set_public_schema(self, request, public_schema):
        """Sets the connection to the public schema."""
        connection.set_schema(public_schema)
        request.urlconf = getattr(settings, "PUBLIC_SCHEMA_URLCONF", "schoollibrary.urls")

        try:
            from tenants.models import School
            request.tenant = School.objects.filter(schema_name=public_schema).first() or School.objects.first()
            logger.info(f"Set public schema, urlconf: {request.urlconf}")
        except Exception as e:
            logger.warning(f"Could not set public tenant: {e}")
            request.tenant = None

    def _set_tenant_schema(self, request, schema_name, public_schema):
        """Sets the connection to a specific tenant schema."""
        try:
            from tenants.models import School
            from django.db import connection as db_connection
            
            # Ensure we're on public schema to query tenants
            db_connection.set_schema('public')
            
            tenant = School.objects.filter(schema_name=schema_name).first()
            
            if not tenant:
                # Try case-insensitive
                tenant = School.objects.filter(schema_name__iexact=schema_name).first()
                
            if not tenant:
                all_tenants = list(School.objects.values_list('schema_name', flat=True))
                logger.error(f"Tenant '{schema_name}' not found. Available: {all_tenants}")
                self._set_public_schema(request, public_schema)
                return None
            
            # Set the tenant on the connection
            db_connection.set_tenant(tenant)
            request.tenant = tenant
            
            # 🔥 CRITICAL FIX: Set URLconf to digitallibrary.urls for tenant requests
            # NOT schoollibrary.urls!
            request.urlconf = 'digitallibrary.urls'
            
            logger.info(f"✅ Set tenant schema to: {schema_name}, urlconf: {request.urlconf}")
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
            
            if "does not exist" not in error_msg:
                raise

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
                return HttpResponse(
                    "<h1>System Initializing</h1><p>The database tables are being created. Please refresh this page in 1 minute.</p>",
                    status=503
                )
