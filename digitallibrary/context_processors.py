# digitallibrary/context_processors.py

import re as _re
import logging
from django.db import connection

logger = logging.getLogger(__name__)


PUBLIC_DOMAINS = [
    "shulehub.org",
    "www.shulehub.org",
    "schoollibrary.onrender.com",
    "schoollibrary-1.onrender.com",
    "localhost",
    "127.0.0.1",
]


def _get_tenant_schema_from_path(request):
    """
    Extract tenant schema from path like:
    /tenant/nyaneje/app/dashboard/
    """
    path = getattr(request, "path", "") or ""
    match = _re.match(r"^/tenant/([^/]+)/", path)

    if match:
        schema = match.group(1)

        # Never treat /tenant/public/... as a real tenant app schema.
        if schema and schema != "public":
            return schema

    return None


def _get_request_tenant_schema(request):
    """
    Resolve tenant schema safely.

    Priority:
    1. URL path: /tenant/<schema>/...
    2. request.tenant_schema
    3. request.tenant.schema_name
    4. session tenant_schema
    5. connection.schema_name
    6. fallback pilot tenant: nyaneje

    Important:
    This avoids generating /tenant/public/... links.
    """
    # 1. URL path is most reliable
    path_schema = _get_tenant_schema_from_path(request)
    if path_schema:
        return path_schema

    # 2. request.tenant_schema
    request_schema = getattr(request, "tenant_schema", None)
    if request_schema and request_schema != "public":
        return request_schema

    # 3. request.tenant
    tenant = getattr(request, "tenant", None)
    tenant_schema = getattr(tenant, "schema_name", None)
    if tenant_schema and tenant_schema != "public":
        return tenant_schema

    # 4. session
    try:
        if hasattr(request, "session"):
            session_schema = request.session.get("tenant_schema")
            if session_schema and session_schema != "public":
                return session_schema
    except Exception:
        pass

    # 5. database connection
    connection_schema = getattr(connection, "schema_name", None)
    if connection_schema and connection_schema != "public":
        return connection_schema

    # 6. safe fallback for your current pilot tenant
    return "nyaneje"


def _get_current_tenant_info(request):
    """
    Safely determine current tenant/schema.

    This function is intentionally defensive because some pages may render
    while connection.schema_name is public even when the URL is tenant-based.
    """
    tenant = getattr(request, "tenant", None)
    path_schema = _get_tenant_schema_from_path(request)
    schema_name = _get_request_tenant_schema(request)

    return tenant, schema_name, path_schema


def school_settings(request):
    """
    Provides school-specific settings to all templates.

    Important:
    Context processors should not create database objects.
    They only return template context.
    """
    tenant, schema_name, path_schema = _get_current_tenant_info(request)

    active_schema = schema_name or "nyaneje"

    # If the request is truly public and not a tenant path, use /app.
    # Otherwise always use /tenant/<schema>/app.
    is_real_public_page = (
        not path_schema
        and active_schema == "public"
    )

    if is_real_public_page:
        app_prefix = "/app"
    else:
        if active_schema == "public":
            active_schema = "nyaneje"

        app_prefix = f"/tenant/{active_schema}/app"

    context = {
        "school": None,
        "school_settings": None,
        "school_name": active_schema.replace("_", " ").title() if active_schema != "public" else "ShuleHub",
        "school_logo": None,
        "school_motto": "Digital Library Platform for Kenyan Schools" if is_real_public_page else "",

        "is_public_schema": is_real_public_page,
        "is_tenant_schema": not is_real_public_page,
        "current_schema": active_schema,

        "app_prefix": app_prefix,
        "school_settings_url": f"{app_prefix}/school-settings/",
        "tv_dashboard_url": f"{app_prefix}/tv/dashboard/",
        "tv_live_url": f"{app_prefix}/tv/dashboard/",

        "public_warning": "You are on ShuleHub public portal." if is_real_public_page else None,
    }

    if not is_real_public_page:
        try:
            from .models import SchoolSetting

            school_setting = SchoolSetting.objects.first()

            if school_setting:
                context.update({
                    "school": school_setting,
                    "school_settings": school_setting,
                    "school_name": getattr(school_setting, "name", None) or active_schema.replace("_", " ").title(),
                    "school_logo": school_setting.logo.url if getattr(school_setting, "logo", None) else None,
                    "school_motto": getattr(school_setting, "motto", None) or "",
                    "is_public_schema": False,
                    "is_tenant_schema": True,
                    "current_schema": active_schema,
                    "public_warning": None,
                })
            else:
                tenant_name = (
                    getattr(tenant, "name", None)
                    or active_schema.replace("_", " ").title()
                )

                context.update({
                    "school": None,
                    "school_settings": None,
                    "school_name": tenant_name,
                    "school_logo": None,
                    "school_motto": "",
                    "is_public_schema": False,
                    "is_tenant_schema": True,
                    "current_schema": active_schema,
                    "public_warning": "Settings not configured. Please update School Settings.",
                })

        except Exception as e:
            logger.warning(
                "Tenant school_settings context error for schema %s: %s",
                active_schema,
                e,
            )

            context.update({
                "school": None,
                "school_settings": None,
                "school_name": active_schema.replace("_", " ").title(),
                "school_logo": None,
                "school_motto": "",
                "is_public_schema": False,
                "is_tenant_schema": True,
                "current_schema": active_schema,
                "public_warning": None,
            })

    return context


def tenant_context(request):
    """
    Provides tenant variables to all templates.

    This prevents templates from accidentally rendering:
    /tenant/public/app/...
    """
    tenant_schema = _get_request_tenant_schema(request)

    if not tenant_schema or tenant_schema == "public":
        tenant_schema = "nyaneje"

    return {
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant": getattr(request, "tenant", None),
    }


def tenant_urls(request):
    """
    Provides safe tenant-aware URLs to templates.

    Use these in templates where possible instead of hardcoding:
    /tenant/public/app/...
    """
    tenant_schema = _get_request_tenant_schema(request)

    if not tenant_schema or tenant_schema == "public":
        tenant_schema = "nyaneje"

    base = f"/tenant/{tenant_schema}/app"

    return {
        "tenant_base_url": base,

        "tenant_dashboard_url": f"{base}/dashboard/",
        "tenant_home_url": f"{base}/",
        "tenant_login_url": f"{base}/login/",
        "tenant_logout_url": f"{base}/logout/",

        "tenant_admin_dashboard_url": f"{base}/admin/dashboard/",

        "tenant_students_url": f"{base}/students/",
        "tenant_student_create_url": f"{base}/students/create/",

        "tenant_fees_dashboard_url": f"{base}/fees/dashboard/",
        "tenant_fee_structures_url": f"{base}/fees/structures/",
        "tenant_fee_structure_create_url": f"{base}/fees/structure/create/",
        "tenant_payment_record_url": f"{base}/fees/payments/record/",
        "tenant_defaulters_url": f"{base}/fees/defaulters/",
        "tenant_collection_report_url": f"{base}/fees/reports/",

        "tenant_performance_url": f"{base}/performance/",
        "tenant_library_url": f"{base}/library/",
        "tenant_print_url": f"{base}/print/",

        "tenant_tv_dashboard_url": f"{base}/tv/dashboard/",
        "tenant_tv_live_url": f"{base}/tv/dashboard/",

        "tenant_notifications_url": f"{base}/notifications/",
        "tenant_notifications_api_url": f"{base}/api/notifications/",

        "tenant_school_settings_url": f"{base}/school-settings/",

        "tenant_sms_staff_url": f"{base}/sms/to-staff/",
        "tenant_exam_create_url": f"{base}/exams/create/",
        "tenant_grading_systems_url": f"{base}/grading/systems/",
    }
