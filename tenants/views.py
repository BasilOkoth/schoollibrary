from functools import wraps
from urllib.parse import quote

import logging
import traceback

from django.contrib import messages
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django_tenants.utils import schema_context

from .models import School, Domain
from .forms import TenantCreationForm, TenantUpdateForm, ResetPasswordForm


logger = logging.getLogger(__name__)


def force_public_schema(request=None):
    """
    Force the current database connection and request context to public schema.

    Super Admin users live in the public schema. This function prevents
    tenant-schema switching from making Django read the wrong auth_user table.
    """
    try:
        connection.set_schema_to_public()

        if request is not None:
            request.tenant_schema = "public"

            if hasattr(request, "session"):
                request.session["tenant_schema"] = "public"
                request.session.modified = True

    except Exception as error:
        logger.warning("Could not force public schema: %s", error)


def get_public_superuser_from_session(request):
    """
    Recover the authenticated public superuser directly from the session.

    This solves a django-tenants issue where request.user may be evaluated
    under a tenant schema, causing Django to think the public superuser is
    not logged in.
    """
    force_public_schema(request)

    user = getattr(request, "user", None)

    if user and user.is_authenticated and user.is_active and user.is_superuser:
        return user

    user_id = None

    try:
        user_id = request.session.get(SESSION_KEY)
    except Exception as error:
        logger.warning("Could not read user id from session: %s", error)

    if not user_id:
        return None

    try:
        with schema_context("public"):
            public_user = User.objects.get(
                pk=user_id,
                is_active=True,
                is_superuser=True,
            )

        request.user = public_user
        force_public_schema(request)

        return public_user

    except User.DoesNotExist:
        return None

    except Exception as error:
        logger.warning("Could not recover public superuser: %s", error)
        return None


def is_superuser(user):
    """
    Check if user is an active public-schema superuser.
    """
    return user.is_authenticated and user.is_active and user.is_superuser


def super_admin_required(view_func):
    """
    Super Admin decorator.

    This gives the public Django superuser full system rights:
    - manage all tenants
    - create tenants
    - delete tenants
    - edit tenant details
    - manage domains
    - reset tenant user passwords
    - run tenant migrations
    - access backup/superadmin dashboards

    Tenant admin/principal accounts remain limited to their own school.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        force_public_schema(request)

        public_superuser = get_public_superuser_from_session(request)

        if not public_superuser:
            messages.warning(
                request,
                "Please log in with your Super Admin account to continue.",
            )
            next_url = quote(request.get_full_path())
            return redirect(f"/login/?next={next_url}")

        request.user = public_superuser
        force_public_schema(request)

        return view_func(request, *args, **kwargs)

    return wrapper


@super_admin_required
def super_admin_dashboard(request):
    """
    Super Admin Dashboard - full control over all tenants.
    """
    force_public_schema(request)

    with schema_context("public"):
        schools = School.objects.all().order_by("-created_on")

        total_schools = schools.count()
        active_schools = schools.filter(is_active=True).count()
        inactive_schools = schools.filter(is_active=False).count()
        trial_schools = schools.filter(on_trial=True).count()
        total_domains = Domain.objects.count()

        paid_schools = schools.filter(
            paid_until__gte=timezone.now()
        ).count()

        expired_schools = schools.filter(
            paid_until__lt=timezone.now(),
            paid_until__isnull=False,
        ).count()

        tenant_data = []

        for school in schools:
            primary_domain = school.domains.filter(
                is_primary=True
            ).first()

            user_count = 0

            try:
                with schema_context(school.schema_name):
                    user_count = User.objects.count()
            except Exception as error:
                logger.warning(
                    "Could not count users for %s: %s",
                    school.schema_name,
                    error,
                )

            tenant_data.append(
                {
                    "school": school,
                    "primary_domain": (
                        primary_domain.domain
                        if primary_domain
                        else "No domain"
                    ),
                    "user_count": user_count,
                }
            )

    context = {
        "schools": tenant_data,
        "total_schools": total_schools,
        "active_schools": active_schools,
        "inactive_schools": inactive_schools,
        "trial_schools": trial_schools,
        "paid_schools": paid_schools,
        "expired_schools": expired_schools,
        "total_domains": total_domains,
        "is_super_admin_page": True,
        "is_public_schema": True,
        "tenant_schema": "public",
        "current_tenant_schema": "public",
        "tenant_base_url": "/tenants/super-admin",
        "tenant_dashboard_url": "/tenants/super-admin/",
    }

    return render(
        request,
        "tenants/super_admin/dashboard.html",
        context,
    )


@super_admin_required
def create_tenant(request):
    """
    Superuser-only view to create a tenant, create default principal/admin
    accounts, and assign ShuleHub domains.

    Assumes School.auto_create_schema = True in tenants/models.py.
    """
    force_public_schema(request)

    if request.method == "POST":
        form = TenantCreationForm(request.POST)

        if form.is_valid():
            school_name = form.cleaned_data["school_name"]

            schema_name = (
                form.cleaned_data["schema_name"]
                .lower()
                .strip()
                .replace(" ", "_")
                .replace("-", "_")
            )

            domain_slug = schema_name.replace("_", "-")

            primary_domain = f"{domain_slug}.shulehub.org"
            fallback_domain = (
                f"{domain_slug}."
                "schoollibrary-production-test.onrender.com"
            )

            principal_email = form.cleaned_data["principal_email"]
            administrator_email = form.cleaned_data["administrator_email"]

            tenant = None

            try:
                force_public_schema(request)

                if School.objects.filter(schema_name=schema_name).exists():
                    messages.error(
                        request,
                        f"Schema '{schema_name}' already exists.",
                    )
                    return redirect(request.path)

                if Domain.objects.filter(domain=primary_domain).exists():
                    messages.error(
                        request,
                        f"Domain '{primary_domain}' already exists.",
                    )
                    return redirect(request.path)

                # ------------------------------------------------------------
                # 1. Create tenant in public schema
                # ------------------------------------------------------------
                tenant = School.objects.create(
                    schema_name=schema_name,
                    name=school_name,
                    on_trial=True,
                    is_active=True,
                    paid_until=timezone.now()
                    + timezone.timedelta(days=30),
                )

                # School.auto_create_schema = True creates schema and runs
                # tenant migrations when the tenant is saved.

                # ------------------------------------------------------------
                # 2. Create domains in public schema
                # ------------------------------------------------------------
                force_public_schema(request)

                Domain.objects.create(
                    domain=primary_domain,
                    tenant=tenant,
                    is_primary=True,
                )

                Domain.objects.get_or_create(
                    domain=fallback_domain,
                    tenant=tenant,
                    defaults={
                        "is_primary": False,
                    },
                )

                # ------------------------------------------------------------
                # 3. Verify required tenant tables exist
                # ------------------------------------------------------------
                required_tables = [
                    "digitallibrary_userprofile",
                    "digitallibrary_gradingsystem",
                    "digitallibrary_schoolsetting",
                ]

                with connection.cursor() as cursor:
                    for table in required_tables:
                        cursor.execute(
                            """
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables
                                WHERE table_schema = %s
                                AND table_name = %s
                            );
                            """,
                            [schema_name, table],
                        )

                        table_exists = cursor.fetchone()[0]

                        if not table_exists:
                            raise Exception(
                                (
                                    f"Required table '{table}' was not "
                                    f"created in schema '{schema_name}'. "
                                    "Run: python manage.py migrate_schemas "
                                    f"--schema={schema_name}"
                                )
                            )

                # ------------------------------------------------------------
                # 4. Create default users and settings inside tenant schema
                # ------------------------------------------------------------
                with schema_context(schema_name):
                    from digitallibrary.models import (
                        UserProfile,
                        SchoolSetting,
                    )

                    principal, _ = User.objects.get_or_create(
                        username="principal",
                        defaults={
                            "email": principal_email,
                            "first_name": "School",
                            "last_name": "Principal",
                        },
                    )

                    principal.set_password("principal12345")
                    principal.email = principal_email
                    principal.first_name = "School"
                    principal.last_name = "Principal"
                    principal.is_staff = True
                    principal.is_superuser = False
                    principal.is_active = True
                    principal.save()

                    principal_profile, _ = UserProfile.objects.get_or_create(
                        user=principal,
                    )
                    principal_profile.role = "principal"
                    principal_profile.is_approved = True
                    principal_profile.save()

                    admin, _ = User.objects.get_or_create(
                        username="admin",
                        defaults={
                            "email": administrator_email,
                            "first_name": "School",
                            "last_name": "Admin",
                        },
                    )

                    admin.set_password("admin12345")
                    admin.email = administrator_email
                    admin.first_name = "School"
                    admin.last_name = "Admin"
                    admin.is_staff = True
                    admin.is_superuser = False
                    admin.is_active = True
                    admin.save()

                    admin_profile, _ = UserProfile.objects.get_or_create(
                        user=admin,
                    )
                    admin_profile.role = "admin"
                    admin_profile.is_approved = True
                    admin_profile.save()

                    # --------------------------------------------------------
                    # SchoolSetting model fields available:
                    # id, name, motto, phone, email, address, website, logo.
                    # Do NOT use school_name, primary_color, timezone, etc.
                    # --------------------------------------------------------
                    school_setting, _ = SchoolSetting.objects.get_or_create(
                        id=1,
                        defaults={
                            "name": school_name,
                            "motto": "Excellence in Education",
                            "phone": "+254700000000",
                            "email": f"info@{primary_domain}",
                            "address": "",
                            "website": f"https://{primary_domain}",
                        },
                    )

                    school_setting.name = school_name
                    school_setting.motto = (
                        school_setting.motto
                        or "Excellence in Education"
                    )
                    school_setting.phone = (
                        school_setting.phone
                        or "+254700000000"
                    )
                    school_setting.email = (
                        school_setting.email
                        or f"info@{primary_domain}"
                    )
                    school_setting.address = school_setting.address or ""
                    school_setting.website = (
                        school_setting.website
                        or f"https://{primary_domain}"
                    )
                    school_setting.save()

                # ------------------------------------------------------------
                # 5. Return super admin safely to public schema
                # ------------------------------------------------------------
                force_public_schema(request)

                messages.success(
                    request,
                    (
                        f"✅ Tenant '{school_name}' created successfully!\n\n"
                        f"🌐 Primary URL: https://{primary_domain}/app/\n"
                        f"🔁 Backup URL: https://{fallback_domain}/app/\n\n"
                        "👑 PRINCIPAL: principal / principal12345\n"
                        "⚙️ ADMIN: admin / admin12345"
                    ),
                )

                return redirect("/tenants/super-admin/")

            except Exception as error:
                error_details = traceback.format_exc()
                logger.error(
                    "Error creating tenant %s: %s\n%s",
                    school_name,
                    error,
                    error_details,
                )

                messages.error(
                    request,
                    f"Error creating tenant: {error}",
                )

                force_public_schema(request)

                if tenant:
                    schema_to_drop = tenant.schema_name
                    tenant_id = tenant.id

                    try:
                        force_public_schema(request)
                        Domain.objects.filter(tenant_id=tenant_id).delete()
                    except Exception:
                        pass

                    try:
                        force_public_schema(request)
                        school_table = School._meta.db_table
                        with connection.cursor() as cursor:
                            cursor.execute(
                                f'DELETE FROM "{school_table}" WHERE id = %s;',
                                [tenant_id],
                            )
                    except Exception:
                        pass

                    try:
                        force_public_schema(request)
                        with connection.cursor() as cursor:
                            cursor.execute(
                                (
                                    f'DROP SCHEMA IF EXISTS '
                                    f'"{schema_to_drop}" CASCADE;'
                                )
                            )
                    except Exception:
                        pass

                force_public_schema(request)
                return redirect(request.path)

        messages.error(
            request,
            "Please correct the errors below and try again.",
        )

    else:
        form = TenantCreationForm()

    force_public_schema(request)

    existing_tenants = School.objects.all().order_by("-created_on")[:10]

    return render(
        request,
        "tenants/create_tenant.html",
        {
            "form": form,
            "existing_tenants": existing_tenants,
            "total_tenants": School.objects.count(),
            "is_super_admin_page": True,
            "is_public_schema": True,
            "tenant_schema": "public",
            "current_tenant_schema": "public",
            "tenant_base_url": "/tenants/super-admin",
            "app_prefix": "/tenants/super-admin",
            "tenant_dashboard_url": "/tenants/super-admin/",
        },
    )


@super_admin_required
def tenant_dashboard(request):
    """
    Main tenant management dashboard showing all tenants.
    """
    force_public_schema(request)

    tenants = School.objects.all().order_by("-created_on")
    total_tenants = tenants.count()

    tenant_stats = []

    for tenant in tenants:
        primary_domain = tenant.domains.filter(is_primary=True).first()

        users_count = 0

        try:
            with schema_context(tenant.schema_name):
                users_count = User.objects.count()
        except Exception as error:
            logger.warning(
                "Could not count users for %s: %s",
                tenant.schema_name,
                error,
            )

        tenant_stats.append(
            {
                "tenant": tenant,
                "domain": (
                    primary_domain.domain
                    if primary_domain
                    else "No domain"
                ),
                "users_count": users_count,
            }
        )

    context = {
        "tenants": tenant_stats,
        "total_tenants": total_tenants,
        "is_super_admin_page": True,
        "is_public_schema": True,
        "tenant_schema": "public",
        "current_tenant_schema": "public",
        "tenant_base_url": "/tenants/super-admin",
        "app_prefix": "/tenants/super-admin",
        "tenant_dashboard_url": "/tenants/super-admin/",
    }

    return render(
        request,
        "tenants/dashboard.html",
        context,
    )


@super_admin_required
def tenant_detail(request, tenant_id):
    """
    View detailed information about a specific tenant.
    """
    force_public_schema(request)

    tenant = get_object_or_404(
        School,
        id=tenant_id,
    )
    domains = tenant.domains.all()
    primary_domain = domains.filter(is_primary=True).first()

    context = {
        "tenant": tenant,
        "domains": domains,
        "primary_domain": primary_domain,
        "tenant_id": tenant_id,
        "is_super_admin_page": True,
        "is_public_schema": True,
        "tenant_schema": "public",
        "current_tenant_schema": "public",
        "tenant_base_url": "/tenants/super-admin",
        "app_prefix": "/tenants/super-admin",
        "tenant_dashboard_url": "/tenants/super-admin/",
    }

    return render(
        request,
        "tenants/tenant_detail.html",
        context,
    )


@super_admin_required
def tenant_edit(request, tenant_id):
    """
    Edit tenant details.
    """
    force_public_schema(request)

    tenant = get_object_or_404(
        School,
        id=tenant_id,
    )

    if request.method == "POST":
        form = TenantUpdateForm(
            request.POST,
            instance=tenant,
        )

        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Tenant '{tenant.name}' updated successfully!",
            )
            return redirect(
                "tenants:tenant_detail",
                tenant_id=tenant.id,
            )

    else:
        form = TenantUpdateForm(instance=tenant)

    context = {
        "form": form,
        "tenant": tenant,
        "is_super_admin_page": True,
        "is_public_schema": True,
        "tenant_schema": "public",
        "current_tenant_schema": "public",
        "tenant_base_url": "/tenants/super-admin",
        "app_prefix": "/tenants/super-admin",
        "tenant_dashboard_url": "/tenants/super-admin/",
    }

    return render(
        request,
        "tenants/tenant_edit.html",
        context,
    )


@super_admin_required
def tenant_delete(request, tenant_id):
    """
    Delete a tenant completely from the public superadmin area.

    Safe deletion order:
    1. Force public schema
    2. Read tenant details from public schema
    3. Delete backup/restore records only if those tables exist
    4. Delete domains from public schema
    5. Delete School row from public schema
    6. Drop tenant schema
    """
    force_public_schema(request)

    with schema_context("public"):
        tenant = get_object_or_404(School, id=tenant_id)

        tenant_name = tenant.name
        schema_name = tenant.schema_name
        tenant_pk = tenant.pk

        if schema_name in ["public", "", None]:
            messages.error(request, "Cannot delete the public schema.")
            return redirect("/tenants/super-admin/")

        if request.method == "POST":
            try:
                force_public_schema(request)

                # ------------------------------------------------------------
                # 1. Delete backup/restore records safely
                # ------------------------------------------------------------
                with connection.cursor() as cursor:
                    # Check whether backup table exists
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_schema = 'public'
                            AND table_name = 'digitallibrary_tenantbackup'
                        );
                        """
                    )
                    tenantbackup_exists = cursor.fetchone()[0]

                    # Check whether restore log table exists
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_schema = 'public'
                            AND table_name = 'digitallibrary_tenantrestorelog'
                        );
                        """
                    )
                    tenantrestorelog_exists = cursor.fetchone()[0]

                    if tenantbackup_exists and tenantrestorelog_exists:
                        cursor.execute(
                            """
                            DELETE FROM digitallibrary_tenantrestorelog
                            WHERE backup_id IN (
                                SELECT id
                                FROM digitallibrary_tenantbackup
                                WHERE school_id = %s
                            );
                            """,
                            [tenant_pk],
                        )

                    if tenantbackup_exists:
                        cursor.execute(
                            """
                            DELETE FROM digitallibrary_tenantbackup
                            WHERE school_id = %s;
                            """,
                            [tenant_pk],
                        )

                # ------------------------------------------------------------
                # 2. Delete domains from public schema
                # ------------------------------------------------------------
                Domain.objects.filter(tenant_id=tenant_pk).delete()

                # ------------------------------------------------------------
                # 3. Delete the School row safely
                # ------------------------------------------------------------
                school_table = School._meta.db_table

                with connection.cursor() as cursor:
                    cursor.execute(
                        f'DELETE FROM "{school_table}" WHERE id = %s;',
                        [tenant_pk],
                    )

                # ------------------------------------------------------------
                # 4. Drop the tenant schema
                # ------------------------------------------------------------
                with connection.cursor() as cursor:
                    cursor.execute(
                        f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;'
                    )

                force_public_schema(request)

                messages.success(
                    request,
                    (
                        f"✅ Tenant '{tenant_name}' and schema "
                        f"'{schema_name}' have been deleted successfully."
                    ),
                )

                return redirect("/tenants/super-admin/")

            except Exception as error:
                force_public_schema(request)

                logger.error(
                    (
                        f"Error deleting tenant '{tenant_name}' "
                        f"with schema '{schema_name}': {error}"
                    )
                )

                messages.error(
                    request,
                    f"Error deleting tenant '{tenant_name}': {error}",
                )

                return redirect("/tenants/super-admin/")

        context = {
            "tenant": tenant,
            "tenant_schema": "public",
            "current_tenant_schema": "public",
            "tenant_base_url": "/tenants/super-admin",
            "app_prefix": "/tenants/super-admin",
            "tenant_dashboard_url": "/tenants/super-admin/",
            "is_super_admin_page": True,
            "is_public_schema": True,
        }

        return render(
            request,
            "tenants/tenant_delete_confirm.html",
            context,
        )
@super_admin_required
def reset_tenant_password(request, tenant_id):
    """
    Reset password for a user in a tenant.
    """
    force_public_schema(request)

    tenant = get_object_or_404(
        School,
        id=tenant_id,
    )

    if request.method == "POST":
        form = ResetPasswordForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            new_password = form.cleaned_data["new_password"]

            try:
                with schema_context(tenant.schema_name):
                    user = User.objects.get(username=username)
                    user.set_password(new_password)
                    user.save()

                force_public_schema(request)

                messages.success(
                    request,
                    (
                        f"Password for '{username}' in "
                        f"'{tenant.name}' has been reset!"
                    ),
                )

                return redirect(
                    "tenants:tenant_detail",
                    tenant_id=tenant.id,
                )

            except User.DoesNotExist:
                force_public_schema(request)

                messages.error(
                    request,
                    f"User '{username}' not found in '{tenant.name}'.",
                )

    else:
        form = ResetPasswordForm()

    force_public_schema(request)

    context = {
        "tenant": tenant,
        "form": form,
        "is_super_admin_page": True,
        "is_public_schema": True,
        "tenant_schema": "public",
        "current_tenant_schema": "public",
        "tenant_base_url": "/tenants/super-admin",
        "app_prefix": "/tenants/super-admin",
        "tenant_dashboard_url": "/tenants/super-admin/",
    }

    return render(
        request,
        "tenants/reset_password.html",
        context,
    )


@super_admin_required
def add_domain(request, tenant_id):
    """
    Add a new domain to a tenant.
    """
    force_public_schema(request)

    tenant = get_object_or_404(
        School,
        id=tenant_id,
    )

    if request.method == "POST":
        domain_name = request.POST.get("domain")
        is_primary = request.POST.get("is_primary") == "on"

        if domain_name:
            if Domain.objects.filter(domain=domain_name).exists():
                messages.error(
                    request,
                    f"Domain '{domain_name}' already exists!",
                )
            else:
                Domain.objects.create(
                    domain=domain_name,
                    tenant=tenant,
                    is_primary=is_primary,
                )

                if is_primary:
                    tenant.domains.exclude(
                        domain=domain_name,
                    ).update(
                        is_primary=False,
                    )

                messages.success(
                    request,
                    f"Domain '{domain_name}' added successfully!",
                )

    force_public_schema(request)

    return redirect(
        "tenants:tenant_detail",
        tenant_id=tenant.id,
    )


@super_admin_required
def remove_domain(request, domain_id):
    """
    Remove a domain from a tenant.
    """
    force_public_schema(request)

    domain = get_object_or_404(
        Domain,
        id=domain_id,
    )
    tenant_id = domain.tenant.id

    if domain.is_primary:
        messages.error(
            request,
            "Cannot remove primary domain.",
        )
    else:
        domain.delete()
        messages.success(
            request,
            f"Domain '{domain.domain}' removed successfully!",
        )

    force_public_schema(request)

    return redirect(
        "tenants:tenant_detail",
        tenant_id=tenant_id,
    )


@super_admin_required
def set_primary_domain(request, domain_id):
    """
    Set a domain as primary for its tenant.
    """
    force_public_schema(request)

    domain = get_object_or_404(
        Domain,
        id=domain_id,
    )
    tenant = domain.tenant

    tenant.domains.update(is_primary=False)
    domain.is_primary = True
    domain.save()

    messages.success(
        request,
        f"'{domain.domain}' is now the primary domain.",
    )

    force_public_schema(request)

    return redirect(
        "tenants:tenant_detail",
        tenant_id=tenant.id,
    )


@super_admin_required
def unified_super_admin_dashboard(request):
    """
    Unified Super Admin Dashboard - combines tenant management and backup management.
    Django 5.2-safe version.
    """
    import sys
    import django
    from pathlib import Path
    from django.conf import settings

    force_public_schema(request)

    with schema_context("public"):
        schools = School.objects.all().order_by("-created_on")

        total_schools = schools.count()
        active_schools = schools.filter(is_active=True).count()
        inactive_schools = schools.filter(is_active=False).count()
        trial_schools = schools.filter(on_trial=True).count()

        total_domains = Domain.objects.count()

        paid_schools = schools.filter(
            paid_until__gte=timezone.now()
        ).count()

        expired_schools = schools.filter(
            paid_until__lt=timezone.now(),
            paid_until__isnull=False,
        ).count()

        tenant_data = []

        for school in schools[:10]:
            primary_domain = school.domains.filter(
                is_primary=True,
            ).first()

            user_count = 0

            try:
                with schema_context(school.schema_name):
                    user_count = User.objects.count()
            except Exception as error:
                logger.warning(
                    "Could not count users for %s: %s",
                    school.schema_name,
                    error,
                )

            tenant_data.append(
                {
                    "school": school,
                    "primary_domain": (
                        primary_domain.domain
                        if primary_domain
                        else "No domain"
                    ),
                    "user_count": user_count,
                }
            )

    backup_stats = {
        "database_backups": [],
        "media_backups": [],
        "last_backup": None,
        "total_backups": 0,
        "error": None,
    }

    try:
        database_backup_dir = Path(
            getattr(
                settings,
                "DATABASE_BACKUP_DIR",
                settings.BASE_DIR / "backups" / "database",
            )
        )

        media_backup_dir = Path(
            getattr(
                settings,
                "MEDIA_BACKUP_DIR",
                settings.BASE_DIR / "backups" / "media",
            )
        )

        database_backup_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        media_backup_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        database_backups = []
        media_backups = []

        for pattern in [
            "*.json",
            "*.dump",
            "*.sql",
            "*.sqlite3",
            "*.backup",
        ]:
            database_backups.extend(database_backup_dir.glob(pattern))

        for pattern in [
            "*.tar.gz",
            "*.zip",
            "*.tar",
            "*.gz",
        ]:
            media_backups.extend(media_backup_dir.glob(pattern))

        database_backups = sorted(
            database_backups,
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        media_backups = sorted(
            media_backups,
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        backup_stats["database_backups"] = [
            f.name
            for f in database_backups[:5]
        ]
        backup_stats["media_backups"] = [
            f.name
            for f in media_backups[:5]
        ]
        backup_stats["total_backups"] = (
            len(database_backups)
            + len(media_backups)
        )

        if database_backups:
            backup_stats["last_backup"] = database_backups[0].name
        elif media_backups:
            backup_stats["last_backup"] = media_backups[0].name

    except Exception as error:
        logger.warning("Backup stats error: %s", error)
        backup_stats["error"] = str(error)

    system_stats = {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "django_version": django.get_version(),
        "database_size": "Unknown",
        "media_usage": "Unknown",
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_database_size(current_database())")
            db_size = cursor.fetchone()[0]
            system_stats["database_size"] = (
                f"{db_size / (1024 ** 3):.2f} GB"
            )
    except Exception as error:
        logger.warning("Could not get database size: %s", error)
        system_stats["database_size"] = "N/A"

    context = {
        "is_super_admin_page": True,
        "is_public_schema": True,
        "tenant_schema": "public",
        "current_tenant_schema": "public",
        "tenant_base_url": "/tenants/super-admin",
        "app_prefix": "/tenants/super-admin",
        "tenant_dashboard_url": "/tenants/super-admin/",
        "schools": tenant_data,
        "total_schools": total_schools,
        "active_schools": active_schools,
        "inactive_schools": inactive_schools,
        "trial_schools": trial_schools,
        "paid_schools": paid_schools,
        "expired_schools": expired_schools,
        "total_domains": total_domains,
        "backup_stats": backup_stats,
        "system_stats": system_stats,
        "current_time": timezone.now(),
    }

    return render(
        request,
        "tenants/super_admin/unified_dashboard.html",
        context,
    )


@super_admin_required
def fix_tenant_migrations(request, tenant_id):
    """
    Fix missing tables for an existing tenant by running migrations.
    """
    force_public_schema(request)

    tenant = get_object_or_404(
        School,
        id=tenant_id,
    )

    if request.method == "POST":
        try:
            call_command(
                "migrate_schemas",
                schema_name=tenant.schema_name,
                interactive=False,
                verbosity=2,
            )

            force_public_schema(request)

            messages.success(
                request,
                f"✅ Migrations successfully applied to '{tenant.name}'",
            )

        except Exception as error:
            force_public_schema(request)

            messages.error(
                request,
                (
                    f"❌ Error running migrations for "
                    f"'{tenant.name}': {error}"
                ),
            )

        return redirect(
            "tenants:tenant_detail",
            tenant_id=tenant.id,
        )

    force_public_schema(request)

    context = {
        "tenant": tenant,
        "is_super_admin_page": True,
        "is_public_schema": True,
        "tenant_schema": "public",
        "current_tenant_schema": "public",
        "tenant_base_url": "/tenants/super-admin",
        "app_prefix": "/tenants/super-admin",
        "tenant_dashboard_url": "/tenants/super-admin/",
    }

    return render(
        request,
        "tenants/fix_tenant_migrations.html",
        context,
    )
