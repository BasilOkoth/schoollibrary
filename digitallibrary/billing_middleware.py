from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.db import connection

from tenants.models import School


class SubscriptionAccessMiddleware:
    """
    Restricts premium ShuleHub modules when a tenant subscription is blocked.

    This middleware does not block:
    - billing page
    - payment page
    - M-Pesa callbacks
    - dashboard
    - login/logout
    - static/media/admin paths
    """

    FREE_PATH_KEYWORDS = [
        "/billing/",
        "/subscription/",
        "/pay-subscription/",
        "/mpesa/",
        "/stk/",
        "/callback/",
        "/dashboard/",
        "/logout/",
        "/login/",
        "/smart-login/",
        "/admin/",
        "/static/",
        "/media/",
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
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""

        if self.should_skip_path(path):
            return self.get_response(request)

        if not self.is_premium_path(path):
            return self.get_response(request)

        school = self.get_current_school(request)

        if not school:
            return self.get_response(request)

        if self.school_is_blocked(school):
            messages.error(
                request,
                "Your ShuleHub subscription is blocked. Please update payment to continue using this feature.",
            )

            billing_url = self.get_billing_url(request, school)

            return redirect(billing_url)

        return self.get_response(request)

    def should_skip_path(self, path):
        return any(keyword in path for keyword in self.FREE_PATH_KEYWORDS)

    def is_premium_path(self, path):
        return any(keyword in path for keyword in self.PREMIUM_PATH_KEYWORDS)

    def get_current_school(self, request):
        """
        Gets the current tenant/school.

        Supports:
        - request.tenant
        - connection.schema_name
        """

        tenant = getattr(request, "tenant", None)

        if tenant and getattr(tenant, "schema_name", None):
            return tenant

        schema_name = getattr(connection, "schema_name", None)

        if not schema_name or schema_name == "public":
            return None

        return School.objects.filter(schema_name=schema_name).first()

    def school_is_blocked(self, school):
        """
        Determines whether the school should be blocked.

        This supports your existing School model fields:
        - paid_until
        - on_trial

        It also supports future fields if you add them:
        - billing_status
        - subscription_status
        - is_billing_blocked
        - grace_ends_at
        """

        today = timezone.localdate()
        now = timezone.now()

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
            if hasattr(grace_ends_at, "date"):
                grace_date = grace_ends_at.date()
            else:
                grace_date = grace_ends_at

            if grace_date >= today:
                return False

        on_trial = getattr(school, "on_trial", False)

        if on_trial:
            trial_ends_at = getattr(school, "trial_ends_at", None)

            if trial_ends_at:
                if hasattr(trial_ends_at, "date"):
                    trial_date = trial_ends_at.date()
                else:
                    trial_date = trial_ends_at

                if trial_date >= today:
                    return False

        paid_until = getattr(school, "paid_until", None)

        if paid_until:
            if hasattr(paid_until, "date"):
                paid_date = paid_until.date()
            else:
                paid_date = paid_until

            if paid_date >= today:
                return False

        return True

    def get_billing_url(self, request, school):
        """
        Builds tenant-aware billing URL.

        For path tenants:
        /tenant/demo/app/billing/

        For domain tenants:
        /tenant/demo/app/billing/ still works in your current structure.
        """

        schema_name = getattr(school, "schema_name", None)

        if schema_name:
            return f"/tenant/{schema_name}/app/billing/"

        return "/dashboard/"
