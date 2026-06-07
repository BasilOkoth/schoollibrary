# digitallibrary/middleware.py

import re
import logging

from django.db import connection
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

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
    "/tenants/super-admin/",
    "/tenants/super-admin/dashboard/",
    "/tenants/secure-admin/",
]


def is_public_path(path):
    """
    Paths that should not require tenant resolution.
    Important for Render health checks, static/public routes,
    Django admin, and the central Super Admin dashboard.
    """
    return any(path == p or path.startswith(p) for p in PUBLIC_PATHS if p != "/")


# ============================================================
# DATABASE ERROR HANDLING
# ============================================================

class ProgrammingErrorMiddleware(MiddlewareMixin):
    """Handle programming errors gracefully."""

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
    """Handle admin access on public schema."""

    def process_request(self, request):
        if request.path.startswith("/admin/"):
            if getattr(connection, "schema_name", "public") == "public":
                return None

        return None


# ============================================================
# STRIP TENANT SCHEMA FROM PATH
# ============================================================

class StripTenantSchemaMiddleware(MiddlewareMixin):
    """
    Extract tenant schema from URLs such as:
    /tenant/nyaneje/
    /tenant/nyaneje/app/

    Super Admin must not be treated as a school tenant.
    """

    RESERVED_TENANT_SLUGS = {
        "super-admin",
        "secure-admin",
        "admin",
        "public",
        "login",
        "logout",
        "static",
        "media",
    }

    def process_request(self, request):
        if is_public_path(request.path):
            return None

        path = request.path or ""

        if path.startswith("/tenant/super-admin/"):
            connection.set_schema_to_public()
            request.tenant_schema = "public"
            return None

        path_parts = path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            tenant_schema = path_parts[1].strip()

            if tenant_schema in self.RESERVED_TENANT_SLUGS:
                connection.set_schema_to_public()
                request.tenant_schema = "public"
                return None

            request.tenant_schema = tenant_schema

            if hasattr(request, "session"):
                request.session["tenant_schema"] = tenant_schema
                request.session.modified = True

        return None


# ============================================================
# FORCE SESSION SAVE
# ============================================================

class ForceSessionMiddleware(MiddlewareMixin):
    """Ensure modified session is saved."""

    def process_response(self, request, response):
        if (
            hasattr(request, "session")
            and request.session is not None
            and request.session.modified
        ):
            request.session.save()

        return response


# ============================================================
# TENANT SESSION RESTORE
# ============================================================

class TenantSessionMiddleware(MiddlewareMixin):
    """
    Restore tenant from session.

    Important:
    This middleware ignores reserved names such as super-admin.
    """

    RESERVED_TENANT_SLUGS = {
        "super-admin",
        "secure-admin",
        "admin",
        "public",
        "login",
        "logout",
        "static",
        "media",
    }

    def process_request(self, request):
        if is_public_path(request.path):
            return None

        path = request.path or ""

        if path.startswith("/tenant/super-admin/"):
            connection.set_schema_to_public()
            request.tenant_schema = "public"
            return None

        tenant_schema = None

        if hasattr(request, "session"):
            tenant_schema = request.session.get("tenant_schema")

        if tenant_schema in self.RESERVED_TENANT_SLUGS:
            tenant_schema = None

            if hasattr(request, "session"):
                request.session.pop("tenant_schema", None)
                request.session.modified = True

            connection.set_schema_to_public()
            request.tenant_schema = "public"
            return None

        if tenant_schema and not hasattr(request, "tenant"):
            try:
                from tenants.models import School

                with schema_context("public"):
                    tenant = School.objects.get(schema_name=tenant_schema)

                request.tenant = tenant
                connection.set_tenant(tenant)

                logger.info("TenantSessionMiddleware restored tenant: %s", tenant_schema)

            except Exception as e:
                logger.error("TenantSessionMiddleware error: %s", e)
                connection.set_schema_to_public()
                request.tenant_schema = "public"

        return None

    def process_response(self, request, response):
        if not hasattr(request, "session"):
            return response

        tenant_schema = getattr(request, "tenant_schema", None)

        if tenant_schema and tenant_schema != "public":
            request.session["tenant_schema"] = tenant_schema
            request.session.modified = True

        elif hasattr(request, "tenant") and request.tenant:
            schema_name = getattr(request.tenant, "schema_name", None)

            if schema_name and schema_name not in self.RESERVED_TENANT_SLUGS:
                request.session["tenant_schema"] = schema_name
                request.session.modified = True

        return response


# ============================================================
# FORCE TENANT FROM URL OR SESSION
# ============================================================

class ForceTenantMiddleware(MiddlewareMixin):
    """
    Force tenant from URL or session.

    Important:
    Super Admin is not a school tenant.
    """

    RESERVED_TENANT_SLUGS = {
        "super-admin",
        "secure-admin",
        "admin",
        "public",
        "login",
        "logout",
        "static",
        "media",
    }

    def process_request(self, request):
        if is_public_path(request.path):
            return None

        path = request.path or ""

        if path.startswith("/tenant/super-admin/"):
            connection.set_schema_to_public()
            request.tenant_schema = "public"
            return None

        tenant_schema = None

        path_parts = path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            tenant_schema = path_parts[1].strip()

            if hasattr(request, "session"):
                request.session["tenant_schema"] = tenant_schema
                request.session.modified = True

        elif hasattr(request, "session"):
            tenant_schema = request.session.get("tenant_schema")

        if tenant_schema in self.RESERVED_TENANT_SLUGS:
            connection.set_schema_to_public()
            request.tenant_schema = "public"

            if hasattr(request, "session"):
                request.session.pop("tenant_schema", None)
                request.session.modified = True

            return None

        if tenant_schema and not hasattr(request, "tenant"):
            try:
                from tenants.models import School

                with schema_context("public"):
                    tenant = School.objects.get(schema_name=tenant_schema)

                request.tenant = tenant
                connection.set_tenant(tenant)

                logger.info("ForceTenantMiddleware set tenant: %s", tenant_schema)

            except Exception as e:
                logger.error("ForceTenantMiddleware error: %s", e)
                connection.set_schema_to_public()
                request.tenant_schema = "public"

        return None


# ============================================================
# FINAL TENANT SAFETY CHECK
# ============================================================

class EnsureTenantMiddleware(MiddlewareMixin):
    """
    Final tenant safety check.

    Prevents reserved names such as super-admin from becoming tenants.
    """

    RESERVED_TENANT_SLUGS = {
        "super-admin",
        "secure-admin",
        "admin",
        "public",
        "login",
        "logout",
        "static",
        "media",
    }

    def process_request(self, request):
        if is_public_path(request.path):
            return None

        path = request.path or ""

        if path.startswith("/tenant/super-admin/"):
            connection.set_schema_to_public()
            request.tenant_schema = "public"
            return None

        if "/tenant/" not in path:
            return None

        tenant_schema = None

        path_parts = path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            tenant_schema = path_parts[1].strip()

            if hasattr(request, "session"):
                request.session["tenant_schema"] = tenant_schema
                request.session.modified = True

        elif hasattr(request, "session"):
            tenant_schema = request.session.get("tenant_schema")

        if tenant_schema in self.RESERVED_TENANT_SLUGS:
            connection.set_schema_to_public()
            request.tenant_schema = "public"

            if hasattr(request, "session"):
                request.session.pop("tenant_schema", None)
                request.session.modified = True

            return None

        if tenant_schema and not hasattr(request, "tenant"):
            try:
                from tenants.models import School

                with schema_context("public"):
                    tenant = School.objects.get(schema_name=tenant_schema)

                request.tenant = tenant
                connection.set_tenant(tenant)

            except Exception as e:
                logger.error("EnsureTenantMiddleware error: %s", e)
                connection.set_schema_to_public()
                request.tenant_schema = "public"

        return None


# ============================================================
# RESET SCHEMA BEFORE SESSION SAVE
# ============================================================

class PublicSchemaBeforeSessionSaveMiddleware:
    """
    Reset schema to public before Django SessionMiddleware saves the session.

    This keeps Django admin happy because Django sessions are stored in public.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if hasattr(request, "session"):
                connection.set_schema_to_public()
        except Exception as e:
            logger.warning("Could not reset schema to public before session save: %s", e)

        return response


# ============================================================
# RESTORE AUTHENTICATED TENANT USER
# ============================================================

class TenantAuthenticatedUserMiddleware:
    """
    Re-loads the authenticated user from the correct tenant schema.

    This fixes cases where Django AuthenticationMiddleware checks the session
    before the tenant user can be resolved correctly, causing login_required()
    to redirect authenticated tenant users back to login.
    """

    RESERVED_TENANT_SLUGS = {
        "super-admin",
        "secure-admin",
        "admin",
        "public",
        "login",
        "logout",
        "static",
        "media",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            path = request.path or ""

            if path.startswith("/tenant/super-admin/"):
                connection.set_schema_to_public()
                request.tenant_schema = "public"
                return self.get_response(request)

            match = re.match(r"^/tenant/([^/]+)/", path)

            if match and hasattr(request, "session"):
                tenant_schema = match.group(1).strip()

                if tenant_schema in self.RESERVED_TENANT_SLUGS:
                    connection.set_schema_to_public()
                    request.tenant_schema = "public"
                    return self.get_response(request)

                current_user = getattr(request, "user", None)

                is_already_authenticated = (
                    current_user is not None
                    and current_user.is_authenticated
                )

                if not is_already_authenticated:
                    user_id = request.session.get("_auth_user_id")

                    if user_id:
                        User = get_user_model()

                        with schema_context(tenant_schema):
                            user = User.objects.filter(
                                pk=user_id,
                                is_active=True,
                            ).first()

                            if user:
                                user.backend = request.session.get(
                                    "_auth_user_backend",
                                    "django.contrib.auth.backends.ModelBackend",
                                )

                                request.user = user

                                print(
                                    f"✅ TenantAuthenticatedUserMiddleware restored user "
                                    f"{user.username} in schema {tenant_schema}"
                                )

        except Exception as e:
            logger.warning("TenantAuthenticatedUserMiddleware error: %s", e)

        return self.get_response(request)


# ============================================================
# PATH-BASED TENANT SCHEMA SWITCHING
# ============================================================

class PathTenantSchemaMiddleware:
    """
    Switch schema early based on /tenant/<schema>/ path.

    This must run BEFORE AuthenticationMiddleware so Django loads
    request.user from the tenant schema, not public.

    Important:
    Super Admin is NOT a school tenant.
    Therefore /tenant/super-admin/app/ redirects to /tenants/super-admin/.
    """

    RESERVED_TENANT_SLUGS = {
        "super-admin",
        "secure-admin",
        "admin",
        "public",
        "login",
        "logout",
        "static",
        "media",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            from django.shortcuts import redirect
            from django.http import JsonResponse

            path = request.path or ""

            # ------------------------------------------------------------
            # 1. Prevent Super Admin from being treated as a school tenant
            # ------------------------------------------------------------
            if path.startswith("/tenant/super-admin/"):
                connection.set_schema_to_public()
                request.tenant_schema = "public"

                # Stop notification polling from treating super-admin as tenant.
                if "/api/" in path:
                    return JsonResponse({
                        "count": 0,
                        "notifications": [],
                    })

                return redirect("/tenants/super-admin/")

            # ------------------------------------------------------------
            # 2. Normal path-based tenant handling
            # Example: /tenant/nyaneje/app/
            # ------------------------------------------------------------
            match = re.match(r"^/tenant/([^/]+)/", path)

            if match:
                tenant_schema = match.group(1).strip()

                if tenant_schema in self.RESERVED_TENANT_SLUGS:
                    connection.set_schema_to_public()
                    request.tenant_schema = "public"
                    return redirect("/app/")

                connection.set_schema(tenant_schema)
                request.tenant_schema = tenant_schema

                if hasattr(request, "session"):
                    request.session["tenant_schema"] = tenant_schema
                    request.session.modified = True

                print(f"✅ PathTenantSchemaMiddleware switched to {tenant_schema}")

        except Exception as e:
            logger.warning("PathTenantSchemaMiddleware error: %s", e)

            try:
                connection.set_schema_to_public()
                request.tenant_schema = "public"
            except Exception:
                pass

        return self.get_response(request)
