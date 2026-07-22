from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import connection
from django.shortcuts import redirect
from django.utils import timezone
from django_tenants.utils import schema_context

from tenants.models import School, SchoolSubscriptionAccount


class SubscriptionAccessMiddleware:
    """
    Restricts premium ShuleHub modules only when a tenant subscription is
    explicitly blocked, overdue, suspended, expired, or outside every valid
    billing/trial/grace period.

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
        "/exam-papers/",
        "/result-streams/",
    ]

    BLOCKED_STATUSES = {
        "blocked",
        "suspended",
        "expired",
        "overdue",
        "past_due",
        "past due",
        "inactive",
        "cancelled",
        "canceled",
    }

    ACTIVE_STATUSES = {
        "active",
        "paid",
        "current",
        "trial",
        "trialing",
        "grace",
        "grace_period",
        "grace period",
    }

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
                (
                    "Your ShuleHub subscription is blocked. "
                    "Please update payment to continue using this feature."
                ),
            )
            return redirect(self.get_billing_url(school))

        return self.get_response(request)

    def should_skip_public_path(self, path):
        return any(
            path.startswith(prefix)
            for prefix in self.PUBLIC_SKIP_PREFIXES
        )

    def is_billing_or_payment_path(self, path):
        return any(
            keyword in path
            for keyword in self.BILLING_ALLOWED_KEYWORDS
        )

    def is_premium_path(self, path):
        return any(
            keyword in path
            for keyword in self.PREMIUM_PATH_KEYWORDS
        )

    def is_main_dashboard_path(self, path, school):
        schema_name = getattr(
            school,
            "schema_name",
            None,
        )

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

        If request.tenant is public, do not use it. For path-based tenancy,
        PathTenantSchemaMiddleware may switch connection.schema_name after
        TenantMainMiddleware has set request.tenant to public.
        """

        tenant = getattr(
            request,
            "tenant",
            None,
        )

        tenant_schema = getattr(
            tenant,
            "schema_name",
            None,
        )

        if (
            tenant
            and tenant_schema
            and tenant_schema != "public"
        ):
            return tenant

        schema_name = getattr(
            connection,
            "schema_name",
            None,
        )

        if (
            not schema_name
            or schema_name == "public"
        ):
            return None

        return School.objects.filter(
            schema_name=schema_name,
        ).first()

    @staticmethod
    def normalize_status(value):
        return str(
            value or ""
        ).strip().lower()

    @staticmethod
    def date_value(value):
        if not value:
            return None

        return (
            value.date()
            if hasattr(value, "date")
            else value
        )

    @staticmethod
    def decimal_value(value):
        if value in (
            None,
            "",
        ):
            return None

        try:
            return Decimal(
                str(value)
            )
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ):
            return None

    def get_subscription_account(self, school):
        """
        Return the central subscription account for this school.

        Billing records live in the public schema, while this middleware may
        execute after the connection has switched to a tenant schema.
        """

        school_id = getattr(
            school,
            "id",
            None,
        )

        if not school_id:
            return None

        with schema_context("public"):
            return (
                SchoolSubscriptionAccount.objects
                .filter(school_id=school_id)
                .first()
            )

    def subscription_account_is_blocked(self, subscription):
        """
        Use the same subscription rules as the school billing page.
        """

        stored_status = self.normalize_status(
            getattr(
                subscription,
                "status",
                None,
            )
        )

        if stored_status == "suspended":
            return True

        computed_status_method = getattr(
            subscription,
            "computed_status",
            None,
        )

        computed_status = (
            self.normalize_status(
                computed_status_method()
            )
            if callable(computed_status_method)
            else stored_status
        )

        if computed_status in {
            "blocked",
            "suspended",
        }:
            return True

        is_blocked_method = getattr(
            subscription,
            "is_blocked",
            None,
        )

        if callable(is_blocked_method):
            return bool(
                is_blocked_method()
            )

        critical_features_blocked = bool(
            getattr(
                subscription,
                "critical_features_blocked",
                False,
            )
        )

        if critical_features_blocked:
            return True

        # Active, due, and grace subscriptions remain accessible unless the
        # subscription model itself explicitly reports that they are blocked.
        if computed_status in {
            "active",
            "due",
            "grace",
        }:
            return False

        amount_due = self.decimal_value(
            getattr(
                subscription,
                "amount_due",
                None,
            )
        )

        if (
            amount_due is not None
            and amount_due <= 0
        ):
            return False

        return False

    def school_is_blocked(self, school):
        """
        Determine whether the school should be blocked.

        Source-of-truth order:
        1. SchoolSubscriptionAccount, used by the billing page.
        2. Legacy School billing fields, only when no subscription account
           exists.

        This prevents an active subscription account from being overridden by
        an expired legacy School.paid_until value.
        """

        subscription = self.get_subscription_account(
            school
        )

        if subscription is not None:
            return self.subscription_account_is_blocked(
                subscription
            )

        # ------------------------------------------------------------
        # Legacy fallback
        # ------------------------------------------------------------
        today = timezone.localdate()

        if getattr(
            school,
            "is_billing_blocked",
            False,
        ):
            return True

        billing_status = self.normalize_status(
            getattr(
                school,
                "billing_status",
                None,
            )
        )

        subscription_status = self.normalize_status(
            getattr(
                school,
                "subscription_status",
                None,
            )
        )

        statuses = {
            status
            for status in (
                billing_status,
                subscription_status,
            )
            if status
        }

        if statuses & self.BLOCKED_STATUSES:
            return True

        if statuses & self.ACTIVE_STATUSES:
            return False

        grace_date = self.date_value(
            getattr(
                school,
                "grace_ends_at",
                None,
            )
        )

        if (
            grace_date
            and grace_date >= today
        ):
            return False

        on_trial = bool(
            getattr(
                school,
                "on_trial",
                False,
            )
        )

        trial_date = self.date_value(
            getattr(
                school,
                "trial_ends_at",
                None,
            )
        )

        if (
            on_trial
            and trial_date
            and trial_date >= today
        ):
            return False

        paid_date = self.date_value(
            getattr(
                school,
                "paid_until",
                None,
            )
        )

        if (
            paid_date
            and paid_date >= today
        ):
            return False

        next_billing_date = self.date_value(
            getattr(
                school,
                "next_billing_date",
                None,
            )
        )

        if (
            next_billing_date
            and next_billing_date >= today
        ):
            return False

        amount_due = self.decimal_value(
            getattr(
                school,
                "amount_due",
                None,
            )
        )

        outstanding_balance = self.decimal_value(
            getattr(
                school,
                "outstanding_balance",
                None,
            )
        )

        known_balances = [
            balance
            for balance in (
                amount_due,
                outstanding_balance,
            )
            if balance is not None
        ]

        if (
            known_balances
            and all(
                balance <= 0
                for balance in known_balances
            )
        ):
            return False

        if (
            on_trial
            and trial_date
            and trial_date < today
        ):
            return True

        if (
            grace_date
            and grace_date < today
        ):
            return True

        if (
            paid_date
            and paid_date < today
        ):
            return True

        if any(
            balance > 0
            for balance in known_balances
        ):
            return True

        # Incomplete legacy metadata must not block access by default.
        return False

    def get_billing_url(self, school):
        schema_name = getattr(
            school,
            "schema_name",
            None,
        )

        if schema_name:
            return (
                f"/tenant/{schema_name}/app/billing/"
            )

        return "/dashboard/"
