from functools import wraps

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django_tenants.utils import schema_context

from tenants.models import School

from digitallibrary.models import TenantBackup, TenantRestoreLog
from .services import create_backup_file, restore_backup_file


def super_admin_required(view_func):
    """
    Allow only the ShuleHub super administrator.

    This does not use staff_member_required, so it will not
    redirect an authenticated super admin to /admin/login/.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(
                f"/login/?next={request.get_full_path()}"
            )

        profile = getattr(
            request.user,
            "profile",
            None,
        )

        role = (
            getattr(profile, "role", "")
            or ""
        ).strip().lower()

        allowed = (
            request.user.is_superuser
            or request.user.is_staff
            or role in {
                "super_admin",
                "superadmin",
            }
        )

        if not allowed:
            messages.error(
                request,
                (
                    "Access denied. Super administrator "
                    "privileges are required."
                ),
            )
            return redirect("/tenants/super-admin/")

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapper


def _client_ip(request):
    forwarded_for = request.META.get(
        "HTTP_X_FORWARDED_FOR"
    )

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def _school_has_field(field_name):
    """
    Check whether tenants.models.School has a given field.

    This keeps the backup page safe across slightly different
    School model versions.
    """
    return any(
        field.name == field_name
        for field in School._meta.fields
    )


def _active_tenant_schools():
    """
    Return tenant schools from tenants.models.School.

    These are the actual schools that appear in the tenant
    dropdown. The public schema is never included.
    """
    schools = School.objects.exclude(
        schema_name="public"
    )

    if _school_has_field("is_active"):
        schools = schools.filter(
            is_active=True
        )

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


def _create_tenant_backup_record(
    *,
    school,
    request,
    backup_type="manual",
    status="pending",
    notes="",
):
    """
    Create a TenantBackup row without assigning a School object.

    This avoids model-class mismatch errors such as:
    Cannot assign '<School ...>': 'TenantBackup.school' must be
    a 'School' instance.

    We use school_id plus tenant_schema and tenant_name.
    """
    return TenantBackup.objects.create(
        school_id=school.pk,
        tenant_schema=school.schema_name,
        tenant_name=_tenant_name_for_school(school),
        backup_type=backup_type,
        status=status,
        created_by=request.user,
        notes=notes,
    )


@super_admin_required
def backup_dashboard(request):
    """
    Show all tenant backups.

    Each row represents one tenant and therefore has its
    own independent restore button.
    """
    with schema_context("public"):
        backups = (
            TenantBackup.objects.select_related(
                "created_by",
                "restored_by",
            )
            .all()
        )

        restore_logs = (
            TenantRestoreLog.objects.select_related(
                "backup",
                "initiated_by",
            )
            .all()[:25]
        )

        schools = _active_tenant_schools()

        context = {
            "backups": backups,
            "restore_logs": restore_logs,
            "schools": schools,
        }

    return render(
        request,
        "tenantbackups/dashboard.html",
        context,
    )


@super_admin_required
def backup_all_tenants(request):
    """
    Back up every active tenant school.

    One TenantBackup row and one backup file are created
    for each tenant. This is what makes single-tenant
    restoration possible.
    """
    if request.method != "POST":
        return redirect("tenantbackups:dashboard")

    with schema_context("public"):
        schools = list(
            _active_tenant_schools()
        )

    completed = 0
    failed = 0

    for school in schools:
        with schema_context("public"):
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

            with schema_context("public"):
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
            (
                f"Backup completed for {completed} "
                f"tenant(s)."
            ),
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

    return redirect("tenantbackups:dashboard")


@super_admin_required
def backup_single_tenant(request, school_id):
    """
    Create a backup for one selected tenant.
    """
    if request.method != "POST":
        return redirect("tenantbackups:dashboard")

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
            return redirect("tenantbackups:dashboard")

        if (
            _school_has_field("is_active")
            and not getattr(school, "is_active", True)
        ):
            messages.error(
                request,
                "This tenant school is inactive and cannot be backed up.",
            )
            return redirect("tenantbackups:dashboard")

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
        with schema_context("public"):
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

    return redirect("tenantbackups:dashboard")


@super_admin_required
def restore_tenant_backup(request, backup_id):
    """
    Restore only the tenant attached to the selected
    TenantBackup UUID.

    There is intentionally no restore-all operation.
    """
    if request.method != "POST":
        return redirect("tenantbackups:dashboard")

    with schema_context("public"):
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
            return redirect("tenantbackups:dashboard")

        if (
            not backup.tenant_schema
            or backup.tenant_schema == "public"
        ):
            messages.error(
                request,
                "Invalid tenant backup selected.",
            )
            return redirect("tenantbackups:dashboard")

        restore_log = TenantRestoreLog.objects.create(
            backup=backup,
            school_id=backup.school_id,
            tenant_schema=backup.tenant_schema,
            status="pending",
            initiated_by=request.user,
            ip_address=_client_ip(request),
        )

        safety_backup = TenantBackup.objects.create(
            school_id=backup.school_id,
            tenant_schema=backup.tenant_schema,
            tenant_name=backup.tenant_name,
            backup_type="pre_restore",
            status="pending",
            created_by=request.user,
            notes=(
                f"Safety backup created before restoring "
                f"backup {backup.id}."
            ),
        )

    try:
        create_backup_file(safety_backup)

    except Exception as error:
        with schema_context("public"):
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
        return redirect("tenantbackups:dashboard")

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

    return redirect("tenantbackups:dashboard")
