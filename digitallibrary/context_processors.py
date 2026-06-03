# digitallibrary/context_processors.py

import re as _re
import logging

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
    3. session fallback
    """
    tenant = getattr(request, "tenant", None)
    path_schema = _get_tenant_schema_from_path(request)

    if path_schema:
        schema_name = path_schema
    elif tenant and getattr(tenant, "schema_name", None):
        schema_name = tenant.schema_name
    else:
        schema_name = request.session.get("tenant_schema", "public") if hasattr(request, "session") else "public"

    if schema_name and schema_name != "public" and hasattr(request, "session"):
        request.session["tenant_schema"] = schema_name

    return tenant, schema_name, path_schema


def school_settings(request):
    """
    Provides school-specific settings to all templates.
    This should not break if SchoolSetting is missing.
    """
    tenant, schema_name, path_schema = _get_current_tenant_info(request)

    context = {
        "school": None,
        "school_name": "ShuleHub",
        "school_logo": None,
        "school_motto": "Digital Library Platform for Kenyan Schools",
        "is_public_schema": schema_name == "public" and not path_schema,
        "is_tenant_schema": schema_name != "public" or bool(path_schema),
        "current_schema": schema_name,
        "public_warning": "You are on ShuleHub public portal.",
    }

    if schema_name != "public":
        try:
            from .models import SchoolSetting

            school_setting = SchoolSetting.objects.first()

            if school_setting:
                context.update({
                    "school": school_setting,
                    "school_name": school_setting.name or "School System",
                    "school_logo": school_setting.logo.url if school_setting.logo else None,
                    "school_motto": school_setting.motto or "",
                    "is_public_schema": False,
                    "is_tenant_schema": True,
                    "current_schema": schema_name,
                    "public_warning": None,
                })
            else:
                tenant_name = getattr(tenant, "name", schema_name.title()) if tenant else schema_name.title()
                context.update({
                    "school": None,
                    "school_name": tenant_name,
                    "school_logo": None,
                    "school_motto": "",
                    "is_public_schema": False,
                    "is_tenant_schema": True,
                    "current_schema": schema_name,
                    "public_warning": "Settings not configured. Please visit the admin panel.",
                })

        except Exception as e:
            logger.warning("Tenant school_settings context error for schema %s: %s", schema_name, e)
            context.update({
                "school_name": schema_name.title(),
                "is_public_schema": False,
                "is_tenant_schema": True,
                "current_schema": schema_name,
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
        # Basic tenant info
        "tenant": tenant,
        "tenant_schema": tenant_prefix or schema_name,
        "tenant_prefix": tenant_prefix,
        "current_schema": schema_name,
        "current_host": host,

        # Public/tenant flags
        "is_public_schema": is_public,
        "is_tenant_schema": not is_public,

        # Core URL prefix
        "base_url": app_prefix,
        "app_prefix": app_prefix,

        # Auth/user
        "user_role": user_role,
        "is_authenticated": request.user.is_authenticated,

        # Dashboard URLs
        "home_url": f"{app_prefix}/",
        "dashboard_url": f"{app_prefix}/dashboard/",

        # Auth URLs
        "login_url": f"{app_prefix}/login/",
        "logout_url": f"{app_prefix}/logout/",

        # Library URLs
        "library_url": f"{app_prefix}/library/",
        "upload_url": f"{app_prefix}/upload/",
        "my_uploads_url": f"{app_prefix}/my-uploads/",
        "ai_search_url": f"{app_prefix}/ai-search/",

        # TV URLs
        "tv_base": f"{app_prefix}/tv",
        "tv_display_url": f"{app_prefix}/tv/",
        "tv_dashboard_url": f"{app_prefix}/tv/dashboard/",
        "tv_content_add_url": f"{app_prefix}/tv/content/add/",
        "tv_settings_url": f"{app_prefix}/tv/settings/",

        # Fees URLs
        "fees_base": f"{app_prefix}/fees",
        "fees_dashboard_url": f"{app_prefix}/fees/dashboard/",
        "fees_students_url": f"{app_prefix}/fees/students/",
        "fees_structure_url": f"{app_prefix}/fees/structures/",
        "fees_payment_url": f"{app_prefix}/fees/payments/record/",
        "fees_defaulters_url": f"{app_prefix}/fees/defaulters/",
        "fees_reports_url": f"{app_prefix}/fees/reports/",
        "fees_historical_arrears_url": f"{app_prefix}/fees/historical-arrears/add/",

        # Performance URLs
        "performance_url": f"{app_prefix}/performance/",
        "exams_url": f"{app_prefix}/exams/",
        "enter_results_url": f"{app_prefix}/enter-results/",
        "bulk_enter_results_url": f"{app_prefix}/bulk-enter-results/",
        "performance_reports_url": f"{app_prefix}/performance/reports/",

        # SMS URLs
        "sms_url": f"{app_prefix}/sms/dashboard/",

        # Parent Portal URLs
        "parent_url": f"{app_prefix}/parent/",
        "parent_login_url": f"{app_prefix}/parent/login/",
        "parent_dashboard_url": f"{app_prefix}/parent/dashboard/",
        "parent_fee_url": f"{app_prefix}/parent/fee/",

        # Other URLs
        "students_url": f"{app_prefix}/students/",
        "users_url": f"{app_prefix}/users/",
        "profile_url": f"{app_prefix}/profile/",
        "notifications_url": f"{app_prefix}/notifications/",
        "school_settings_url": f"{app_prefix}/school/settings/",
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
        }
    }
