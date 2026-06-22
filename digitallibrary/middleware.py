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
    "www",
}


PUBLIC_HOSTS = {
    "localhost",
    "127.0.0.1",
    "shulehub.org",
    "www.shulehub.org",
    "schoollibrary-production-test.onrender.com",
}


def clean_host(host):
    """
    Remove port and normalize host.
    Example:
    ngege.shulehub.org:443 -> ngege.shulehub.org
    """
    return (host or "").split(":")[0].strip().lower()


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


def force_public_schema(request=None):
    """
    Safely switch request/connection to public schema.
    """
    try:
        connection.set_schema_to_public()
        if request is not None:
            request.tenant_schema = "public"
    except Exception as error:
        logger.warning("Could not force public schema: %s", error)


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
            force_public_schema(request)

        return None


# ============================================================
# DOMAIN + PATH-BASED TENANT SCHEMA SWITCHING
# ============================================================

class PathTenantSchemaMiddleware:
    """
    Switch schema early based on either:

    1. Subdomain/domain-based tenancy:
       https://ngege.shulehub.org/app/

    2. Path-based tenancy:
       https://shulehub.org/tenant/ngegemixed/app/

    This middleware must run AFTER SessionMiddleware and BEFORE
    AuthenticationMiddleware.

    Important:
    - For subdomains, the tenant comes from tenants_domain.domain.
    - For path-based URLs, the tenant comes from /tenant/<schema>/...
    - Do NOT store tenant_schema in session.
    - Validate the tenant from the public schema first.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _switch_to_tenant(self, request, tenant, source="unknown"):
        """
        Safely switch to a validated tenant.
        """
        connection.set_tenant(tenant)
        request.tenant = tenant
        request.tenant_schema = tenant.schema_name

        logger.info(
            "PathTenantSchemaMiddleware switched by %s to tenant schema: %s",
            source,
            tenant.schema_name,
        )

    def _get_tenant_by_domain(self, host):
        """
        Look up tenant using the public tenants_domain table.
        """
        from tenants.models import Domain

        with schema_context("public"):
            domain = (
                Domain.objects
                .select_related("tenant")
                .filter(
                    domain=host,
                    tenant__is_active=True,
                )
                .first()
            )

            if domain:
                return domain.tenant

        return None

    def _get_tenant_by_schema(self, schema_name):
        """
        Look up tenant using public tenants_school.schema_name.
        """
        from tenants.models import School

        with schema_context("public"):
            tenant = (
                School.objects
                .filter(
                    schema_name=schema_name,
                    is_active=True,
                )
                .first()
            )

        return tenant

    def __call__(self, request):
        try:
            from django.shortcuts import redirect
            from django.http import JsonResponse

            path = request.path or "/"
            host = clean_host(request.get_host())

            # ------------------------------------------------------------
            # 1. Public admin/system paths must always stay public
            # ------------------------------------------------------------
            if is_public_path(path):
                force_public_schema(request)
                return self.get_response(request)

            # ------------------------------------------------------------
            # 2. Prevent wrong super-admin tenant URL
            # Example: /tenant/super-admin/app/
            # ------------------------------------------------------------
            if path.startswith("/tenant/super-admin/"):
                force_public_schema(request)

                if "/api/" in path:
                    return JsonResponse(
                        {
                            "count": 0,
                            "notifications": [],
                        }
                    )

                return redirect("/tenants/super-admin/")

            # ------------------------------------------------------------
            # 3. Try domain/subdomain-based tenant first
            # Example: https://ngege.shulehub.org/app/
            # ------------------------------------------------------------
            if host and host not in PUBLIC_HOSTS:
                tenant = self._get_tenant_by_domain(host)

                if tenant:
                    self._switch_to_tenant(
                        request,
                        tenant,
                        source=f"domain {host}",
                    )
                    return self.get_response(request)

                logger.warning(
                    "Host '%s' was requested but no active tenant domain was found.",
                    host,
                )

            # ------------------------------------------------------------
            # 4. Detect path-based tenant
            # Example: /tenant/nyandago/app/
            # ------------------------------------------------------------
            match = re.match(r"^/tenant/([^/]+)/", path)

            if not match:
                # No tenant in URL and no valid subdomain tenant.
                force_public_schema(request)
                return self.get_response(request)

            tenant_schema = match.group(1).strip().lower()

            # ------------------------------------------------------------
            # 5. Protect reserved words
            # ------------------------------------------------------------
            if tenant_schema in RESERVED_TENANT_SLUGS:
                force_public_schema(request)
                return redirect("/app/")

            # ------------------------------------------------------------
            # 6. Validate tenant from public schema
            # ------------------------------------------------------------
            tenant = self._get_tenant_by_schema(tenant_schema)

            if not tenant:
                logger.warning(
                    "Tenant schema '%s' was requested but does not exist or is inactive.",
                    tenant_schema,
                )

                force_public_schema(request)
                return redirect("/app/")

            # ------------------------------------------------------------
            # 7. Safely switch to path-based tenant
            # ------------------------------------------------------------
            self._switch_to_tenant(
                request,
                tenant,
                source=f"path {tenant_schema}",
            )

        except Exception as error:
            logger.warning("PathTenantSchemaMiddleware error: %s", error)

            force_public_schema(request)

        return self.get_response(request)
