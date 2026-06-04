# digitallibrary/middleware.py

import re
import logging

from django.db import connection
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
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
    """
    Extract tenant schema from URLs such as:
    /tenant/nyaneje/
    /tenant/nyaneje/app/
    """

    def process_request(self, request):
        if is_public_path(request.path):
            return None

        path_parts = request.path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            tenant_schema = path_parts[1]
            request.tenant_schema = tenant_schema

            if hasattr(request, "session"):
                request.session["tenant_schema"] = tenant_schema
                request.session.modified = True

        return None


class ForceSessionMiddleware(MiddlewareMixin):
    """Ensure modified session is saved"""

    def process_response(self, request, response):
        if (
            hasattr(request, "session")
            and request.session is not None
            and request.session.modified
        ):
            request.session.save()

        return response


class TenantSessionMiddleware(MiddlewareMixin):
    """Restore tenant from session"""

    def process_request(self, request):
        if is_public_path(request.path):
            return None

        tenant_schema = None

        if hasattr(request, "session"):
            tenant_schema = request.session.get("tenant_schema")

        if tenant_schema and not hasattr(request, "tenant"):
            try:
                from tenants.models import School

                tenant = School.objects.get(schema_name=tenant_schema)

                request.tenant = tenant
                connection.set_tenant(tenant)

                logger.info(
                    f"TenantSessionMiddleware restored tenant: {tenant_schema}"
                )

            except Exception as e:
                logger.error(
                    f"TenantSessionMiddleware error: {e}"
                )

        return None

    def process_response(self, request, response):

        if not hasattr(request, "session"):
            return response

        if hasattr(request, "tenant_schema"):
            request.session["tenant_schema"] = request.tenant_schema
            request.session.modified = True

        elif hasattr(request, "tenant") and request.tenant:
            request.session["tenant_schema"] = request.tenant.schema_name
            request.session.modified = True

        return response


class ForceTenantMiddleware(MiddlewareMixin):
    """Force tenant from URL or session"""

    def process_request(self, request):

        if is_public_path(request.path):
            return None

        tenant_schema = None

        if hasattr(request, "session"):
            tenant_schema = request.session.get("tenant_schema")

        if not tenant_schema:

            path_parts = request.path.strip("/").split("/")

            if len(path_parts) >= 2 and path_parts[0] == "tenant":
                tenant_schema = path_parts[1]

                if hasattr(request, "session"):
                    request.session["tenant_schema"] = tenant_schema
                    request.session.modified = True

        if tenant_schema and not hasattr(request, "tenant"):

            try:
                from tenants.models import School

                tenant = School.objects.get(
                    schema_name=tenant_schema
                )

                request.tenant = tenant
                connection.set_tenant(tenant)

                logger.info(
                    f"ForceTenantMiddleware set tenant: {tenant_schema}"
                )

            except Exception as e:
                logger.error(
                    f"ForceTenantMiddleware error: {e}"
                )

        return None


class EnsureTenantMiddleware(MiddlewareMixin):
    """Final tenant safety check"""

    def process_request(self, request):

        if is_public_path(request.path):
            return None

        if "/tenant/" not in request.path:
            return None

        tenant_schema = None

        if hasattr(request, "session"):
            tenant_schema = request.session.get("tenant_schema")

        if not tenant_schema:

            path_parts = request.path.strip("/").split("/")

            if len(path_parts) >= 2 and path_parts[0] == "tenant":
                tenant_schema = path_parts[1]

                if hasattr(request, "session"):
                    request.session["tenant_schema"] = tenant_schema
                    request.session.modified = True

        if tenant_schema and not hasattr(request, "tenant"):

            try:
                from tenants.models import School

                tenant = School.objects.get(
                    schema_name=tenant_schema
                )

                request.tenant = tenant
                connection.set_tenant(tenant)

            except Exception as e:
                logger.error(
                    f"EnsureTenantMiddleware error: {e}"
                )

        return None
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class PublicSchemaBeforeSessionSaveMiddleware:
    """
    Reset schema to public before Django SessionMiddleware saves the session.

    This keeps Django admin happy because we still use the real
    django.contrib.sessions.middleware.SessionMiddleware in settings.py.
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
import re
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


class TenantAuthenticatedUserMiddleware:
    """
    Re-loads the authenticated user from the correct tenant schema.

    This fixes cases where Django AuthenticationMiddleware checks the session
    before the tenant user can be resolved correctly, causing login_required()
    to redirect authenticated tenant users back to login.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            path = request.path or ""
            match = re.match(r"^/tenant/([^/]+)/", path)

            if match and hasattr(request, "session"):
                tenant_schema = match.group(1)

                current_user = getattr(request, "user", None)
                is_already_authenticated = (
                    current_user is not None and current_user.is_authenticated
                )

                if not is_already_authenticated:
                    user_id = request.session.get("_auth_user_id")

                    if user_id:
                        User = get_user_model()

                        with schema_context(tenant_schema):
                            user = User.objects.filter(pk=user_id, is_active=True).first()

                            if user:
                                user.backend = request.session.get(
                                    "_auth_user_backend",
                                    "django.contrib.auth.backends.ModelBackend"
                                )

                                request.user = user
                                print(
                                    f"✅ TenantAuthenticatedUserMiddleware restored user "
                                    f"{user.username} in schema {tenant_schema}"
                                )

        except Exception as e:
            logger.warning("TenantAuthenticatedUserMiddleware error: %s", e)

        return self.get_response(request)
import re
import logging
from django.db import connection

logger = logging.getLogger(__name__)


class PathTenantSchemaMiddleware:
    """
    Switch schema early based on /tenant/<schema>/ path.

    This must run BEFORE AuthenticationMiddleware so Django loads
    request.user from the tenant schema, not public.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            path = request.path or ""
            match = re.match(r"^/tenant/([^/]+)/", path)

            if match:
                tenant_schema = match.group(1)
                connection.set_schema(tenant_schema)
                request.tenant_schema = tenant_schema
                print(f"✅ PathTenantSchemaMiddleware switched to {tenant_schema}")

        except Exception as e:
            logger.warning("PathTenantSchemaMiddleware error: %s", e)

        return self.get_response(request)
