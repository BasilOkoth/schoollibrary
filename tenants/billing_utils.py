from django_tenants.utils import schema_context
from .models import School, SchoolSubscriptionAccount


def school_subscription_is_blocked(tenant_schema):
    if not tenant_schema or tenant_schema == "public":
        return False

    with schema_context("public"):
        school = School.objects.filter(schema_name=tenant_schema).first()

        if not school:
            return False

        subscription = SchoolSubscriptionAccount.objects.filter(school=school).first()

        if not subscription:
            return False

        return subscription.is_blocked()
