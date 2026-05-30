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
        
        # Get tenant from session (for persistence after login)
        session_tenant = None
        if hasattr(request, 'session') and request.session:
            session_tenant = request.session.get('tenant_schema')

        # 1. Admin and health endpoints always use public schema
        if (
            request.path.startswith("/admin/")
            or request.path.startswith("/health/")
            or request.path.startswith("/healthz/")
            or request.path.startswith("/smart-login/")
        ):
            self._set_public_schema(request, public_schema)
            return None

        # 2. URL tenant routing (highest priority)
        match = re.match(r"^/tenant/([^/]+)/", request.path)
        if match:
            schema_name = match.group(1)
            # Store tenant in session for persistence
            if hasattr(request, 'session'):
                request.session['tenant_schema'] = schema_name
                request.session['active_tenant'] = schema_name
                logger.debug(f"Stored tenant {schema_name} in session")
            return self._set_tenant_schema(request, schema_name, public_schema)

        # 3. IMPORTANT FIX: Skip redirects for login, logout, and POST requests
        is_login_path = '/login/' in request.path or '/logout/' in request.path
        is_post_request = request.method == 'POST'
        is_auth_related = '/auth/' in request.path or '/accounts/' in request.path
        
        # Handle /app/ redirects for public hosts (using session tenant)
        # BUT ONLY for GET requests that aren't login-related
        if (self._is_public_host(host) 
            and request.path.startswith('/app/') 
            and not is_login_path
            and not is_auth_related
            and not is_post_request):
            try:
                if hasattr(request, 'session'):
                    tenant_schema = request.session.get('tenant_schema')
                    if tenant_schema:
                        suffix = request.path[4:] if len(request.path) > 4 else ''
                        new_url = f'/tenant/{tenant_schema}/app{suffix}'
                        if request.GET:
                            new_url += '?' + request.GET.urlencode()
                        if request.method == 'GET':
                            return redirect(new_url)
                        else:
                            resp = HttpResponseRedirect(new_url)
                            resp.status_code = 307
                            return resp
            except Exception as e:
                logger.warning(f"App redirect failed: {e}")

        # 4. Public hosts use public schema
        if self._is_public_host(host):
            self._set_public_schema(request, public_schema)
            return None

        # 5. If we have a session tenant but no URL match, use it
        if session_tenant:
            try:
                logger.debug(f"Using session tenant: {session_tenant}")
                return self._set_tenant_schema(request, session_tenant, public_schema)
            except Exception as e:
                logger.warning(f"Failed to set tenant from session: {e}")

        # 6. Fallback to normal django-tenants behavior
        return super().process_request(request)

    def _set_public_schema(self, request, public_schema):
        """Set connection to public schema"""
        connection.set_schema(public_schema)
        request.urlconf = getattr(settings, "PUBLIC_SCHEMA_URLCONF", "schoollibrary.urls")
        try:
            from tenants.models import School
            request.tenant = School.objects.filter(schema_name=public_schema).first() or School.objects.first()
        except Exception as e:
            logger.error(f"Error setting public tenant: {e}")
            request.tenant = None

    def _set_tenant_schema(self, request, schema_name, public_schema):
        """Set connection to tenant schema"""
        try:
            from tenants.models import School
            tenant = School.objects.get(schema_name=schema_name)
            connection.set_tenant(tenant)
            request.tenant = tenant
            request.urlconf = "schoollibrary.urls"
            request.current_app = 'digitallibrary'
            
            # CRITICAL FIX: Don't force session save during login/POST requests
            is_login_related = '/login/' in request.path or '/logout/' in request.path
            is_auth_related = '/auth/' in request.path or '/accounts/' in request.path
            is_post_request = request.method == 'POST'
            
            if hasattr(request, 'session'):
                if is_login_related or is_auth_related or is_post_request:
                    # For login flow, set tenant but don't force save
                    request.session['tenant_schema'] = schema_name
                    request.session.modified = True
                    logger.debug(f"Set tenant for login flow: {schema_name}")
                else:
                    # Normal flow - save normally
                    request.session['tenant_schema'] = schema_name
                    request.session['active_tenant'] = schema_name
                    logger.debug(f"Stored tenant in session: {schema_name}")
                
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
