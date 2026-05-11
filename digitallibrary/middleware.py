# digitallibrary/middleware.py

import re

from django.conf import settings
from django.db import ProgrammingError, connection
from django.http import JsonResponse
from django.shortcuts import render
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name


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
        connection.set_schema(public_schema)
        request.urlconf = getattr(settings, "PUBLIC_SCHEMA_URLCONF", "schoollibrary.urls")

        try:
            from tenants.models import School

            request.tenant = School.objects.get(schema_name=public_schema)
        except Exception:
            request.tenant = None

    def _set_tenant_schema(self, request, schema_name, public_schema):
        try:
            from tenants.models import School

            tenant = School.objects.get(schema_name=schema_name)
            connection.set_tenant(tenant)

            request.tenant = tenant
            request.urlconf = "schoollibrary.urls"

            return None

        except Exception:
            self._set_public_schema(request, public_schema)
            return None


class StripTenantSchemaMiddleware:
    """
    Removes the 'tenant_schema' URL kwarg before it reaches view functions.
    Useful when using URLs like /tenant/<schema>/app/... but views do not accept tenant_schema.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        view_kwargs.pop("tenant_schema", None)
        return None


class ProgrammingErrorMiddleware:
    """
    Catches ProgrammingError caused by missing tenant/public tables
    and returns a friendly setup message instead of a raw 500 error.
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

            if request.path.startswith("/admin/") or request.path.startswith("/health/") or request.path.startswith("/healthz/"):
                raise

            if (
                request.path.startswith("/api/")
                or request.path.startswith("/app/api/")
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            ):
                return JsonResponse(
                    {
                        "error": "System setup in progress",
                        "message": "Please wait for system initialization.",
                        "setup": True,
                    },
                    status=503,
                )

            return render(
                request,
                "digitallibrary/setup_required.html",
                {
                    "message": "School system is being initialized. Please wait a moment.",
                },
                status=503,
            )
