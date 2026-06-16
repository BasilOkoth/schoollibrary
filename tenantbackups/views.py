from functools import wraps

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django_tenants.utils import schema_context

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


def _backup_school_model():
    """
    Return the exact School model expected by TenantBackup.school.

    This avoids the common multi-app error:
    Cannot assign '<School ...>': 'TenantBackup.school' must be a
    'School' instance.
    """
    return TenantBackup._meta.get_field(
        "school"
    ).remote_field.model


@super_admin_required
def backup_dashboard(request):
    """
    Show all tenant backups.

    Each row represents one tenant and therefore has its
    own independent restore button.
    """
    SchoolModel = _backup_school_model()

    with schema_context("public"):
        backups = (
            TenantBackup.objects.select_related(
                "school",
                "created_by",
                "restored_by",
            )
            .all()
        )

        restore_logs = (
            TenantRestoreLog.objects.select_related(
                "backup",
                "school",
                "initiated_by",
            )
            .all()[:25]
        )

        schools = (
            SchoolModel.objects.exclude(
                schema_name="public"
            )
            .order_by("name")
        )

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

    SchoolModel = _backup_school_model()

    with schema_context("public"):
        schools_query = (
            SchoolModel.objects.exclude(
                schema_name="public"
            )
            .order_by("name")
        )

        # Some School models have is_active; some do not.
        if any(
            field.name == "is_active"
            for field in SchoolModel._meta.fields
        ):
            schools_query = schools_query.filter(
                is_active=True
            )

        schools = list(schools_query)

    completed = 0
    failed = 0

    for school in schools:
        with schema_context("public"):
            backup = TenantBackup.objects.create(
                school=school,
                backup_type="manual",
                status="pending",
                created_by=request.user,
                notes=(
                    "Created by Backup All Tenants."
                ),
            )

        try:
            create_backup_file(backup)
            completed += 1

        except Exception as error:
            failed += 1

            with schema_context("public"):
                backup.status = "failed"
                backup.error_message = str(error)
                backup.save(
                    update_fields=[
                        "status",
                        "error_message",
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

    SchoolModel = _backup_school_model()

    with schema_context("public"):
        school = get_object_or_404(
            SchoolModel,
            pk=school_id,
        )

        if school.schema_name == "public":
            messages.error(
                request,
                "The public schema cannot be backed up here.",
            )
            return redirect("tenantbackups:dashboard")

        backup = TenantBackup.objects.create(
            school=school,
            backup_type="manual",
            status="pending",
            created_by=request.user,
        )

    try:
        create_backup_file(backup)

        messages.success(
            request,
            (
                f"{school.name} was backed up "
                "successfully."
            ),
        )

    except Exception as error:
        messages.error(
            request,
            (
                f"Backup failed for {school.name}: "
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
            TenantBackup.objects.select_related(
                "school"
            ),
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
            backup.school.schema_name
            != backup.tenant_schema
        ):
            messages.error(
                request,
                (
                    "The backup tenant does not match "
                    "the selected school."
                ),
            )
            return redirect("tenantbackups:dashboard")

        restore_log = TenantRestoreLog.objects.create(
            backup=backup,
            school=backup.school,
            tenant_schema=backup.tenant_schema,
            status="pending",
            initiated_by=request.user,
            ip_address=_client_ip(request),
        )

        safety_backup = TenantBackup.objects.create(
            school=backup.school,
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
