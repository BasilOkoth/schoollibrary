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
    tenant_schema = None

    path = getattr(request, "path", "") or ""

    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "tenant":
        tenant_schema = parts[1]

    if not tenant_schema or tenant_schema == "public":
        tenant_schema = getattr(request, "tenant_schema", None)

    if (not tenant_schema or tenant_schema == "public") and hasattr(request, "tenant"):
        tenant_schema = getattr(request.tenant, "schema_name", None)

    if (not tenant_schema or tenant_schema == "public") and hasattr(request, "session"):
        tenant_schema = request.session.get("tenant_schema")

    if not tenant_schema or tenant_schema == "public":
        tenant_schema = "nyaneje"

    return {
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant": getattr(request, "tenant", None),
    }

def tenant_urls(request):
    tenant_schema = None

    path = getattr(request, "path", "") or ""

    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "tenant":
        tenant_schema = parts[1]

    if not tenant_schema or tenant_schema == "public":
        tenant_schema = getattr(request, "tenant_schema", None)

    if (not tenant_schema or tenant_schema == "public") and hasattr(request, "session"):
        tenant_schema = request.session.get("tenant_schema")

    if not tenant_schema or tenant_schema == "public":
        tenant_schema = "nyaneje"

    base = f"/tenant/{tenant_schema}/app"

    return {
        "tenant_base_url": base,
        "tenant_dashboard_url": f"{base}/dashboard/",
        "tenant_login_url": f"{base}/login/",
        "tenant_admin_dashboard_url": f"{base}/admin/dashboard/",
        "tenant_students_url": f"{base}/students/",
        "tenant_student_create_url": f"{base}/students/create/",
        "tenant_tv_dashboard_url": f"{base}/tv/dashboard/",
        "tenant_fees_dashboard_url": f"{base}/fees/dashboard/",
        "tenant_performance_url": f"{base}/performance/",
        "tenant_library_url": f"{base}/library/",
    }
