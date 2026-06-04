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
    match = _re.match(r"^/tenant/([^/]+)/", request.path or "")
    if match:
        return match.group(1)
    return None


def _get_current_tenant_info(request):
    """
    Safely determine current tenant/schema using:
    1. URL path
    2. request.tenant
    3. database connection schema

    IMPORTANT:
    Do NOT read or write request.session here.
    Public tenant pages must not touch session.
    """
    tenant = getattr(request, "tenant", None)
    path_schema = _get_tenant_schema_from_path(request)

    if path_schema:
        schema_name = path_schema
    elif tenant and getattr(tenant, "schema_name", None):
        schema_name = tenant.schema_name
    else:
        schema_name = getattr(connection, "schema_name", "public") or "public"

    return tenant, schema_name, path_schema


def school_settings(request):
    """
    Provides school-specific settings to all templates.
    This should not break if SchoolSetting is missing.

    IMPORTANT:
    Do not read/write request.session here.
    Context processors should only return template context.
    """
    tenant, schema_name, path_schema = _get_current_tenant_info(request)

    active_schema = path_schema or schema_name or "public"

    if path_schema:
        app_prefix = f"/tenant/{path_schema}/app"
    elif active_schema != "public":
        app_prefix = f"/tenant/{active_schema}/app"
    else:
        app_prefix = "/app"

    context = {
        "school": None,
        "school_settings": None,
        "school_name": "ShuleHub",
        "school_logo": None,
        "school_motto": "Digital Library Platform for Kenyan Schools",

        "is_public_schema": active_schema == "public" and not path_schema,
        "is_tenant_schema": active_schema != "public" or bool(path_schema),
        "current_schema": active_schema,

        "app_prefix": app_prefix,
        "school_settings_url": f"{app_prefix}/school-settings/",
        "tv_dashboard_url": f"{app_prefix}/tv/dashboard/",
        "tv_live_url": f"{app_prefix}/tv/",

        "public_warning": "You are on ShuleHub public portal.",
    }

    if active_schema != "public":
        try:
            from .models import SchoolSetting

            school_setting = SchoolSetting.objects.first()

            if school_setting:
                context.update({
                    "school": school_setting,
                    "school_settings": school_setting,
                    "school_name": getattr(school_setting, "name", None) or "School System",
                    "school_logo": school_setting.logo.url if getattr(school_setting, "logo", None) else None,
                    "school_motto": getattr(school_setting, "motto", None) or "",
                    "is_public_schema": False,
                    "is_tenant_schema": True,
                    "current_schema": active_schema,
                    "public_warning": None,
                })
            else:
                tenant_name = getattr(tenant, "name", None) or active_schema.replace("_", " ").title()

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
                e
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
    Provides tenant-aware URL helpers to all templates.
    This is important for keeping users inside /tenant/<schema>/app/.
    """
    host = request.get_host().split(":")[0].lower()
    tenant, schema_name, path_schema = _get_current_tenant_info(request)

    tenant_prefix = path_schema or (schema_name if schema_name != "public" else "")
    is_public = not tenant_prefix

    if tenant_prefix:
        app_prefix = f"/tenant/{tenant_prefix}/app"
    else:
        app_prefix = "/app"

    user_role = None

    try:
        if request.user.is_authenticated and hasattr(request.user, "profile"):
            user_role = request.user.profile.role
    except Exception:
        user_role = None

    context = {
        "tenant": tenant,
        "tenant_schema": tenant_prefix or schema_name,
        "tenant_prefix": tenant_prefix,
        "current_schema": schema_name,
        "current_host": host,

        "is_public_schema": is_public,
        "is_tenant_schema": not is_public,

        "base_url": app_prefix,
        "app_prefix": app_prefix,

        "user_role": user_role,
        "is_authenticated": request.user.is_authenticated,

        "home_url": f"{app_prefix}/",
        "dashboard_url": f"{app_prefix}/dashboard/",

        "login_url": f"{app_prefix}/login/",
        "logout_url": f"{app_prefix}/logout/",

        "library_url": f"{app_prefix}/library/",
        "upload_url": f"{app_prefix}/upload/",
        "my_uploads_url": f"{app_prefix}/my-uploads/",
        "ai_search_url": f"{app_prefix}/ai-search/",

        "tv_base": f"{app_prefix}/tv",
        "tv_display_url": f"{app_prefix}/tv/",
        "tv_dashboard_url": f"{app_prefix}/tv/dashboard/",
        "tv_content_add_url": f"{app_prefix}/tv/content/add/",
        "tv_settings_url": f"{app_prefix}/tv/settings/",

        "fees_base": f"{app_prefix}/fees",
        "fees_dashboard_url": f"{app_prefix}/fees/dashboard/",
        "fees_students_url": f"{app_prefix}/fees/students/",
        "fees_structure_url": f"{app_prefix}/fees/structures/",
        "fees_payment_url": f"{app_prefix}/fees/payments/record/",
        "fees_defaulters_url": f"{app_prefix}/fees/defaulters/",
        "fees_reports_url": f"{app_prefix}/fees/reports/",
        "fees_historical_arrears_url": f"{app_prefix}/fees/historical-arrears/add/",

        "performance_url": f"{app_prefix}/performance/",
        "exams_url": f"{app_prefix}/exams/",
        "enter_results_url": f"{app_prefix}/enter-results/",
        "bulk_enter_results_url": f"{app_prefix}/bulk-enter-results/",
        "performance_reports_url": f"{app_prefix}/performance/reports/",

        "sms_url": f"{app_prefix}/sms/dashboard/",

        "parent_url": f"{app_prefix}/parent/",
        "parent_login_url": f"{app_prefix}/parent/login/",
        "parent_dashboard_url": f"{app_prefix}/parent/dashboard/",
        "parent_fee_url": f"{app_prefix}/parent/fee/",

        "students_url": f"{app_prefix}/students/",
        "users_url": f"{app_prefix}/users/",
        "profile_url": f"{app_prefix}/profile/",
        "notifications_url": f"{app_prefix}/notifications/",
        "school_settings_url": f"{app_prefix}/school-settings/",
        "admin_library_url": f"{app_prefix}/admin-library/dashboard/",
        "print_url": f"{app_prefix}/print/",
        "feedback_api_url": f"{app_prefix}/api/submit-feedback/",
    }

    return context


def tenant_urls(request):
    """
    Optional helper dictionary for JavaScript/templates.
    Explicit URLs are safer than pattern.replace('_', '/').
    """
    tenant, schema_name, path_schema = _get_current_tenant_info(request)
    tenant_prefix = path_schema or (schema_name if schema_name != "public" else "")

    app_prefix = f"/tenant/{tenant_prefix}/app" if tenant_prefix else "/app"

    return {
        "tenant_urls": {
            "tenant_prefix": tenant_prefix,
            "app_prefix": app_prefix,
            "home": f"{app_prefix}/",
            "dashboard": f"{app_prefix}/dashboard/",
            "login": f"{app_prefix}/login/",
            "logout": f"{app_prefix}/logout/",
            "library": f"{app_prefix}/library/",
            "upload": f"{app_prefix}/upload/",
            "tv_dashboard": f"{app_prefix}/tv/dashboard/",
            "fees_dashboard": f"{app_prefix}/fees/dashboard/",
            "fees_payment": f"{app_prefix}/fees/payments/record/",
            "fees_defaulters": f"{app_prefix}/fees/defaulters/",
            "parent_dashboard": f"{app_prefix}/parent/dashboard/",
            "feedback_api": f"{app_prefix}/api/submit-feedback/",
            "school_settings": f"{app_prefix}/school-settings/",
        }
    }
