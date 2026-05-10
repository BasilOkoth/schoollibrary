# digitallibrary/middleware.py

import re
from django.db import ProgrammingError, connection
from django.shortcuts import render
from django.http import JsonResponse
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name


class PublicAdminMiddleware(TenantMainMiddleware):
    """
    Handles:
    - shulehub.org and www.shulehub.org as public schema
    - /admin/ always as public schema
    - /tenant/<schema>/... as path-based tenant access
    - other domains using normal django-tenants domain routing
    """

    def process_request(self, request):
        host = request.get_host().split(":")[0].lower()
        public_schema = get_public_schema_name()

        # Force main domain and admin to public schema
        if host in ["shulehub.org", "www.shulehub.org"] or request.path.startswith("/admin/"):
            connection.set_schema(public_schema)

            try:
                from tenants.models import School
                request.tenant = School.objects.get(schema_name=public_schema)
            except Exception:
                request.tenant = None

            request.urlconf = "schoollibrary.urls"
            return None

        # Path-based tenant routing: /tenant/<schema>/...
        match = re.match(r"^/tenant/([^/]+)/", request.path)
        if match:
            schema_name = match.group(1)

            try:
                from tenants.models import School
                tenant = School.objects.get(schema_name=schema_name)

                connection.set_schema(schema_name)
                request.tenant = tenant
                request.urlconf = "schoollibrary.urls"

                return None

            except Exception:
                connection.set_schema(public_schema)
                request.tenant = None
                request.urlconf = "schoollibrary.urls"
                return None

        # Normal domain-based tenant routing
        return super().process_request(request)


class StripTenantSchemaMiddleware:
    """
    Removes the 'tenant_schema' URL kwarg before it reaches view functions.
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
    Catch ProgrammingError caused by missing tenant tables
    and show a friendly setup message.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)

        except ProgrammingError as e:
            error_msg = str(e)

            if "does not exist" in error_msg:
                if request.path.startswith("/admin/") or request.path.startswith("/healthz/"):
                    raise

                if request.path.startswith("/api/") or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse(
                        {
                            "error": "System setup in progress",
                            "message": "Please wait for system initialization",
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

            raise
