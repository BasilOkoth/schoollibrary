from functools import wraps
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.models import User
from django.db import connection
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django_tenants.utils import schema_context

from tenants.models import School
from digitallibrary.models import TenantBackup, TenantRestoreLog
from .services import create_backup_file, restore_backup_file


def super_admin_required(view_func):
    """
    Backup-console access guard.

    Only Django superusers and staff users may access the backup console.
    This check is public-schema safe and does not use tenant UserProfile.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        next_url = quote(request.get_full_path())

        if not request.user.is_authenticated:
            return redirect(f"/login/?next={next_url}")

        allowed = request.user.is_superuser or request.user.is_staff

        if not allowed:
            messages.error(
                request,
                "Access denied. Super administrator privileges are required.",
            )
            return redirect("/tenants/super-admin/")

        return view_func(request, *args, **kwargs)

    return wrapper


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def _school_has_field(field_name):
    """
    Check whether tenants.models.School has a given field.
    """
    return any(
        field.name == field_name
        for field in School._meta.fields
    )


def _active_tenant_schools():
    """
    Return active tenant schools from the public schema.

    The public schema itself is never included.
    """
    schools = School.objects.exclude(schema_name="public")

    if _school_has_field("is_active"):
        schools = schools.filter(is_active=True)

    return schools.order_by("name")


def _tenant_name_for_school(school):
    """
    Safely get a tenant display name.
    """
    return (
        getattr(school, "name", None)
        or getattr(school, "school_name", None)
        or getattr(school, "schema_name", "")
        or "Unknown School"
    )


def _schema_from_path(request):
    """
    Extract tenant schema from paths like:
        /tenant/nyandago/app/tenant-backups/
    """
    path_parts = request.path.strip("/").split("/")

    if len(path_parts) >= 2 and path_parts[0] == "tenant":
        return path_parts[1]

    return None


def _first_active_tenant_schema():
    """
    Return the first available tenant schema from public School records.
    """
    with schema_context("public"):
        school = _active_tenant_schools().first()

        if school:
            return school.schema_name

    return None


def _resolve_schema_name(request, tenant_schema=None):
    """
    Resolve the tenant schema for backup operations.

    Priority:
    1. Explicit tenant_schema argument
    2. URL path /tenant/<schema>/...
    3. GET/POST tenant_schema or schema
    4. request.tenant or request.tenant_schema
    5. session backup_tenant_schema
    6. first active tenant school
    """
    schema_name = (
        tenant_schema
        or _schema_from_path(request)
        or request.GET.get("tenant_schema")
        or request.GET.get("schema")
        or request.GET.get("tenant")
        or request.POST.get("tenant_schema")
        or request.POST.get("schema")
        or request.POST.get("tenant")
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or request.session.get("backup_tenant_schema")
    )

    if not schema_name or str(schema_name).strip() in [
        "",
        "public",
        "None",
        "none",
        "null",
        "undefined",
    ]:
        schema_name = _first_active_tenant_schema()

    if schema_name:
        schema_name = str(schema_name).strip()
        request.session["backup_tenant_schema"] = schema_name
        request.session.modified = True

    return schema_name


def _backup_dashboard_url(schema_name=None):
    """
    Always return a tenant-aware backup dashboard URL.
    """
    if schema_name and schema_name != "public":
        return f"/tenant/{schema_name}/app/tenant-backups/"

    fallback_schema = _first_active_tenant_schema()

    if fallback_schema:
        return f"/tenant/{fallback_schema}/app/tenant-backups/"

    return "/tenants/super-admin/"


def _backup_all_url(schema_name):
    return f"/tenant/{schema_name}/app/tenant-backups/all/create/"


def _backup_single_url(schema_name, school_id):
    return f"/tenant/{schema_name}/app/tenant-backups/school/{school_id}/create/"


def _restore_url(schema_name, backup_id):
    return f"/tenant/{schema_name}/app/tenant-backups/{backup_id}/restore/"


def _create_tenant_backup_record(
    *,
    school,
    request,
    backup_type="manual",
    status="pending",
    notes="",
):
    """
    Create a TenantBackup row inside the tenant schema.

    The TenantBackup table exists inside each tenant schema, not public.
    """
    create_kwargs = {
        "school_id": school.pk,
        "tenant_schema": school.schema_name,
        "tenant_name": _tenant_name_for_school(school),
        "backup_type": backup_type,
        "status": status,
        "notes": notes,
    }

    # created_by may point to tenant auth_user. Only attach it if possible.
    try:
        if User.objects.filter(id=request.user.id).exists():
            create_kwargs["created_by"] = request.user
    except Exception:
        pass

    return TenantBackup.objects.create(**create_kwargs)


@super_admin_required
def backup_dashboard(request, tenant_schema=None):
    """
    Show tenant backups for the selected tenant.

    This view must run backup queries inside the selected tenant schema.
    It should not query TenantBackup from public.
    """
    schema_name = _resolve_schema_name(request, tenant_schema)

    if not schema_name:
        messages.error(
            request,
            "No tenant school was found. Please create a tenant first.",
        )
        return redirect("/tenants/super-admin/")

    with schema_context("public"):
        schools = list(_active_tenant_schools())
        selected_school = next(
            (
                school
                for school in schools
                if school.schema_name == schema_name
            ),
            None,
        )

    if not selected_school:
        messages.error(
            request,
            f"Tenant '{schema_name}' was not found.",
        )
        return redirect("/tenants/super-admin/")

    with schema_context(schema_name):
        backups = (
            TenantBackup.objects.select_related(
                "created_by",
                "restored_by",
            )
            .all()
            .order_by("-created_at")
        )

        restore_logs = (
            TenantRestoreLog.objects.select_related(
                "backup",
                "initiated_by",
            )
            .all()
            .order_by("-started_at")[:25]
        )

        context = {
            "backups": backups,
            "restore_logs": restore_logs,
            "schools": schools,
            "selected_school": selected_school,
            "selected_schema": schema_name,
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": f"/tenant/{schema_name}/app",
            "backup_dashboard_url": _backup_dashboard_url(schema_name),
            "backup_all_url": _backup_all_url(schema_name),
        }

    return render(
        request,
        "tenantbackups/dashboard.html",
        context,
    )


@super_admin_required
def backup_all_tenants(request, tenant_schema=None):
    """
    Back up every active tenant school.

    One TenantBackup row and one backup file are created for each tenant.
    Each backup record is stored inside that tenant's schema.
    """
    schema_name = _resolve_schema_name(request, tenant_schema)

    if request.method != "POST":
        return redirect(_backup_dashboard_url(schema_name))

    with schema_context("public"):
        schools = list(_active_tenant_schools())

    completed = 0
    failed = 0

    for school in schools:
        with schema_context(school.schema_name):
            backup = _create_tenant_backup_record(
                school=school,
                request=request,
                backup_type="manual",
                status="pending",
                notes="Created by Backup All Tenants.",
            )

        try:
            create_backup_file(backup)
            completed += 1

        except Exception as error:
            failed += 1

            with schema_context(school.schema_name):
                backup.status = "failed"
                backup.error_message = str(error)
                backup.completed_at = timezone.now()
                backup.save(
                    update_fields=[
                        "status",
                        "error_message",
                        "completed_at",
                    ]
                )

    if completed:
        messages.success(
            request,
            f"Backup completed for {completed} tenant(s).",
        )

    if failed:
        messages.warning(
            request,
            (
                f"{failed} tenant backup(s) failed. "
                "Check each backup record for details."
            ),
        )

    if not schools:
        messages.info(
            request,
            "No active tenant schools were found.",
        )

    return redirect(_backup_dashboard_url(schema_name))


@super_admin_required
def backup_single_tenant(request, school_id, tenant_schema=None):
    """
    Create a backup for one selected tenant.
    """
    schema_name = _resolve_schema_name(request, tenant_schema)

    if request.method != "POST":
        return redirect(_backup_dashboard_url(schema_name))

    with schema_context("public"):
        school = get_object_or_404(
            School,
            pk=school_id,
        )

        if school.schema_name == "public":
            messages.error(
                request,
                "The public schema cannot be backed up here.",
            )
            return redirect(_backup_dashboard_url(schema_name))

        if (
            _school_has_field("is_active")
            and not getattr(school, "is_active", True)
        ):
            messages.error(
                request,
                "This tenant school is inactive and cannot be backed up.",
            )
            return redirect(_backup_dashboard_url(schema_name))

    schema_name = school.schema_name

    with schema_context(schema_name):
        backup = _create_tenant_backup_record(
            school=school,
            request=request,
            backup_type="manual",
            status="pending",
        )

    try:
        create_backup_file(backup)

        messages.success(
            request,
            (
                f"{_tenant_name_for_school(school)} was backed up "
                "successfully."
            ),
        )

    except Exception as error:
        with schema_context(schema_name):
            backup.status = "failed"
            backup.error_message = str(error)
            backup.completed_at = timezone.now()
            backup.save(
                update_fields=[
                    "status",
                    "error_message",
                    "completed_at",
                ]
            )

        messages.error(
            request,
            (
                f"Backup failed for {_tenant_name_for_school(school)}: "
                f"{error}"
            ),
        )

    return redirect(_backup_dashboard_url(schema_name))


@super_admin_required
def restore_tenant_backup(request, backup_id, tenant_schema=None):
    """
    Restore only the tenant attached to the selected TenantBackup.

    There is intentionally no restore-all operation.
    """
    schema_name = _resolve_schema_name(request, tenant_schema)

    if request.method != "POST":
        return redirect(_backup_dashboard_url(schema_name))

    if not schema_name:
        messages.error(
            request,
            "Tenant context was not detected.",
        )
        return redirect("/tenants/super-admin/")

    with schema_context(schema_name):
        backup = get_object_or_404(
            TenantBackup,
            id=backup_id,
        )

        if not backup.can_restore:
            messages.error(
                request,
                (
                    "This backup cannot be restored. "
                    "It must be completed, verified, and "
                    "have a backup file."
                ),
            )
            return redirect(_backup_dashboard_url(schema_name))

        if (
            not backup.tenant_schema
            or backup.tenant_schema == "public"
        ):
            messages.error(
                request,
                "Invalid tenant backup selected.",
            )
            return redirect(_backup_dashboard_url(schema_name))

        restore_log_kwargs = {
            "backup": backup,
            "school_id": backup.school_id,
            "tenant_schema": backup.tenant_schema,
            "status": "pending",
            "ip_address": _client_ip(request),
        }

        try:
            if User.objects.filter(id=request.user.id).exists():
                restore_log_kwargs["initiated_by"] = request.user
        except Exception:
            pass

        restore_log = TenantRestoreLog.objects.create(
            **restore_log_kwargs
        )

        safety_backup_kwargs = {
            "school_id": backup.school_id,
            "tenant_schema": backup.tenant_schema,
            "tenant_name": backup.tenant_name,
            "backup_type": "pre_restore",
            "status": "pending",
            "notes": (
                f"Safety backup created before restoring "
                f"backup {backup.id}."
            ),
        }

        try:
            if User.objects.filter(id=request.user.id).exists():
                safety_backup_kwargs["created_by"] = request.user
        except Exception:
            pass

        safety_backup = TenantBackup.objects.create(
            **safety_backup_kwargs
        )

    try:
        create_backup_file(safety_backup)

    except Exception as error:
        with schema_context(schema_name):
            restore_log.status = "failed"
            restore_log.error_message = (
                "Pre-restore safety backup failed: "
                f"{error}"
            )
            restore_log.completed_at = timezone.now()
            restore_log.save(
                update_fields=[
                    "status",
                    "error_message",
                    "completed_at",
                ]
            )

        messages.error(
            request,
            (
                "Restore stopped because the safety "
                f"backup failed: {error}"
            ),
        )
        return redirect(_backup_dashboard_url(schema_name))

    try:
        restore_backup_file(
            backup=backup,
            restore_log=restore_log,
        )

        messages.success(
            request,
            (
                f"{backup.tenant_name} "
                f"({backup.tenant_schema}) was restored "
                "successfully. No other tenant was changed."
            ),
        )

    except Exception as error:
        messages.error(
            request,
            (
                f"Restore failed for "
                f"{backup.tenant_name}: {error}"
            ),
        )

    return redirect(_backup_dashboard_url(schema_name))
