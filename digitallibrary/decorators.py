# digitallibrary/decorators.py

import inspect
from functools import wraps

from django.contrib import messages
from django.db import connection
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse


PUBLIC_SCHEMA_NAME = "public"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _current_schema_name(request) -> str:
    if hasattr(connection, "schema_name") and connection.schema_name:
        return connection.schema_name

    tenant = getattr(request, "tenant", None)
    if tenant and getattr(tenant, "schema_name", None):
        return tenant.schema_name

    return PUBLIC_SCHEMA_NAME


def _is_public_schema(request) -> bool:
    return _current_schema_name(request) == PUBLIC_SCHEMA_NAME


def _get_tenant_from_path(request):
    """
    Extract tenant schema from URLs like:
    /tenant/nyaneje/app/dashboard/
    """
    path = getattr(request, "path_info", "") or getattr(request, "path", "")

    parts = path.strip("/").split("/")

    if len(parts) >= 2 and parts[0] == "tenant":
        return parts[1]

    return None


def _set_tenant_on_request(request, tenant_schema=None):
    """
    Store tenant_schema on request and session.
    This does not replace django-tenants middleware;
    it only makes decorators/views/templates safer.
    """
    if not tenant_schema:
        tenant_schema = _get_tenant_from_path(request)

    if not tenant_schema:
        tenant_schema = getattr(request, "tenant_schema", None)

    if not tenant_schema and hasattr(request, "session"):
        tenant_schema = request.session.get("tenant_schema")

    if tenant_schema:
        request.tenant_schema = tenant_schema

        if hasattr(request, "session"):
            request.session["tenant_schema"] = tenant_schema
            request.session.modified = True

    return tenant_schema


def _call_view_safely(view_func, request, *args, **kwargs):
    """
    Prevents old views from crashing when tenant URLs pass tenant_schema.

    Example problem:
        URL passes tenant_schema='nyaneje'
        but view is written as def student_create(request)

    This helper removes tenant_schema only when the view does not accept it.
    """
    try:
        signature = inspect.signature(view_func)

        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in signature.parameters.values()
        )

        accepts_tenant_schema = "tenant_schema" in signature.parameters

        if not accepts_kwargs and not accepts_tenant_schema:
            kwargs.pop("tenant_schema", None)

    except Exception:
        # If inspection fails, avoid breaking the request.
        kwargs.pop("tenant_schema", None)

    return view_func(request, *args, **kwargs)


def _get_available_tenants():
    """
    Get list of available tenants with their names and schema names.
    """
    try:
        from tenants.models import School

        return list(
            School.objects.exclude(schema_name="public").values(
                "id",
                "name",
                "schema_name",
            )
        )
    except Exception:
        return []


def _get_tenant_display(tenant_schema):
    """
    Get the school name for a given schema.
    """
    try:
        from tenants.models import School

        school = School.objects.filter(schema_name=tenant_schema).first()

        if school:
            return school.name

        return tenant_schema.capitalize().replace("_", " ")

    except Exception:
        return tenant_schema.capitalize().replace("_", " ")


def _resolve_redirect_target(target: str):
    """
    Redirect safely whether target is a URL name or fallback.
    """
    try:
        return redirect(target)
    except NoReverseMatch:
        try:
            return redirect(reverse(target))
        except NoReverseMatch:
            return redirect("/")


def _tenant_login_redirect(request, tenant_schema=None):
    """
    Send unauthenticated tenant users to the correct tenant login page.
    """
    tenant_schema = tenant_schema or _get_tenant_from_path(request)

    if tenant_schema:
        return redirect(
            f"/tenant/{tenant_schema}/app/login/?next={request.path}"
        )

    return redirect("login")


# ============================================================
# ROLE-BASED ACCESS DECORATORS
# ============================================================

def role_required(allowed_roles, redirect_to="digitallibrary:home"):
    """
    Restrict access to authenticated users whose profile role is allowed.
    """
    allowed_roles = {role.lower() for role in allowed_roles}

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            tenant_schema = kwargs.get("tenant_schema") or _set_tenant_on_request(request)

            if not request.user.is_authenticated:
                return _tenant_login_redirect(request, tenant_schema)

            try:
                profile = getattr(request.user, "profile", None)
                user_role = (getattr(profile, "role", "") or "").strip().lower()

            except Exception:
                messages.error(
                    request,
                    "Access denied. Please contact the administrator.",
                )
                return _resolve_redirect_target(redirect_to)

            if user_role not in allowed_roles:
                label = user_role.capitalize() if user_role else "User"
                messages.error(
                    request,
                    f"Access denied. {label}s cannot access this page.",
                )
                return _resolve_redirect_target(redirect_to)

            return _call_view_safely(view_func, request, *args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# TENANT PROTECTION DECORATORS
# ============================================================

def tenant_only_view(
    redirect_to="digitallibrary:home",
    message=None,
    behavior="redirect",
):
    """
    Restrict tenant-only views from the public schema.

    Updated for subfolder tenants like:
    /tenant/nyaneje/app/...
    """
    valid_behaviors = {"redirect", "404", "403"}
    behavior = behavior if behavior in valid_behaviors else "redirect"

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            tenant_schema = kwargs.get("tenant_schema") or _set_tenant_on_request(request)

            host = request.get_host()

            is_exact_localhost = host in [
                "localhost:8000",
                "127.0.0.1:8000",
                "localhost",
                "127.0.0.1",
            ]

            has_tenant_path = bool(tenant_schema)

            # If URL contains /tenant/<schema>/..., allow it even if
            # connection.schema_name still temporarily says public.
            if not has_tenant_path and (_is_public_schema(request) or is_exact_localhost):
                if behavior == "404":
                    raise Http404("Page not found.")

                if behavior == "403":
                    return HttpResponseForbidden(message or "Access denied.")

                if message:
                    dynamic_message = message
                else:
                    tenants = _get_available_tenants()

                    if tenants:
                        tenant_list = ", ".join(
                            [
                                f"{t['name']} ({t['schema_name']}.localhost:8000)"
                                for t in tenants[:3]
                            ]
                        )

                        if len(tenants) > 3:
                            remaining = len(tenants) - 3
                            tenant_list += f" and {remaining} more..."

                        dynamic_message = (
                            "School features are only available through your "
                            f"school's tenant URL. Available schools: {tenant_list}"
                        )
                    else:
                        dynamic_message = (
                            "School features are only available through your "
                            "school's tenant URL. Please contact your administrator."
                        )

                messages.warning(request, dynamic_message)
                return _resolve_redirect_target(redirect_to)

            return _call_view_safely(view_func, request, *args, **kwargs)

        return wrapper

    return decorator


def public_only_view(
    redirect_to="digitallibrary:home",
    message="This page is only available from the public portal.",
    behavior="redirect",
):
    """
    Restrict public-only views from tenant schemas.
    """
    valid_behaviors = {"redirect", "404", "403"}
    behavior = behavior if behavior in valid_behaviors else "redirect"

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            _set_tenant_on_request(request)

            if not _is_public_schema(request):
                if behavior == "404":
                    raise Http404("Page not found.")

                if behavior == "403":
                    return HttpResponseForbidden(message)

                messages.warning(request, message)
                return _resolve_redirect_target(redirect_to)

            return _call_view_safely(view_func, request, *args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# CONVENIENCE ROLE DECORATORS
# ============================================================

def fees_access(view_func):
    """
    Allow admin, principal, and bursar to access fee pages.
    """
    return role_required(["admin", "principal", "bursar"])(view_func)


def sms_access(view_func):
    """
    Allow admin, principal, and bursar to access SMS features.
    """
    return role_required(["admin", "principal", "bursar"])(view_func)


def admin_principal_access(view_func):
    """
    Allow admin and principal only.
    """
    return role_required(["admin", "principal"])(view_func)


def admin_only(view_func):
    """
    Allow admin only.
    """
    return role_required(["admin"])(view_func)


def teacher_access(view_func):
    """
    Allow teachers and above.
    """
    return role_required(["teacher", "admin", "principal"])(view_func)


def student_access(view_func):
    """
    Allow students and above.
    """
    return role_required(["student", "teacher", "admin", "principal"])(view_func)


# ============================================================
# TENANT APP PAGE DECORATORS
# ============================================================

def tenant_app_view(view_func):
    """
    Combined decorator for all tenant app views.
    """
    return tenant_only_view(
        redirect_to="digitallibrary:home",
        message=None,
    )(view_func)


def tenant_performance_access(view_func):
    """
    Restrict performance pages to tenant schema only.
    """
    return tenant_only_view(
        redirect_to="digitallibrary:home",
        message=None,
    )(view_func)


def tenant_exams_access(view_func):
    """
    Restrict exams pages to tenant schema only.
    """
    return tenant_only_view(
        redirect_to="digitallibrary:home",
        message=None,
    )(view_func)


def tenant_students_access(view_func):
    """
    Restrict student pages to tenant schema only.
    """
    return tenant_only_view(
        redirect_to="digitallibrary:home",
        message=None,
    )(view_func)


def tenant_results_access(view_func):
    """
    Restrict results pages to tenant schema only.
    """
    return tenant_only_view(
        redirect_to="digitallibrary:home",
        message=None,
    )(view_func)


def tenant_fees_access(view_func):
    """
    Restrict fees pages to tenant schema only.
    """
    return tenant_only_view(
        redirect_to="digitallibrary:home",
        message=None,
    )(view_func)


def tenant_teacher_access(view_func):
    """
    Restrict teacher pages to tenant schema only.
    """
    return tenant_only_view(
        redirect_to="digitallibrary:home",
        message=None,
    )(view_func)


def tenant_library_access(view_func):
    """
    Restrict library pages to tenant schema only.
    """
    return tenant_only_view(
        redirect_to="digitallibrary:home",
        message=None,
    )(view_func)


def tenant_printing_access(view_func):
    """
    Restrict printing pages to tenant schema only.
    """
    return tenant_only_view(
        redirect_to="digitallibrary:home",
        message=None,
    )(view_func)


# ============================================================
# COMBINED DECORATORS: ROLE + TENANT
# ============================================================

def tenant_and_role_required(allowed_roles, redirect_to="digitallibrary:home"):
    """
    Combine tenant protection and role requirement.
    """
    allowed_roles = {role.lower() for role in allowed_roles}

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            tenant_schema = kwargs.get("tenant_schema") or _set_tenant_on_request(request)

            # Tenant protection
            if not tenant_schema and _is_public_schema(request):
                messages.warning(
                    request,
                    "This page is only available through a school tenant URL.",
                )
                return _resolve_redirect_target(redirect_to)

            # Login protection
            if not request.user.is_authenticated:
                return _tenant_login_redirect(request, tenant_schema)

            # Role protection
            try:
                profile = getattr(request.user, "profile", None)
                user_role = (getattr(profile, "role", "") or "").strip().lower()

            except Exception:
                messages.error(
                    request,
                    "Access denied. Please contact the administrator.",
                )
                return _resolve_redirect_target(redirect_to)

            if user_role not in allowed_roles:
                label = user_role.capitalize() if user_role else "User"
                messages.error(
                    request,
                    f"Access denied. {label}s cannot access this page.",
                )
                return _resolve_redirect_target(redirect_to)

            return _call_view_safely(view_func, request, *args, **kwargs)

        return wrapper

    return decorator


def performance_teacher_access(view_func):
    """
    Performance pages for teachers only in tenant schema.
    """
    return tenant_and_role_required(
        ["teacher", "admin", "principal"]
    )(view_func)


def fees_officer_access(view_func):
    """
    Fees pages for fees officers.
    """
    return tenant_and_role_required(
        ["bursar", "admin", "principal"]
    )(view_func)


# ============================================================
# PARENT PORTAL DECORATORS
# ============================================================

def parent_session_required(view_func):
    """
    Ensure parent is authenticated through OTP session.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        _set_tenant_on_request(request)

        if not request.session.get("parent_phone"):
            messages.error(request, "Please login to continue.")

            tenant_schema = kwargs.get("tenant_schema") or _get_tenant_from_path(request)

            if tenant_schema:
                return redirect(
                    f"/tenant/{tenant_schema}/app/parents/login/?next={request.path}"
                )

            return redirect("digitallibrary:parent_login")

        return _call_view_safely(view_func, request, *args, **kwargs)

    return wrapper
