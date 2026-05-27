# digitallibrary/middleware.py

import re
import logging
from django.conf import settings
from django.db import ProgrammingError, connection
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name, get_tenant_model

logger = logging.getLogger(__name__)


class PublicSchemaMiddleware:
    """Force public schema for specific paths BEFORE tenant detection"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Get host without port
        host = request.get_host().split(':')[0].lower()
        public_hosts = ['localhost', '127.0.0.1', 'shulehub.localhost', 'shulehub.org', 'www.shulehub.org']
        
        # Check if this is a tenant subdomain (has dot and not in public hosts)
        is_tenant_subdomain = host not in public_hosts and '.' in host
        
        # For tenant subdomains, skip public schema logic - let tenant middleware handle it
        if is_tenant_subdomain:
            return self.get_response(request)
        
        # Only apply public schema for landing page on public domains
        if request.path == '/' or request.path == '':
            return self.get_response(request)
        
        public_paths = ['/healthz/', '/health/', '/debug/', '/debug-app/']
        
        if request.path in public_paths:
            request.should_be_public = True
            connection.set_schema('public')
        
        return self.get_response(request)


class PublicAdminMiddleware(TenantMainMiddleware):
    """
    Handles tenant detection for subdomains and public routes
    """

    PUBLIC_HOSTS = {
        "shulehub.org",
        "www.shulehub.org",
        "schoollibrary.onrender.com",
        "127.0.0.1",
        "localhost",
        "shulehub.localhost",
    }
    
    # Explicit list of tenant subdomains (these should NOT show landing page)
    TENANT_SUBDOMAINS = {
        "miyuga.localhost",
        "oluti.localhost",
        "daraja.localhost", 
        "orero.localhost",
    }
    
    LANDING_PAGE_PATHS = ['/', '']
    
    PUBLIC_PATHS = [
        '/healthz/', '/health/', '/debug/', '/debug-app/',
        '/login/', '/logout/', '/password-reset/', 
        '/password-reset/done/', '/password-reset-confirm/',
        '/password-reset-complete/', '/accounts/login/',
        '/accounts/logout/',
    ]

    def process_request(self, request):
        host = request.get_host().split(":")[0].lower()
        public_schema = get_public_schema_name()

        # ========== CRITICAL: Check if this is a tenant subdomain ==========
        is_tenant_host = False
        
        # First, check against explicit tenant subdomains list
        if host in self.TENANT_SUBDOMAINS:
            is_tenant_host = True
            logger.debug(f"Host {host} matched tenant subdomain list")
        
        # Also check if host has a dot and is NOT in PUBLIC_HOSTS
        elif host not in self.PUBLIC_HOSTS and '.' in host:
            is_tenant_host = True
            logger.debug(f"Host {host} detected as potential tenant subdomain")
        
        # If this is a tenant subdomain, handle tenant routing
        if is_tenant_host:
            # Try to find tenant for this host
            try:
                TenantModel = get_tenant_model()
                tenant = TenantModel.objects.filter(domains__domain=host).first()
                if tenant:
                    # This is a valid tenant - set tenant and return
                    connection.set_tenant(tenant)
                    request.tenant = tenant
                    request.urlconf = "schoollibrary.urls"
                    logger.info(f"Tenant {tenant.schema_name} found for host {host}")
                    return None
                else:
                    logger.warning(f"No tenant found for host {host}, but continuing")
            except Exception as e:
                logger.error(f"Tenant lookup failed for {host}: {e}")
            
            # Continue to parent middleware for tenant detection
            return super().process_request(request)

        # ========== LANDING PAGE - ONLY for public hosts ==========
        # Only show landing page on public hosts
        if request.path in self.LANDING_PAGE_PATHS:
            connection.set_schema(public_schema)
            request.urlconf = getattr(settings, "PUBLIC_SCHEMA_URLCONF", "schoollibrary.public_urls")
            request.is_public_landing = True
            request.tenant = None
            logger.debug(f"Landing page served for host {host}")
            return None

        # Check if request should be public (set by PublicSchemaMiddleware)
        if hasattr(request, 'should_be_public') and request.should_be_public:
            self._set_public_schema(request, public_schema)
            return None

        # Check if path should be public
        if request.path in self.PUBLIC_PATHS:
            self._set_public_schema(request, public_schema)
            return None

        # Check if any public path matches (for paths with parameters)
        for public_path in self.PUBLIC_PATHS:
            if request.path.startswith(public_path):
                self._set_public_schema(request, public_schema)
                return None

        # Force public schema for main/public domain and admin/health routes
        if (
            host in self.PUBLIC_HOSTS
            or request.path.startswith("/admin/")
            or request.path.startswith("/health/")
            or request.path.startswith("/healthz/")
        ):
            self._set_public_schema(request, public_schema)
            return None

        # Path-based tenant routing: /tenant/<schema>/...
        match = re.match(r"^/tenant/([^/]+)/", request.path)
        if match:
            schema_name = match.group(1)
            return self._set_tenant_schema(request, schema_name, public_schema)

        # For tenant subdomains that didn't match above, let parent handle
        if is_tenant_host:
            return super().process_request(request)

        # Default - set public schema
        self._set_public_schema(request, public_schema)
        return None

    def _set_public_schema(self, request, public_schema):
        """Sets the connection to the public schema"""
        connection.set_schema(public_schema)
        request.urlconf = getattr(settings, "PUBLIC_SCHEMA_URLCONF", "schoollibrary.public_urls")
        request.tenant = None

    def _set_tenant_schema(self, request, schema_name, public_schema):
        """Sets the connection to a specific tenant schema"""
        try:
            TenantModel = get_tenant_model()
            tenant = TenantModel.objects.get(schema_name=schema_name)
            connection.set_tenant(tenant)
            request.tenant = tenant
            request.urlconf = "schoollibrary.urls"
            return None
        except Exception:
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
                from django.http import HttpResponse
                return HttpResponse(
                    "<h1>System Initializing</h1><p>The database tables are being created. Please refresh this page in 1 minute.</p>",
                    status=503
                )
# tenants/middleware.py

from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse


class SuperAdminMiddleware:
    """Middleware to protect super admin routes"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Super admin protected paths
        protected_paths = [
            '/tenants/super-admin/',
            '/super-admin/',
            '/admin/tenants/',
        ]
        
        # Check if request path is protected
        is_protected = any(request.path.startswith(path) for path in protected_paths)
        
        if is_protected:
            # Not authenticated
            if not request.user.is_authenticated:
                messages.error(request, 'Please login to access the admin area')
                return redirect('/login/')
            
            # Not superuser
            if not request.user.is_superuser:
                messages.error(request, 'Access denied. Super admin privileges required.')
                return redirect('/app/dashboard/')
        
        return self.get_response(request)