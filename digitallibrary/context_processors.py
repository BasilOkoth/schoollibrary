# digitallibrary/context_processors.py

import logging

logger = logging.getLogger(__name__)


def school_settings(request):
    """
    Provides school settings and tenant information to templates.
    Safe version that won't crash if tables don't exist.
    """

    schema_name = "public"

    if hasattr(request, "tenant") and request.tenant:
        schema_name = request.tenant.schema_name

    context = {
        "school": None,
        "school_name": "ShuleHub",
        "school_logo": None,
        "school_motto": "Digital Learning Platform",
        "is_public_schema": schema_name == "public",
        "is_tenant_schema": schema_name != "public",
        "current_schema": schema_name,
    }

    if schema_name != "public":
        try:
            from .models import SchoolSetting

            school = SchoolSetting.objects.first()

            if school:
                context.update({
                    "school": school,
                    "school_name": school.name or "School System",
                    "school_logo": school.logo.url if getattr(school, "logo", None) else None,
                    "school_motto": school.motto or "",
                })

        except Exception as e:
            logger.warning(f"School settings context error: {e}")

    return context


def tenant_context(request):
    """
    Makes tenant information available globally to templates.
    """

    host = request.get_host().split(":")[0].lower()

    is_public_domain = host in [
        "shulehub.org",
        "www.shulehub.org",
        "schoollibrary.onrender.com",
        "schoollibrary-1.onrender.com",
    ]

    schema_name = "public"
    tenant_name = "Public"

    if hasattr(request, "tenant") and request.tenant:
        schema_name = request.tenant.schema_name
        tenant_name = getattr(request.tenant, "name", schema_name)

    is_public = (
        schema_name == "public"
        or is_public_domain
    )

    if not is_public and schema_name:
        app_prefix = f"/tenant/{schema_name}/app"
        tenant_url_prefix = f"/tenant/{schema_name}"
    else:
        app_prefix = "/app"
        tenant_url_prefix = ""

    return {
        "tenant_schema": schema_name,
        "tenant_name": tenant_name,

        "is_public_schema": is_public,
        "is_tenant_schema": not is_public,

        "current_host": host,
        "current_schema": schema_name,

        "app_prefix": app_prefix,
        "tenant_url_prefix": tenant_url_prefix,
    }
