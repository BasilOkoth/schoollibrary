# digitallibrary/middleware.py

import logging
from django.db import connection
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


PUBLIC_PATHS = [
    "/",
    "/healthz/",
    "/admin/",
    "/static/",
    "/media/",
    "/login/",
    "/logout/",
    "/favicon.ico",
]


def is_public_path(path):
    """
    Paths that should not require tenant resolution.
    Important for Render health checks and static/public routes.
    """
    return any(path == p or path.startswith(p) for p in PUBLIC_PATHS if p != "/")


class ProgrammingErrorMiddleware(MiddlewareMixin):
    """Handle programming errors gracefully"""

    def process_exception(self, request, exception):
        from django.db import ProgrammingError
        from django.http import HttpResponse

        if isinstance(exception, ProgrammingError):
            logger.error(f"ProgrammingError: {exception}")
            return HttpResponse(
                "<h1>Database Error</h1><p>Please try again later.</p>",
                status=500,
            )

        return None


class PublicAdminMiddleware(MiddlewareMixin):
    """Handle admin access on public schema"""

    def process_request(self, request):
        if request.path.startswith("/admin/"):
            if getattr(connection, "schema_name", "public") == "public":
                return None
        return None


class StripTenantSchemaMiddleware(MiddlewareMixin):
    """Extract tenant schema from URLs such as /tenant/nyaneje/app/..."""

    def process_request(self, request):
        if is_public_path(request.path):
            return None

        path_parts = request.path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            tenant_schema = path_parts[1]
            request.tenant_schema = tenant_schema
            request.session["tenant_schema"] = tenant_schema
            request.session.modified = True

        return None


class ForceSessionMiddleware(MiddlewareMixin):
    """Ensure modified session is saved"""

    def process_response(self, request, response):
        if hasattr(request, "session") and request.session.modified:
            request.session.save()
        return response


class TenantSessionMiddleware(MiddlewareMixin):
    """Maintain tenant session across requests"""

    def process_request(self, request):
        if is_public_path(request.path):
            return None

        tenant_schema = request.session.get("tenant_schema")

        if tenant_schema and not hasattr(request, "tenant"):
            try:
                from tenants.models import School

                tenant = School.objects.get(schema_name=tenant_schema)
                request.tenant = tenant
                connection.set_tenant(tenant)
                logger.debug(f"TenantSessionMiddleware set tenant: {tenant_schema}")

            except Exception as e:
                logger.error(f"TenantSessionMiddleware error: {e}")

        return None

    def process_response(self, request, response):
        if hasattr(request, "tenant_schema"):
            request.session["tenant_schema"] = request.tenant_schema
            request.session.modified = True

        elif hasattr(request, "tenant") and request.tenant:
            request.session["tenant_schema"] = request.tenant.schema_name
            request.session.modified = True

        return response


class ForceTenantMiddleware(MiddlewareMixin):
    """Force tenant to be set from session or URL"""

    def process_request(self, request):
        if is_public_path(request.path):
            return None

        tenant_schema = request.session.get("tenant_schema")

        if not tenant_schema:
            path_parts = request.path.strip("/").split("/")

            if len(path_parts) >= 2 and path_parts[0] == "tenant":
                tenant_schema = path_parts[1]
                request.session["tenant_schema"] = tenant_schema
                request.session.modified = True

        if tenant_schema and not hasattr(request, "tenant"):
            try:
                from tenants.models import School

                tenant = School.objects.get(schema_name=tenant_schema)
                request.tenant = tenant
                connection.set_tenant(tenant)
                logger.info(f"ForceTenantMiddleware set tenant: {tenant_schema}")

            except Exception as e:
                logger.error(f"ForceTenantMiddleware error: {e}")

        return None


class EnsureTenantMiddleware(MiddlewareMixin):
    """Ensure tenant is set for tenant requests only"""

    def process_request(self, request):
        if is_public_path(request.path):
            return None

        if "/tenant/" not in request.path:
            return None

        tenant_schema = request.session.get("tenant_schema")

        if not tenant_schema:
            path_parts = request.path.strip("/").split("/")

            if len(path_parts) >= 2 and path_parts[0] == "tenant":
                tenant_schema = path_parts[1]
                request.session["tenant_schema"] = tenant_schema
                request.session.modified = True

        if tenant_schema and not hasattr(request, "tenant"):
            try:
                from tenants.models import School

                tenant = School.objects.get(schema_name=tenant_schema)
                request.tenant = tenant
                connection.set_tenant(tenant)

            except Exception as e:
                logger.error(f"EnsureTenantMiddleware error: {e}")

        return None
