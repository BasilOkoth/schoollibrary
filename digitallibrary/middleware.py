# digitallibrary/middleware.py

import re
import logging

from django.db import connection
from django.utils.deprecation import MiddlewareMixin
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


PUBLIC_PATHS = [
    "/",
    "/healthz/",
    "/health/",
    "/admin/",
    "/static/",
    "/media/",
    "/login/",
    "/logout/",
    "/favicon.ico",
    "/smart-login/",
    "/accounts/login/",
    "/password-reset/",
    "/password-reset/done/",
    "/password-reset-complete/",
    "/tenants/super-admin/",
    "/tenants/super-admin/dashboard/",
    "/tenants/secure-admin/",
    "/superadmin/",
    "/mpesa/",
]


RESERVED_TENANT_SLUGS = {
    "super-admin",
    "secure-admin",
    "admin",
    "public",
    "login",
    "logout",
    "static",
    "media",
    "app",
    "library",
    "tenants",
    "superadmin",
    "mpesa",
}


def is_public_path(path):
    """
    Paths that should stay on the public schema.

    These include Render health checks, static/media files, Django admin,
    public login/logout, password reset, and super-admin tenant management.
    """
    path = path or "/"

    return any(
        path == public_path or path.startswith(public_path)
        for public_path in PUBLIC_PATHS
        if public_path != "/"
    )


# ============================================================
# DATABASE ERROR HANDLING
# ============================================================

class ProgrammingErrorMiddleware(MiddlewareMixin):
    """
    Handle database programming errors gracefully.

    This prevents users from seeing raw database tracebacks in production.
    """

    def process_exception(self, request, exception):
        from django.db import ProgrammingError
        from django.http import HttpResponse

        if isinstance(exception, ProgrammingError):
            logger.error("ProgrammingError: %s", exception)

            return HttpResponse(
                "<h1>Database Error</h1><p>Please try again later.</p>",
                status=500,
            )

        return None


# ============================================================
# PUBLIC ADMIN HANDLING
# ============================================================

class PublicAdminMiddleware(MiddlewareMixin):
    """
    Keep Django admin and super-admin pages on the public schema.
    """

    def process_request(self, request):
        path = request.path or ""

        if (
            path.startswith("/admin/")
            or path.startswith("/tenants/")
            or path.startswith("/superadmin/")
            or path.startswith("/login/")
            or path.startswith("/logout/")
            or path.startswith("/smart-login/")
        ):
            try:
                connection.set_schema_to_public()
                request.tenant_schema = "public"
            except Exception as e:
                logger.warning("Could not force public schema: %s", e)

        return None


# ============================================================
# PATH-BASED TENANT SCHEMA SWITCHING
# ============================================================

class PathTenantSchemaMiddleware:
    """
    Switch schema early based on URLs such as:

        /tenant/nyandago/app/
        /tenant/nyaneje/app/dashboard/
        /tenant/orero/app/login/

    This middleware must run AFTER SessionMiddleware and BEFORE
    AuthenticationMiddleware.

    Important:
    - The tenant comes from the URL path.
    - Do NOT store tenant_schema in session.
    - Do NOT blindly call connection.set_schema(schema_name).
    - Validate the tenant from the public schema first.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            from django.shortcuts import redirect
            from django.http import JsonResponse
            from tenants.models import School

            path = request.path or "/"

            # ------------------------------------------------------------
            # 1. Public paths stay on public schema
            # ------------------------------------------------------------
            if is_public_path(path):
                connection.set_schema_to_public()
                request.tenant_schema = "public"
                return self.get_response(request)

            # ------------------------------------------------------------
            # 2. Prevent wrong super-admin tenant URL
            # Example: /tenant/super-admin/app/
            # ------------------------------------------------------------
            if path.startswith("/tenant/super-admin/"):
                connection.set_schema_to_public()
                request.tenant_schema = "public"

                if "/api/" in path:
                    return JsonResponse(
                        {
                            "count": 0,
                            "notifications": [],
                        }
                    )

                return redirect("/tenants/super-admin/")

            # ------------------------------------------------------------
            # 3. Detect normal tenant path
            # Example: /tenant/nyandago/app/
            # ------------------------------------------------------------
            match = re.match(r"^/tenant/([^/]+)/", path)

            if not match:
                # No tenant in URL, so remain public.
                connection.set_schema_to_public()
                request.tenant_schema = "public"
                return self.get_response(request)

            tenant_schema = match.group(1).strip().lower()

            # ------------------------------------------------------------
            # 4. Protect reserved words
            # ------------------------------------------------------------
            if tenant_schema in RESERVED_TENANT_SLUGS:
                connection.set_schema_to_public()
                request.tenant_schema = "public"
                return redirect("/app/")

            # ------------------------------------------------------------
            # 5. Validate tenant from public schema
            # ------------------------------------------------------------
            with schema_context("public"):
                tenant = (
                    School.objects
                    .filter(
                        schema_name=tenant_schema,
                        is_active=True,
                    )
                    .first()
                )

            if not tenant:
                logger.warning(
                    "Tenant schema '%s' was requested but does not exist or is inactive.",
                    tenant_schema,
                )

                connection.set_schema_to_public()
                request.tenant_schema = "public"

                return redirect("/app/")

            # ------------------------------------------------------------
            # 6. Safely switch to tenant
            # ------------------------------------------------------------
            connection.set_tenant(tenant)
            request.tenant = tenant
            request.tenant_schema = tenant.schema_name

            logger.info(
                "PathTenantSchemaMiddleware switched to tenant schema: %s",
                tenant.schema_name,
            )

        except Exception as e:
            logger.warning("PathTenantSchemaMiddleware error: %s", e)

            try:
                connection.set_schema_to_public()
                request.tenant_schema = "public"
            except Exception:
                pass

        return self.get_response(request)
