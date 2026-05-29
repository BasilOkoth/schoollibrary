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

        # 1. Admin/health/smart-login always use public schema
        if (
            request.path.startswith("/admin/")
            or request.path.startswith("/health/")
            or request.path.startswith("/healthz/")
            or request.path.startswith("/smart-login/")
        ):
            self._set_public_schema(request, public_schema)
            return None

        # 2. Path-based tenant routing wins
        match = re.match(r"^/tenant/([^/]+)/", request.path)
        if match:
            schema_name = match.group(1)
            try:
                if hasattr(request, 'session'):
                    request.session['_tenant_schema'] = schema_name
            except Exception:
                pass
            return self._set_tenant_schema(request, schema_name, public_schema)

        # 3. /app/... on public host → redirect to /tenant/<schema>/app/...
        #    when session remembers a tenant (fixes {% url %} tag resolutions)
        if self._is_public_host(host) and request.path.startswith('/app/'):
            try:
                if hasattr(request, 'session'):
                    tenant_schema = request.session.get('_tenant_schema')
                    if tenant_schema:
                        suffix = request.path[4:]   # strip /app
                        new_url = f'/tenant/{tenant_schema}/app{suffix}'
                        if request.GET:
                            new_url += '?' + request.GET.urlencode()
                        if request.method == 'GET':
                            return redirect(new_url)
                        else:
                            resp = HttpResponseRedirect(new_url)
                            resp.status_code = 307
                            return resp
            except Exception:
                pass

        # 4. Public hosts use public schema
        if self._is_public_host(host):
            self._set_public_schema(request, public_schema)
            return None

        # 5. Subdomain-based routing (fallback)
        return super().process_request(request)

    def _set_public_schema(self, request, public_schema):
        connection.set_schema(public_schema)
        request.urlconf = getattr(settings, "PUBLIC_SCHEMA_URLCONF", "schoollibrary.urls")
        try:
            from tenants.models import School
            request.tenant = School.objects.filter(schema_name=public_schema).first() or School.objects.first()
        except Exception:
            request.tenant = None

    def _set_tenant_schema(self, request, schema_name, public_schema):
        try:
            from tenants.models import School
            tenant = School.objects.get(schema_name=schema_name)
            connection.set_tenant(tenant)
            request.tenant = tenant
            request.urlconf = "schoollibrary.urls"
            # Use 'digitallibrary' namespace for {% url %} reversal so
            # tenant_schema arg is not required — session redirect handles routing
            request.current_app = 'digitallibrary'
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
                    {"error": "System setup in progress",
                     "message": "Database still initializing. Refresh in a minute.",
                     "setup": True},
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
