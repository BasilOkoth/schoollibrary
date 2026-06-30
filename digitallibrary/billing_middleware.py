from django.contrib import messages
from django.db import connection
from django.shortcuts import redirect
from django.utils import timezone

from tenants.models import School


class SubscriptionAccessMiddleware:
    """
    Restricts premium ShuleHub modules when a tenant subscription is blocked.

    Important:
    Do not allow every URL containing /dashboard/.
    Premium module dashboards such as /sms/dashboard/ must still be blocked.
    """

    PUBLIC_SKIP_PREFIXES = [
        "/static/",
        "/media/",
        "/admin/",
        "/tenants/",
        "/superadmin/",
        "/smart-login/",
        "/login/",
        "/logout/",
    ]

    BILLING_ALLOWED_KEYWORDS = [
        "/billing/",
        "/subscription/",
        "/pay-subscription/",
        "/mpesa/",
        "/stk/",
        "/callback/",
    ]

    PREMIUM_PATH_KEYWORDS = [
        "/sms/",
        "/reports/",
        "/report/",
        "/timetable/",
        "/tv/",
        "/results/",
        "/marks/",
        "/exams/",
        "/performance/",
        "/academics/promotions/",
        "/students/",
        "/parents/",
        "/fees/",
        "/print/",
        "/resources/",
        "/subjects/",
        "/classes/",
        "/streams/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""

        if self.should_skip_public_path(path):
            return self.get_response(request)

        if self.is_billing_or_payment_path(path):
            return self.get_response(request)

        school = self.get_current_school(request)

        if not school:
            return self.get_response(request)

        if not self.school_is_blocked(school):
            return self.get_response(request)

        # Allow only the main school dashboard so the user can see notices
        # and navigate to billing. Do not allow SMS/TV/timetable dashboards.
        if self.is_main_dashboard_path(path, school):
            return self.get_response(request)

        if self.is_premium_path(path):
            messages.error(
                request,
                "Your ShuleHub subscription is blocked. Please update payment to continue using this feature.",
            )
            return redirect(self.get_billing_url(school))

        return self.get_response(request)

    def should_skip_public_path(self, path):
        return any(path.startswith(prefix) for prefix in self.PUBLIC_SKIP_PREFIXES)

    def is_billing_or_payment_path(self, path):
        return any(keyword in path for keyword in self.BILLING_ALLOWED_KEYWORDS)

    def is_premium_path(self, path):
        return any(keyword in path for keyword in self.PREMIUM_PATH_KEYWORDS)

    def is_main_dashboard_path(self, path, school):
        schema_name = getattr(school, "schema_name", None)

        allowed_dashboard_paths = [
            "/app/dashboard/",
            "/dashboard/",
        ]

        if schema_name:
            allowed_dashboard_paths.append(
                f"/tenant/{schema_name}/app/dashboard/"
            )

        normalized_path = path.rstrip("/") + "/"

        return normalized_path in allowed_dashboard_paths

    def get_current_school(self, request):
        """
        Gets the current tenant/school.

        Supports:
        - request.tenant
        - connection.schema_name

        Important:
        If request.tenant is public, do not use it. For path-based tenancy,
        PathTenantSchemaMiddleware may switch connection.schema_name after
        TenantMainMiddleware has set request.tenant to public.
        """

        tenant = getattr(request, "tenant", None)

        tenant_schema = getattr(tenant, "schema_name", None)

        if tenant and tenant_schema and tenant_schema != "public":
            return tenant

        schema_name = getattr(connection, "schema_name", None)

        if not schema_name or schema_name == "public":
            return None

        return School.objects.filter(schema_name=schema_name).first()

    def school_is_blocked(self, school):
        """
        Determines whether the school should be blocked.

        Supports current and possible future fields:
        - paid_until
        - on_trial
        - trial_ends_at
        - grace_ends_at
        - billing_status
        - subscription_status
        - is_billing_blocked
        """

        today = timezone.localdate()

        if getattr(school, "is_billing_blocked", False):
            return True

        billing_status = getattr(school, "billing_status", None)

        if billing_status and str(billing_status).lower() == "blocked":
            return True

        subscription_status = getattr(school, "subscription_status", None)

        if subscription_status and str(subscription_status).lower() == "blocked":
            return True

        grace_ends_at = getattr(school, "grace_ends_at", None)

        if grace_ends_at:
            grace_date = grace_ends_at.date() if hasattr(grace_ends_at, "date") else grace_ends_at

            if grace_date >= today:
                return False

        on_trial = getattr(school, "on_trial", False)

        if on_trial:
            trial_ends_at = getattr(school, "trial_ends_at", None)

            if trial_ends_at:
                trial_date = trial_ends_at.date() if hasattr(trial_ends_at, "date") else trial_ends_at

                if trial_date >= today:
                    return False

        paid_until = getattr(school, "paid_until", None)

        if paid_until:
            paid_date = paid_until.date() if hasattr(paid_until, "date") else paid_until

            if paid_date >= today:
                return False

        return True

    def get_billing_url(self, school):
        schema_name = getattr(school, "schema_name", None)

        if schema_name:
            return f"/tenant/{schema_name}/app/billing/"

        return "/dashboard/"
