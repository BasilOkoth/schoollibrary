# digitallibrary/middleware.py

import re
import logging

from django.contrib import messages
from django.db import connection
from django.shortcuts import redirect
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


def get_tenant_schema_from_path(path):
    """
    Extract tenant schema from:

        /tenant/miyuga/app/exams/
    """
    path = path or ""

    match = re.match(r"^/tenant/([^/]+)/", path)

    if match:
        schema_name = match.group(1).strip().lower()

        if schema_name and schema_name != "public":
            return schema_name

    return None


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
            tenant_schema = get_tenant_schema_from_path(path)

            if not tenant_schema:
                force_public_schema(request)
                return self.get_response(request)

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


# ============================================================
# SUBSCRIPTION FEATURE BLOCKING
# ============================================================

class SubscriptionGateMiddleware:
    """
    Blocks selected tenant features when the school subscription account
    is marked as blocked.

    This uses the public schema billing table:
        tenants_schoolsubscriptionaccount

    It checks:
    - critical_features_blocked=True
    - status='BLOCKED'
    - status='SUSPENDED'
    - computed_status() if available
    """

    # Pages that should remain open even when blocked.
    # Billing must remain open so the school can see the issue and pay.
    ALLOWED_PATH_KEYWORDS = [
        "/billing/",
        "/login/",
        "/logout/",
        "/smart-login/",
        "/api/notifications/",
        "/parent/login/",
        "/parent/otp/",
        "/admin/",
        "/static/",
        "/media/",
        "/mpesa/",
    ]

    # Modules to block when critical_features_blocked=True.
    BLOCKED_PATH_KEYWORDS = [
        "/sms/",
        "/reports/",
        "/report-cards/",
        "/marks/",
        "/exams/",
        "/exams/create/",
        "/performance/",
        "/bulk-enter-results/",
        "/bulk-results/",
        "/enter-results/",
        "/results/",
        "/students/",
        "/subjects/",
        "/student-subjects/",
        "/timetable/",
        "/tv/",
        "/print/",
        "/resources/add/",
        "/resources/upload/",
        "/upload/",
        "/fees/",
        "/payments/",
        "/users/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        block_response = self.check_subscription_gate(request)

        if block_response:
            return block_response

        return self.get_response(request)

    def get_tenant_schema(self, request):
        """
        Resolve tenant schema from:
        - request.tenant_schema
        - request.tenant.schema_name
        - /tenant/<schema>/app/... path
        """
        tenant_schema = getattr(request, "tenant_schema", None)

        if tenant_schema and tenant_schema != "public":
            return tenant_schema

        tenant = getattr(request, "tenant", None)
        tenant_schema = getattr(tenant, "schema_name", None)

        if tenant_schema and tenant_schema != "public":
            return tenant_schema

        tenant_schema = get_tenant_schema_from_path(request.path)

        if tenant_schema and tenant_schema != "public":
            return tenant_schema

        return None

    def get_app_path(self, request, tenant_schema):
        """
        Convert tenant path to app path.

        Example:
            /tenant/miyuga/app/exams/ -> /exams/
            /tenant/miyuga/app/timetable/ -> /timetable/
            /app/exams/ -> /exams/
        """
        path = request.path or ""

        tenant_prefix = f"/tenant/{tenant_schema}/app"

        if path.startswith(tenant_prefix):
            app_path = path.replace(tenant_prefix, "", 1)

            if not app_path.startswith("/"):
                app_path = "/" + app_path

            return app_path or "/"

        if path.startswith("/app/"):
            app_path = path.replace("/app", "", 1)

            if not app_path.startswith("/"):
                app_path = "/" + app_path

            return app_path or "/"

        return path

    def is_allowed_path(self, app_path):
        return any(
            keyword in app_path
            for keyword in self.ALLOWED_PATH_KEYWORDS
        )

    def is_blockable_path(self, app_path):
        return any(
            keyword in app_path
            for keyword in self.BLOCKED_PATH_KEYWORDS
        )

    def school_subscription_is_blocked(self, tenant_schema):
        """
        Read the subscription account from the public schema.
        """
        try:
            with schema_context("public"):
                from tenants.models import School, SchoolSubscriptionAccount

                school = (
                    School.objects
                    .filter(schema_name=tenant_schema)
                    .first()
                )

                if not school:
                    return False

                account = (
                    SchoolSubscriptionAccount.objects
                    .filter(school=school)
                    .first()
                )

                if not account:
                    return False

                if account.critical_features_blocked:
                    return True

                if account.status in ["BLOCKED", "SUSPENDED"]:
                    return True

                if hasattr(account, "computed_status"):
                    computed_status = account.computed_status()

                    if computed_status in ["BLOCKED", "SUSPENDED"]:
                        return True

                return False

        except Exception as error:
            logger.warning(
                "SubscriptionGateMiddleware failed for tenant '%s': %s",
                tenant_schema,
                error,
            )
            return False

    def check_subscription_gate(self, request):
        tenant_schema = self.get_tenant_schema(request)

        if not tenant_schema:
            return None

        app_path = self.get_app_path(request, tenant_schema)

        # Never block allowed paths.
        if self.is_allowed_path(app_path):
            return None

        # Only block selected premium/critical modules.
        if not self.is_blockable_path(app_path):
            return None

        # Check billing status.
        if not self.school_subscription_is_blocked(tenant_schema):
            return None

        messages.error(
            request,
            (
                "This feature is temporarily blocked because the school's "
                "ShuleHub subscription requires attention. Please clear the "
                "subscription balance or contact ShuleHub support."
            ),
        )

        return redirect(f"/tenant/{tenant_schema}/app/billing/")
