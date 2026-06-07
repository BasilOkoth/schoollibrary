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


DEFAULT_TENANT_SCHEMA = "nyaneje"


def _clean_schema(schema):
    """
    Normalize schema values and reject unsafe/public/empty schemas.

    This is very important because templates must never generate:
    /tenant/public/app/...
    /tenant/None/app/...
    /tenant/undefined/app/...
    """
    if not schema:
        return None

    schema = str(schema).strip()

    if not schema:
        return None

    bad_values = ["public", "none", "null", "undefined", "false", "true"]

    if schema.lower() in bad_values:
        return None

    return schema


def _get_tenant_schema_from_path(request):
    """
    Extract tenant schema from path like:
    /tenant/nyaneje/app/dashboard/
    """
    path = getattr(request, "path", "") or ""
    match = _re.match(r"^/tenant/([^/]+)/", path)

    if match:
        return _clean_schema(match.group(1))

    return None


def _get_tenant_schema_from_resolver(request):
    """
    Extract tenant_schema from URL kwargs where available.

    Example:
    path("tenant/<str:tenant_schema>/app/...", ...)
    """
    try:
        resolver_match = getattr(request, "resolver_match", None)

        if resolver_match and resolver_match.kwargs:
            return _clean_schema(resolver_match.kwargs.get("tenant_schema"))

    except Exception:
        return None

    return None


def _get_tenant_schema_from_referer(request):
    """
    Try to recover tenant schema from HTTP_REFERER.

    This helps when a template is rendered from a page that accidentally
    lost tenant context but the user came from:
    /tenant/nyaneje/app/...
    """
    try:
        referer = request.META.get("HTTP_REFERER", "") or ""
        match = _re.search(r"/tenant/([^/]+)/app/", referer)

        if match:
            return _clean_schema(match.group(1))

    except Exception:
        return None

    return None


def _get_request_tenant_schema(request):
    """
    Resolve tenant schema safely.

    Priority:
    1. URL resolver kwargs tenant_schema
    2. URL path: /tenant/<schema>/...
    3. request.tenant_schema
    4. request.tenant.schema_name
    5. session tenant_schema
    6. HTTP_REFERER tenant schema
    7. connection.schema_name
    8. fallback pilot tenant: nyaneje

    This prevents templates from rendering:
    /tenant//app/...
    /tenant/public/app/...
    """
    resolver_schema = _get_tenant_schema_from_resolver(request)
    if resolver_schema:
        return resolver_schema

    path_schema = _get_tenant_schema_from_path(request)
    if path_schema:
        return path_schema

    request_schema = _clean_schema(getattr(request, "tenant_schema", None))
    if request_schema:
        return request_schema

    tenant = getattr(request, "tenant", None)
    tenant_schema = _clean_schema(getattr(tenant, "schema_name", None))
    if tenant_schema:
        return tenant_schema

    try:
        if hasattr(request, "session"):
            session_schema = _clean_schema(request.session.get("tenant_schema"))

            if session_schema:
                return session_schema
    except Exception:
        pass

    referer_schema = _get_tenant_schema_from_referer(request)
    if referer_schema:
        return referer_schema

    connection_schema = _clean_schema(getattr(connection, "schema_name", None))
    if connection_schema:
        return connection_schema

    return DEFAULT_TENANT_SCHEMA


def _is_public_page(request, active_schema):
    """
    Decide whether current page should behave as public.

    A page is public only when:
    - it is not a /tenant/<schema>/... path
    - and the database connection is public.
    """
    path = getattr(request, "path", "") or ""

    if path.startswith("/tenant/"):
        return False

    path_schema = _get_tenant_schema_from_path(request)
    resolver_schema = _get_tenant_schema_from_resolver(request)

    if path_schema or resolver_schema:
        return False

    raw_connection_schema = getattr(connection, "schema_name", None)

    if raw_connection_schema == "public":
        return True

    if str(active_schema).lower() == "public":
        return True

    return False


def _build_app_prefix(schema):
    """
    Build safe tenant app prefix.
    """
    schema = _clean_schema(schema) or DEFAULT_TENANT_SCHEMA
    return f"/tenant/{schema}/app"


def _build_tenant_urls(schema):
    """
    Central place for all tenant URLs.

    Use these in templates instead of hardcoding /tenant/{{ current_schema }}/app/...
    """
    schema = _clean_schema(schema) or DEFAULT_TENANT_SCHEMA
    base = _build_app_prefix(schema)

    return {
        "tenant_prefix": schema,
        "tenant_schema": schema,
        "current_tenant_schema": schema,

        "tenant_base_url": base,

        # Core tenant pages
        "tenant_home_url": f"{base}/",
        "tenant_dashboard_url": f"{base}/dashboard/",
        "tenant_login_url": f"{base}/login/",
        "tenant_logout_url": f"{base}/logout/",
        "tenant_school_settings_url": f"{base}/school-settings/",

        # Admin
        "tenant_admin_dashboard_url": f"{base}/admin/dashboard/",
        "tenant_users_url": f"{base}/users/",
        "tenant_add_user_url": f"{base}/users/add/",

        # Students
        "tenant_students_url": f"{base}/students/",
        "tenant_student_create_url": f"{base}/students/create/",

        # Fees
        "tenant_fees_dashboard_url": f"{base}/fees/dashboard/",
        "tenant_fee_students_url": f"{base}/fees/students/",
        "tenant_fee_structures_url": f"{base}/fees/structures/",
        "tenant_fee_structure_list_url": f"{base}/fees/structure/",
        "tenant_fee_structure_create_url": f"{base}/fees/structure/create/",
        "tenant_payment_record_url": f"{base}/fees/payments/record/",
        "tenant_defaulters_url": f"{base}/fees/defaulters/",
        "tenant_collection_report_url": f"{base}/fees/reports/",
        "tenant_historical_arrears_url": f"{base}/fees/historical-arrears/",
        "tenant_historical_arrears_add_url": f"{base}/fees/historical-arrears/",

        # Library / performance
        "tenant_performance_url": f"{base}/performance/",
        "tenant_library_url": f"{base}/library/",
        "tenant_print_url": f"{base}/print/",
        "tenant_upload_resource_url": f"{base}/upload/",
        "tenant_my_uploads_url": f"{base}/my-uploads/",

        # TV
        "tenant_tv_dashboard_url": f"{base}/tv/dashboard/",
        "tenant_tv_live_url": f"{base}/tv/",
        "tenant_tv_schedule_url": f"{base}/tv/schedule/",
        "tenant_tv_content_add_url": f"{base}/tv/content/add/",

        # Notifications
        "tenant_notifications_url": f"{base}/notifications/",
        "tenant_notifications_api_url": f"{base}/api/notifications/",
        "tenant_notifications_mark_all_read_url": f"{base}/api/notifications/mark-all-read/",

        # SMS
        "tenant_sms_staff_url": f"{base}/sms/to-staff/",

        # Exams
        "tenant_exams_url": f"{base}/exams/",
        "tenant_exam_list_url": f"{base}/exams/",
        "tenant_exam_create_url": f"{base}/exams/create/",
        "tenant_bulk_enter_results_url": f"{base}/exams/bulk-enter/",
        "tenant_bulk_excel_upload_url": f"{base}/exams/bulk-excel-upload/",
        "tenant_enter_results_url": f"{base}/enter-results/",
        "tenant_enter_results_form_url": f"{base}/enter-results-form/",

        # Grading
        "tenant_grading_systems_url": f"{base}/grading/systems/",
        "tenant_grading_system_create_url": f"{base}/grading/systems/create/",
    }


def _get_current_tenant_info(request):
    """
    Safely determine current tenant/schema.
    """
    tenant = getattr(request, "tenant", None)
    schema_name = _get_request_tenant_schema(request)
    path_schema = _get_tenant_schema_from_path(request)

    return tenant, schema_name, path_schema


def school_settings(request):
    """
    Provides school-specific settings to all templates.

    Important:
    Context processors should not create database objects.
    They only return template context.
    """
    tenant, schema_name, path_schema = _get_current_tenant_info(request)

    active_schema = _clean_schema(schema_name) or DEFAULT_TENANT_SCHEMA
    is_real_public_page = _is_public_page(request, active_schema)

    if is_real_public_page:
        app_prefix = "/app"
        current_schema = "public"

        # Keep tenant_schema safe even on public pages so accidental
        # tenant URL tags do not generate /tenant/public/app/...
        tenant_schema = DEFAULT_TENANT_SCHEMA
    else:
        current_schema = active_schema
        tenant_schema = active_schema
        app_prefix = _build_app_prefix(active_schema)

    safe_urls = _build_tenant_urls(tenant_schema)

    context = {
        "school": None,
        "school_settings": None,

        "school_name": (
            "ShuleHub"
            if is_real_public_page
            else active_schema.replace("_", " ").replace("-", " ").title()
        ),
        "school_logo": None,
        "school_motto": (
            "Digital Library Platform for Kenyan Schools"
            if is_real_public_page
            else ""
        ),

        "is_public_schema": is_real_public_page,
        "is_tenant_schema": not is_real_public_page,

        "current_schema": current_schema,

        # Important tenant-safe template variables
        "tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "current_tenant_schema": tenant_schema,

        "app_prefix": app_prefix,

        "school_settings_url": f"{app_prefix}/school-settings/",
        "tv_dashboard_url": f"{app_prefix}/tv/dashboard/",
        "tv_live_url": f"{app_prefix}/tv/",
        "tv_schedule_url": f"{app_prefix}/tv/schedule/",

        "public_warning": (
            "You are on ShuleHub public portal."
            if is_real_public_page
            else None
        ),
    }

    # Add all tenant-safe URLs into school_settings context too
    context.update(safe_urls)

    if is_real_public_page:
        return context

    try:
        from .models import SchoolSetting

        school_setting = SchoolSetting.objects.first()

        if school_setting:
            context.update({
                "school": school_setting,
                "school_settings": school_setting,
                "school_name": (
                    getattr(school_setting, "name", None)
                    or active_schema.replace("_", " ").replace("-", " ").title()
                ),
                "school_logo": (
                    school_setting.logo.url
                    if getattr(school_setting, "logo", None)
                    else None
                ),
                "school_motto": getattr(school_setting, "motto", None) or "",
                "is_public_schema": False,
                "is_tenant_schema": True,
                "current_schema": active_schema,

                "tenant_schema": tenant_schema,
                "tenant_prefix": tenant_schema,
                "current_tenant_schema": tenant_schema,

                "public_warning": None,
            })

            context.update(safe_urls)

        else:
            tenant_name = (
                getattr(tenant, "name", None)
                or active_schema.replace("_", " ").replace("-", " ").title()
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

                "tenant_schema": tenant_schema,
                "tenant_prefix": tenant_schema,
                "current_tenant_schema": tenant_schema,

                "public_warning": "Settings not configured. Please update School Settings.",
            })

            context.update(safe_urls)

    except Exception as e:
        logger.warning(
            "Tenant school_settings context error for schema %s: %s",
            active_schema,
            e,
        )

        context.update({
            "school": None,
            "school_settings": None,
            "school_name": active_schema.replace("_", " ").replace("-", " ").title(),
            "school_logo": None,
            "school_motto": "",
            "is_public_schema": False,
            "is_tenant_schema": True,
            "current_schema": active_schema,

            "tenant_schema": tenant_schema,
            "tenant_prefix": tenant_schema,
            "current_tenant_schema": tenant_schema,

            "public_warning": None,
        })

        context.update(safe_urls)

    return context


def tenant_context(request):
    """
    Provides tenant variables to all templates.

    This prevents templates from accidentally rendering:
    /tenant//app/...
    /tenant/public/app/...
    """
    tenant_schema = _get_request_tenant_schema(request)
    tenant_schema = _clean_schema(tenant_schema) or DEFAULT_TENANT_SCHEMA

    return {
        "tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant": getattr(request, "tenant", None),
        "tenant_app_prefix": _build_app_prefix(tenant_schema),
    }


def tenant_urls(request):
    """
    Provides safe tenant-aware URLs to templates.

    Use these in templates instead of hardcoding:
    /tenant/{{ current_schema }}/app/...
    """
    tenant_schema = _get_request_tenant_schema(request)
    tenant_schema = _clean_schema(tenant_schema) or DEFAULT_TENANT_SCHEMA

    return _build_tenant_urls(tenant_schema)
