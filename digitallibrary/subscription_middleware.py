# digitallibrary/subscription_middleware.py

from django.contrib import messages
from django.shortcuts import redirect
from django_tenants.utils import schema_context


PUBLIC_SCHEMA_NAME = "public"


# Pages that should still work even when a school is blocked.
# Important: billing must remain open so the school can pay.
ALLOWED_PATH_KEYWORDS = [
    "/login/",
    "/logout/",
    "/billing/",
    "/api/notifications/",
    "/parent/login/",
    "/parent/otp/",
    "/static/",
    "/media/",
]


# These are the modules you want to block when critical_features_blocked=True.
# You can add or remove modules here.
BLOCKED_MODULE_PREFIXES = [
    "/exams/",
    "/exams/create/",
    "/performance/",
    "/bulk-enter-results/",
    "/bulk-results/",
    "/enter-results/",
    "/results/",
    "/reports/",
    "/students/",
    "/subjects/",
    "/student-subjects/",
    "/timetable/",
    "/tv/",
    "/print/",
    "/resources/",
    "/upload/",
]


class SubscriptionFeatureBlockMiddleware:
    """
    Blocks premium/critical tenant modules when a school's subscription
    account is marked as blocked.

    It checks:
    - SchoolSubscriptionAccount.critical_features_blocked
    - SchoolSubscriptionAccount.status == BLOCKED or SUSPENDED
    - computed_status() == BLOCKED or SUSPENDED if available

    It does NOT block:
    - login
    - logout
    - billing page
    - notification API
    - static/media
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        block_response = self.check_subscription_block(request)

        if block_response:
            return block_response

        return self.get_response(request)

    def get_tenant_schema_from_request(self, request):
        path = request.path or ""

        # Handles /tenant/miyuga/app/...
        parts = path.strip("/").split("/")

        if len(parts) >= 2 and parts[0] == "tenant":
            schema_name = parts[1].strip()

            if schema_name and schema_name != PUBLIC_SCHEMA_NAME:
                return schema_name

        # Handles subdomain-based tenant request
        tenant = getattr(request, "tenant", None)
        schema_name = getattr(tenant, "schema_name", None)

        if schema_name and schema_name != PUBLIC_SCHEMA_NAME:
            return schema_name

        schema_name = getattr(request, "tenant_schema", None)

        if schema_name and schema_name != PUBLIC_SCHEMA_NAME:
            return schema_name

        return None

    def get_app_path(self, request, tenant_schema):
        """
        Converts:
        /tenant/miyuga/app/exams/ -> /exams/
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
        for allowed in ALLOWED_PATH_KEYWORDS:
            if allowed in app_path:
                return True

        return False

    def is_blocked_module(self, app_path):
        if app_path == "/":
            return False

        for prefix in BLOCKED_MODULE_PREFIXES:
            if app_path.startswith(prefix):
                return True

        return False

    def school_is_blocked(self, tenant_schema):
        try:
            with schema_context("public"):
                from tenants.models import School, SchoolSubscriptionAccount

                school = School.objects.filter(
                    schema_name=tenant_schema,
                ).first()

                if not school:
                    return False

                account = SchoolSubscriptionAccount.objects.filter(
                    school=school,
                ).first()

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

        except Exception:
            # Do not crash the whole site because of billing checks.
            return False

    def check_subscription_block(self, request):
        tenant_schema = self.get_tenant_schema_from_request(request)

        if not tenant_schema:
            return None

        app_path = self.get_app_path(request, tenant_schema)

        if self.is_allowed_path(app_path):
            return None

        if not self.is_blocked_module(app_path):
            return None

        if not self.school_is_blocked(tenant_schema):
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
