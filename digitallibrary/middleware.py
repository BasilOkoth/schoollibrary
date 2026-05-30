# digitallibrary/middleware.py

import re
import logging
from django.conf import settings
from django.db import ProgrammingError, connection
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name

logger = logging.getLogger(__name__)


# digitallibrary/middleware.py - COMPLETE REPLACEMENT

class PublicAdminMiddleware(TenantMainMiddleware):
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
        
        # ALWAYS start in public schema for tenant resolution
        connection.set_schema(public_schema)
        
        # Get tenant from session
        session_tenant = None
        if hasattr(request, 'session') and request.session:
            session_tenant = request.session.get('tenant_schema')

        # 1. Admin and health endpoints always use public schema
        if (request.path.startswith("/admin/") or 
            request.path.startswith("/health/") or 
            request.path.startswith("/healthz/") or
            request.path.startswith("/smart-login/")):
            self._set_public_schema(request, public_schema)
            return None

        # 2. URL tenant routing (highest priority)
        match = re.match(r"^/tenant/([^/]+)/", request.path)
        if match:
            schema_name = match.group(1)
            
            # Verify tenant exists (while in public schema)
            from tenants.models import School
            if not School.objects.filter(schema_name=schema_name).exists():
                logger.error(f"Tenant '{schema_name}' not found in database")
                self._set_public_schema(request, public_schema)
                # Return 404 or redirect
                from django.http import HttpResponseNotFound
                request.tenant_not_found = True
                return HttpResponseNotFound(f"Tenant '{schema_name}' not found")
            
            # Store in session
            if hasattr(request, 'session'):
                request.session['tenant_schema'] = schema_name
            
            return self._set_tenant_schema(request, schema_name, public_schema)

        # 3. Handle /app/ redirects
        if (self._is_public_host(host) and 
            request.path.startswith('/app/') and 
            '/login/' not in request.path and
            request.method == 'GET'):
            
            if session_tenant:
                # Redirect to tenant URL
                suffix = request.path[4:] if len(request.path) > 4 else ''
                new_url = f'/tenant/{session_tenant}/app{suffix}'
                if request.GET:
                    new_url += '?' + request.GET.urlencode()
                from django.shortcuts import redirect
                return redirect(new_url)

        # 4. Public hosts use public schema
        if self._is_public_host(host):
            self._set_public_schema(request, public_schema)
            return None

        # 5. Use session tenant if available
        if session_tenant:
            from tenants.models import School
            if School.objects.filter(schema_name=session_tenant).exists():
                return self._set_tenant_schema(request, session_tenant, public_schema)

        # 6. Fallback to normal django-tenants behavior
        return super().process_request(request)

    def _set_public_schema(self, request, public_schema):
        """Set connection to public schema"""
        connection.set_schema(public_schema)
        request.urlconf = getattr(settings, "PUBLIC_SCHEMA_URLCONF", "schoollibrary.urls")
        try:
            from tenants.models import School
            request.tenant = School.objects.filter(schema_name=public_schema).first()
        except Exception as e:
            logger.error(f"Error setting public tenant: {e}")
            request.tenant = None

    def _set_tenant_schema(self, request, schema_name, public_schema):
        """Set connection to tenant schema"""
        try:
            from tenants.models import School
            
            # Ensure we're in public schema to query School
            connection.set_schema(public_schema)
            
            # Get the tenant
            tenant = School.objects.get(schema_name=schema_name)
            
            # Switch to tenant schema
            connection.set_tenant(tenant)
            request.tenant = tenant
            request.urlconf = "schoollibrary.urls"
            request.current_app = 'digitallibrary'
            
            # Store in session for persistence
            if hasattr(request, 'session'):
                request.session['tenant_schema'] = schema_name
                request.session['active_tenant'] = schema_name
                logger.debug(f"Set tenant schema: {schema_name}")
                
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
