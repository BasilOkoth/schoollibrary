# digitallibrary/decorators.py

import inspect
from functools import wraps
from urllib.parse import quote

from django.contrib import messages
from django.db import connection
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse
from django_tenants.utils import schema_context


PUBLIC_SCHEMA_NAME = "public"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _get_tenant_from_path(request):
    """
    Extract the schema from URLs such as:

        /tenant/nyandago/app/dashboard/
        /tenant/ngegemixed/app/upload/
    """
    path = (
        getattr(request, "path_info", "")
        or getattr(request, "path", "")
        or ""
    )

    parts = path.strip("/").split("/")

    if len(parts) >= 2 and parts[0] == "tenant":
        schema_name = parts[1].strip()

        if schema_name and schema_name != PUBLIC_SCHEMA_NAME:
            return schema_name

    return None


def _current_schema_name(request) -> str:
    """
    Return the currently active schema name.

    Path schema wins because the same browser may open two tenants
    at the same time, for example nyandago and ngegemixed.
    """
    path_schema = _get_tenant_from_path(request)

    if path_schema:
        return path_schema

    request_schema = getattr(request, "tenant_schema", None)

    if request_schema:
        return request_schema

    tenant = getattr(request, "tenant", None)
    tenant_schema = getattr(tenant, "schema_name", None)

    if tenant_schema:
        return tenant_schema

    schema_name = getattr(connection, "schema_name", None)

    if schema_name:
        return schema_name

    return PUBLIC_SCHEMA_NAME


def _is_public_schema(request) -> bool:
    return _current_schema_name(request) == PUBLIC_SCHEMA_NAME


def _set_tenant_on_request(request, tenant_schema=None):
    """
    Resolve and store the tenant schema on the request only.

    IMPORTANT:
    - The tenant in the current URL path wins.
    - Do NOT store tenant_schema in the session.
    - This prevents cross-tenant session collision when multiple
      tenants are open in the same browser.
    """
    path_schema = _get_tenant_from_path(request)

    tenant_schema = (
        tenant_schema
        or path_schema
        or getattr(request, "tenant_schema", None)
    )

    if not tenant_schema:
        request_tenant = getattr(request, "tenant", None)
        tenant_schema = getattr(
            request_tenant,
            "schema_name",
            None,
        )

    if (
        not tenant_schema
        or tenant_schema == PUBLIC_SCHEMA_NAME
    ):
        connection_schema = getattr(
            connection,
            "schema_name",
            None,
        )

        if (
            connection_schema
            and connection_schema != PUBLIC_SCHEMA_NAME
        ):
            tenant_schema = connection_schema

    if (
        tenant_schema
        and tenant_schema != PUBLIC_SCHEMA_NAME
    ):
        request.tenant_schema = tenant_schema
        return tenant_schema

    return None


def _call_view_safely(
    view_func,
    request,
    *args,
    **kwargs,
):
    """
    Call old and new views safely.

    Tenant URLs may pass tenant_schema even when an older view does not
    declare that parameter.
    """
    try:
        signature = inspect.signature(view_func)

        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )

        accepts_tenant_schema = (
            "tenant_schema"
            in signature.parameters
        )

        if (
            not accepts_kwargs
            and not accepts_tenant_schema
        ):
            kwargs.pop("tenant_schema", None)

    except (TypeError, ValueError):
        kwargs.pop("tenant_schema", None)

    return view_func(
        request,
        *args,
        **kwargs,
    )


def _get_available_tenants():
    """
    Return available non-public tenants.
    """
    try:
        from tenants.models import School

        return list(
            School.objects.exclude(
                schema_name=PUBLIC_SCHEMA_NAME,
            ).values(
                "id",
                "name",
                "schema_name",
            )
        )
    except Exception:
        return []


def _get_tenant_display(tenant_schema):
    """
    Return a human-readable school name for a schema.
    """
    if not tenant_schema:
        return "School"

    try:
        from tenants.models import School

        school = School.objects.filter(
            schema_name=tenant_schema,
        ).first()

        if school:
            return school.name

    except Exception:
        pass

    return tenant_schema.capitalize().replace(
        "_",
        " ",
    )


def _tenant_home_url(tenant_schema):
    if (
        tenant_schema
        and tenant_schema != PUBLIC_SCHEMA_NAME
    ):
        return f"/tenant/{tenant_schema}/app/"

    return "/app/"


def _tenant_dashboard_url(tenant_schema):
    if (
        tenant_schema
        and tenant_schema != PUBLIC_SCHEMA_NAME
    ):
        return f"/tenant/{tenant_schema}/app/dashboard/"

    return "/app/dashboard/"


def _tenant_login_url(
    tenant_schema,
    next_path=None,
):
    if (
        tenant_schema
        and tenant_schema != PUBLIC_SCHEMA_NAME
    ):
        base_url = f"/tenant/{tenant_schema}/app/login/"
    else:
        base_url = "/app/login/"

    if next_path:
        return (
            f"{base_url}?next="
            f"{quote(next_path, safe='/')}"
        )

    return base_url


def _resolve_redirect_target(
    target,
    request=None,
    tenant_schema=None,
):
    """
    Resolve a named URL or literal URL while preserving tenant context.

    For tenant requests, redirecting to digitallibrary:home should return
    the user to the tenant home rather than the public portal.
    """
    tenant_schema = (
        tenant_schema
        or (
            _set_tenant_on_request(request)
            if request is not None
            else None
        )
    )

    if target in {
        "digitallibrary:home",
        "home",
    }:
        return redirect(
            _tenant_home_url(tenant_schema)
        )

    if target in {
        "digitallibrary:dashboard",
        "dashboard",
    }:
        return redirect(
            _tenant_dashboard_url(tenant_schema)
        )

    if isinstance(target, str) and target.startswith("/"):
        return redirect(target)

    try:
        resolved = reverse(target)
    except NoReverseMatch:
        return redirect(
            _tenant_home_url(tenant_schema)
        )

    if (
        tenant_schema
        and tenant_schema != PUBLIC_SCHEMA_NAME
        and resolved.startswith("/app/")
    ):
        resolved = (
            f"/tenant/{tenant_schema}"
            f"{resolved}"
        )

    return redirect(resolved)


def _tenant_login_redirect(
    request,
    tenant_schema=None,
):
    """
    Redirect unauthenticated users to the correct school login page.

    Uses tenant from the current URL path first.
    """
    tenant_schema = (
        tenant_schema
        or _get_tenant_from_path(request)
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
    )

    return redirect(
        _tenant_login_url(
            tenant_schema,
            request.get_full_path(),
        )
    )


def _expand_allowed_roles(allowed_roles):
    """
    Expand inherited roles automatically.

    - deputy_principal inherits principal permissions.
    - director_of_studies gets academic/performance/exam access.
    """
    roles = {
        str(role).strip().lower()
        for role in (allowed_roles or [])
    }

    if "principal" in roles:
        roles.add("deputy_principal")
        roles.add("director_of_studies")

    if "teacher" in roles or "class_teacher" in roles:
        roles.add("director_of_studies")

    return roles


# ============================================================
# ROLE-BASED ACCESS DECORATORS
# ============================================================

def role_required(
    allowed_roles,
    redirect_to="digitallibrary:home",
):
    """
    Restrict access to authenticated users with one of the allowed roles.
    """
    allowed_roles = _expand_allowed_roles(allowed_roles)

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(
            request,
            *args,
            **kwargs,
        ):
            tenant_schema = (
                kwargs.get("tenant_schema")
                or _get_tenant_from_path(request)
                or _set_tenant_on_request(request)
            )

            if not request.user.is_authenticated:
                return _tenant_login_redirect(
                    request,
                    tenant_schema,
                )

            if request.user.is_superuser:
                return _call_view_safely(
                    view_func,
                    request,
                    *args,
                    **kwargs,
                )

            profile = getattr(
                request.user,
                "profile",
                None,
            )

            user_role = (
                getattr(profile, "role", "")
                or ""
            ).strip().lower()

            if user_role not in allowed_roles:
                label = (
                    user_role.capitalize()
                    if user_role
                    else "User"
                )

                messages.error(
                    request,
                    (
                        "Access denied. "
                        f"{label}s cannot access "
                        "this page."
                    ),
                )

                return _resolve_redirect_target(
                    redirect_to,
                    request=request,
                    tenant_schema=tenant_schema,
                )

            return _call_view_safely(
                view_func,
                request,
                *args,
                **kwargs,
            )

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
    Restrict a view to school tenant URLs.
    """
    valid_behaviors = {
        "redirect",
        "404",
        "403",
    }

    if behavior not in valid_behaviors:
        behavior = "redirect"

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(
            request,
            *args,
            **kwargs,
        ):
            tenant_schema = (
                kwargs.get("tenant_schema")
                or _get_tenant_from_path(request)
                or _set_tenant_on_request(request)
            )

            host = request.get_host().split(":")[0]

            is_localhost = host in {
                "localhost",
                "127.0.0.1",
            }

            has_tenant_path = bool(
                _get_tenant_from_path(request)
            )

            has_tenant_context = bool(
                tenant_schema
                and tenant_schema
                != PUBLIC_SCHEMA_NAME
            )

            if (
                not has_tenant_path
                and not has_tenant_context
                and (
                    _is_public_schema(request)
                    or is_localhost
                )
            ):
                if behavior == "404":
                    raise Http404("Page not found.")

                if behavior == "403":
                    return HttpResponseForbidden(
                        message or "Access denied."
                    )

                if message:
                    dynamic_message = message
                else:
                    tenants = _get_available_tenants()

                    if tenants:
                        school_names = ", ".join(
                            tenant["name"]
                            for tenant in tenants[:3]
                        )

                        if len(tenants) > 3:
                            school_names += (
                                f" and "
                                f"{len(tenants) - 3} more"
                            )

                        dynamic_message = (
                            "This feature is only "
                            "available through a school "
                            f"tenant URL. Schools: "
                            f"{school_names}."
                        )
                    else:
                        dynamic_message = (
                            "This feature is only "
                            "available through your "
                            "school tenant URL."
                        )

                messages.warning(
                    request,
                    dynamic_message,
                )

                return _resolve_redirect_target(
                    redirect_to,
                    request=request,
                    tenant_schema=tenant_schema,
                )

            return _call_view_safely(
                view_func,
                request,
                *args,
                **kwargs,
            )

        return wrapper

    return decorator


def public_only_view(
    redirect_to="digitallibrary:home",
    message=(
        "This page is only available "
        "from the public portal."
    ),
    behavior="redirect",
):
    """
    Restrict a view to the public schema.
    """
    valid_behaviors = {
        "redirect",
        "404",
        "403",
    }

    if behavior not in valid_behaviors:
        behavior = "redirect"

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(
            request,
            *args,
            **kwargs,
        ):
            tenant_schema = (
                _get_tenant_from_path(request)
                or _set_tenant_on_request(request)
            )

            if (
                tenant_schema
                or not _is_public_schema(request)
            ):
                if behavior == "404":
                    raise Http404("Page not found.")

                if behavior == "403":
                    return HttpResponseForbidden(
                        message
                    )

                messages.warning(
                    request,
                    message,
                )

                return _resolve_redirect_target(
                    redirect_to,
                    request=request,
                    tenant_schema=tenant_schema,
                )

            return _call_view_safely(
                view_func,
                request,
                *args,
                **kwargs,
            )

        return wrapper

    return decorator


# ============================================================
# CONVENIENCE ROLE DECORATORS
# ============================================================

def fees_access(view_func):
    return role_required([
        "admin",
        "principal",
        "bursar",
    ])(view_func)


def sms_access(view_func):
    return role_required([
        "admin",
        "principal",
        "bursar",
    ])(view_func)


def admin_principal_access(view_func):
    return role_required([
        "admin",
        "principal",
        "deputy_principal",
        "director_of_studies",
    ])(view_func)


def admin_only(view_func):
    return role_required([
        "admin",
    ])(view_func)


def teacher_access(view_func):
    """
    Role-only academic/teacher access.
    """
    return role_required([
        "teacher",
        "class_teacher",
        "director_of_studies",
        "admin",
        "principal",
        "deputy_principal",
    ])(view_func)


def student_access(view_func):
    return role_required([
        "student",
        "teacher",
        "class_teacher",
        "director_of_studies",
        "admin",
        "principal",
        "deputy_principal",
    ])(view_func)


# ============================================================
# TENANT APP PAGE DECORATORS
# ============================================================

def tenant_app_view(view_func):
    return tenant_only_view()(view_func)


def tenant_performance_access(view_func):
    return tenant_only_view()(view_func)


def tenant_exams_access(view_func):
    return tenant_only_view()(view_func)


def tenant_students_access(view_func):
    return tenant_only_view()(view_func)


def tenant_results_access(view_func):
    return tenant_only_view()(view_func)


def tenant_fees_access(view_func):
    return tenant_only_view()(view_func)


def tenant_teacher_access(view_func):
    return tenant_only_view()(view_func)


def tenant_library_access(view_func):
    return tenant_only_view()(view_func)


def tenant_printing_access(view_func):
    return tenant_only_view()(view_func)


# ============================================================
# COMBINED DECORATORS: ROLE + TENANT
# ============================================================

def tenant_and_role_required(
    allowed_roles,
    redirect_to="digitallibrary:home",
):
    """
    Require both a school tenant URL and an allowed user role.

    Important:
    - Resolves tenant from URL path first.
    - Checks authentication and role inside the correct tenant schema.
    - Does NOT hide real view errors by redirecting them to login.
    """
    allowed_roles = _expand_allowed_roles(allowed_roles)

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(
            request,
            *args,
            **kwargs,
        ):
            tenant_schema = (
                kwargs.get("tenant_schema")
                or _get_tenant_from_path(request)
                or getattr(request, "tenant_schema", None)
                or getattr(getattr(request, "tenant", None), "schema_name", None)
                or _set_tenant_on_request(request)
            )

            if (
                not tenant_schema
                or tenant_schema == PUBLIC_SCHEMA_NAME
            ):
                messages.warning(
                    request,
                    (
                        "This page is only available "
                        "through a school tenant URL."
                    ),
                )

                return _resolve_redirect_target(
                    redirect_to,
                    request=request,
                    tenant_schema=tenant_schema,
                )

            request.tenant_schema = tenant_schema

            if not request.user.is_authenticated:
                return _tenant_login_redirect(
                    request,
                    tenant_schema,
                )

            with schema_context(tenant_schema):
                if request.user.is_superuser:
                    return _call_view_safely(
                        view_func,
                        request,
                        *args,
                        **kwargs,
                    )

                profile = getattr(
                    request.user,
                    "profile",
                    None,
                )

                if not profile:
                    messages.error(
                        request,
                        "Your account profile was not found in this school tenant.",
                    )
                    return redirect(
                        _tenant_home_url(tenant_schema)
                    )

                user_role = (
                    getattr(profile, "role", "")
                    or ""
                ).strip().lower()

                is_approved = getattr(
                    profile,
                    "is_approved",
                    True,
                )

                if not is_approved:
                    messages.error(
                        request,
                        "Your account is not yet approved.",
                    )
                    return redirect(
                        _tenant_home_url(tenant_schema)
                    )

                if user_role not in allowed_roles:
                    label = (
                        user_role.capitalize()
                        if user_role
                        else "User"
                    )

                    messages.error(
                        request,
                        (
                            "Access denied. "
                            f"{label}s cannot access "
                            "this page."
                        ),
                    )

                    return _resolve_redirect_target(
                        redirect_to,
                        request=request,
                        tenant_schema=tenant_schema,
                    )

                return _call_view_safely(
                    view_func,
                    request,
                    *args,
                    **kwargs,
                )

        return wrapper

    return decorator


def teacher_required(view_func):
    """
    Tenant-aware decorator for teacher-facing, exam and performance pages.

    Director of Studies is included because this role manages:
    - exams
    - results
    - subjects
    - student-subject assignments
    - performance dashboards
    """
    return tenant_and_role_required([
        "teacher",
        "class_teacher",
        "director_of_studies",
        "admin",
        "principal",
        "deputy_principal",
    ])(view_func)


def academic_management_access(view_func):
    """
    Full academic management access.

    Use this for:
    - performance dashboard
    - exam list
    - exam creation/editing
    - results entry
    - bulk results
    - Excel result uploads
    - performance reports
    - subject management
    - student-subject assignment
    """
    return tenant_and_role_required([
        "admin",
        "principal",
        "deputy_principal",
        "director_of_studies",
        "teacher",
        "class_teacher",
    ])(view_func)


def performance_teacher_access(view_func):
    return academic_management_access(view_func)


def exams_management_access(view_func):
    return academic_management_access(view_func)


def results_management_access(view_func):
    return academic_management_access(view_func)


def subject_management_access(view_func):
    return academic_management_access(view_func)


def fees_officer_access(view_func):
    return tenant_and_role_required([
        "bursar",
        "admin",
        "principal",
        "deputy_principal",
    ])(view_func)


# ============================================================
# PARENT PORTAL DECORATORS
# ============================================================

def parent_session_required(view_func):
    """
    Require a valid OTP parent session.
    """
    @wraps(view_func)
    def wrapper(
        request,
        *args,
        **kwargs,
    ):
        tenant_schema = (
            kwargs.get("tenant_schema")
            or _get_tenant_from_path(request)
            or _set_tenant_on_request(request)
        )

        if not request.session.get("parent_phone"):
            messages.error(
                request,
                "Please log in to continue.",
            )

            if tenant_schema:
                return redirect(
                    (
                        f"/tenant/{tenant_schema}"
                        "/app/parent/login/"
                        f"?next={quote(request.path, safe='/')}"
                    )
                )

            return redirect(
                "/app/parent/login/"
            )

        return _call_view_safely(
            view_func,
            request,
            *args,
            **kwargs,
        )

    return wrapper
