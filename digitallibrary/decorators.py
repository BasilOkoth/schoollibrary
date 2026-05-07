# digitallibrary/decorators.py
from functools import wraps

from django.contrib import messages
from django.db import connection
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse


PUBLIC_SCHEMA_NAME = "public"


def _current_schema_name(request) -> str:
    if hasattr(connection, "schema_name") and connection.schema_name:
        return connection.schema_name
    tenant = getattr(request, "tenant", None)
    if tenant and getattr(tenant, "schema_name", None):
        return tenant.schema_name
    return PUBLIC_SCHEMA_NAME


def _is_public_schema(request) -> bool:
    return _current_schema_name(request) == PUBLIC_SCHEMA_NAME


def _get_tenant_from_path(request) -> str:
    """Extract tenant schema from URL path"""
    path = request.path_info
    if '/tenant/' in path:
        parts = path.split('/')
        if len(parts) >= 3 and parts[1] == 'tenant':
            return parts[2]
    return None


def _get_available_tenants():
    """Get list of available tenants with their names and schema names"""
    try:
        from tenants.models import School
        return list(School.objects.exclude(schema_name='public').values('id', 'name', 'schema_name'))
    except:
        return []


def _get_tenant_display(tenant_schema):
    """Get the school name for a given schema"""
    try:
        from tenants.models import School
        school = School.objects.filter(schema_name=tenant_schema).first()
        if school:
            return school.name
        return tenant_schema.capitalize().replace('_', ' ')
    except:
        return tenant_schema.capitalize().replace('_', ' ')


def _resolve_redirect_target(target: str):
    try:
        return redirect(target)
    except NoReverseMatch:
        try:
            return redirect(reverse(target))
        except NoReverseMatch:
            return redirect("digitallibrary:home")


# ============================================================
# ROLE-BASED ACCESS DECORATORS
# ============================================================

def role_required(allowed_roles, redirect_to="digitallibrary:home"):
    """Restrict access to authenticated users whose profile role is allowed."""
    allowed_roles = {role.lower() for role in allowed_roles}

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")

            try:
                user_role = (request.user.profile.role or "").strip().lower()
            except Exception:
                messages.error(request, "Access denied. Please contact the administrator.")
                return _resolve_redirect_target(redirect_to)

            if user_role not in allowed_roles:
                label = user_role.capitalize() if user_role else "User"
                messages.error(request, f"Access denied. {label}s cannot access this page.")
                return _resolve_redirect_target(redirect_to)

            return view_func(request, *args, **kwargs)

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
    Only blocks access when on EXACT localhost (not subdomains like miyuga.localhost).
    """
    valid_behaviors = {"redirect", "404", "403"}
    behavior = behavior if behavior in valid_behaviors else "redirect"

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            host = request.get_host()
            # Only block on exact localhost, NOT subdomains like miyuga.localhost
            is_exact_localhost = host in ['localhost:8000', '127.0.0.1:8000', 'localhost', '127.0.0.1']
            
            # Get tenant from path
            tenant_schema = _get_tenant_from_path(request)
            
            # Only block if on public schema OR exact localhost
            if _is_public_schema(request) or is_exact_localhost:
                if behavior == "404":
                    raise Http404("Page not found.")
                if behavior == "403":
                    return HttpResponseForbidden(message or "Access denied.")
                
                # Build dynamic message
                dynamic_message = None
                if message:
                    dynamic_message = message
                elif tenant_schema:
                    tenant_name = _get_tenant_display(tenant_schema)
                    dynamic_message = f"'{tenant_name}' features are only available through your school's domain. Please use {tenant_schema}.localhost:8000"
                else:
                    tenants = _get_available_tenants()
                    if tenants:
                        tenant_list = ', '.join([f"{t['name']} ({t['schema_name']}.localhost:8000)" for t in tenants[:3]])
                        if len(tenants) > 3:
                            remaining = len(tenants) - 3
                            tenant_list += f" and {remaining} more..."
                        dynamic_message = f"School features are only available through your school's domain. Available schools: {tenant_list}"
                    else:
                        dynamic_message = "School features are only available through your school's domain. Please contact your administrator."
                
                messages.warning(request, dynamic_message)
                return _resolve_redirect_target(redirect_to)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def public_only_view(
    redirect_to="digitallibrary:home",
    message="This page is only available from the public portal.",
    behavior="redirect",
):
    """Restrict public-only views from tenant schemas."""
    valid_behaviors = {"redirect", "404", "403"}
    behavior = behavior if behavior in valid_behaviors else "redirect"

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not _is_public_schema(request):
                if behavior == "404":
                    raise Http404("Page not found.")
                if behavior == "403":
                    return HttpResponseForbidden(message)

                messages.warning(request, message)
                return _resolve_redirect_target(redirect_to)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# CONVENIENCE DECORATORS
# ============================================================

def fees_access(view_func):
    """Allow admin, principal, and bursar to access fee pages"""
    return role_required(["admin", "principal", "bursar"])(view_func)


def sms_access(view_func):
    """Allow admin, principal, and bursar to access SMS features"""
    return role_required(["admin", "principal", "bursar"])(view_func)


def admin_principal_access(view_func):
    """Allow admin and principal only"""
    return role_required(["admin", "principal"])(view_func)


def admin_only(view_func):
    """Allow admin only"""
    return role_required(["admin"])(view_func)


def teacher_access(view_func):
    """Allow teachers and above (teacher, admin, principal)"""
    return role_required(["teacher", "admin", "principal"])(view_func)


def student_access(view_func):
    """Allow students and above"""
    return role_required(["student", "teacher", "admin", "principal"])(view_func)


# ============================================================
# TENANT APP PAGE DECORATORS
# ============================================================

def tenant_app_view(view_func):
    """Combined decorator for all tenant app views."""
    return tenant_only_view(
        redirect_to="digitallibrary:home",
        message=None
    )(view_func)


def tenant_performance_access(view_func):
    """Restrict performance pages to tenant schema only"""
    return tenant_only_view(redirect_to="digitallibrary:home", message=None)(view_func)


def tenant_exams_access(view_func):
    """Restrict exams pages to tenant schema only"""
    return tenant_only_view(redirect_to="digitallibrary:home", message=None)(view_func)


def tenant_students_access(view_func):
    """Restrict student pages to tenant schema only"""
    return tenant_only_view(redirect_to="digitallibrary:home", message=None)(view_func)


def tenant_results_access(view_func):
    """Restrict results pages to tenant schema only"""
    return tenant_only_view(redirect_to="digitallibrary:home", message=None)(view_func)


def tenant_fees_access(view_func):
    """Restrict fees pages to tenant schema only"""
    return tenant_only_view(redirect_to="digitallibrary:home", message=None)(view_func)


def tenant_teacher_access(view_func):
    """Restrict teacher pages to tenant schema only"""
    return tenant_only_view(redirect_to="digitallibrary:home", message=None)(view_func)


def tenant_library_access(view_func):
    """Restrict library pages to tenant schema only"""
    return tenant_only_view(redirect_to="digitallibrary:home", message=None)(view_func)


def tenant_printing_access(view_func):
    """Restrict printing pages to tenant schema only"""
    return tenant_only_view(redirect_to="digitallibrary:home", message=None)(view_func)


# ============================================================
# COMBINED DECORATORS (Role + Tenant)
# ============================================================

def tenant_and_role_required(allowed_roles, redirect_to="digitallibrary:home"):
    """Combine tenant protection and role requirement."""
    def decorator(view_func):
        @wraps(view_func)
        @tenant_only_view(redirect_to=redirect_to)
        @role_required(allowed_roles, redirect_to=redirect_to)
        def wrapper(request, *args, **kwargs):
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def performance_teacher_access(view_func):
    """Performance pages for teachers only (in tenant schema)"""
    return tenant_and_role_required(["teacher", "admin", "principal"])(view_func)


def fees_officer_access(view_func):
    """Fees pages for fees officers (bursar, admin, principal)"""
    return tenant_and_role_required(["bursar", "admin", "principal"])(view_func)