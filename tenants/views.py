from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.management import call_command
from django_tenants.utils import schema_context
from django.db import connection
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
import logging

from .models import School, Domain
from .forms import TenantCreationForm, TenantUpdateForm, ResetPasswordForm

logger = logging.getLogger(__name__)


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_authenticated and user.is_superuser


def super_admin_required(view_func):
    """Decorator to ensure user is super admin"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/login/")

        if not request.user.is_superuser:
            return HttpResponseForbidden("Access denied. Super admin privileges required.")

        return view_func(request, *args, **kwargs)

    return wrapper


@login_required
@super_admin_required
def super_admin_dashboard(request):
    """
    Super Admin Dashboard - Full control over all tenants
    """
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
            primary_domain = school.domains.filter(is_primary=True).first()

            user_count = 0

            try:
                with schema_context(school.schema_name):
                    user_count = User.objects.count()
            except Exception as e:
                print(f"⚠️ Could not count users for {school.schema_name}: {e}")
                user_count = 0

            tenant_data.append({
                "school": school,
                "primary_domain": primary_domain.domain if primary_domain else "No domain",
                "user_count": user_count,
            })

    context = {
        "schools": tenant_data,
        "total_schools": total_schools,
        "active_schools": active_schools,
        "inactive_schools": inactive_schools,
        "trial_schools": trial_schools,
        "paid_schools": paid_schools,
        "expired_schools": expired_schools,
        "total_domains": total_domains,
    }

    return render(request, "tenants/super_admin/dashboard.html", context)


@login_required
@user_passes_test(is_superuser)
def create_tenant(request):
    """
    Superuser-only view to create a tenant, run migrations,
    create principal/admin accounts, and automatically assign ShuleHub domains.

    Example:
    schema_name: nyandago
    primary domain: nyandago.shulehub.org
    fallback domain: nyandago.schoollibrary-1.onrender.com
    """
    if request.method == "POST":
        form = TenantCreationForm(request.POST)

        if form.is_valid():
            school_name = form.cleaned_data["school_name"]

            # Keep schema safe for PostgreSQL: use underscores, not hyphens
            schema_name = (
                form.cleaned_data["schema_name"]
                .lower()
                .strip()
                .replace(" ", "_")
                .replace("-", "_")
            )

            # Keep domain clean for web: use hyphens, not underscores
            domain_slug = schema_name.replace("_", "-")

            # Automatically create ShuleHub domains
            primary_domain = f"{domain_slug}.shulehub.org"
            fallback_domain = f"{domain_slug}.schoollibrary-1.onrender.com"

            principal_email = form.cleaned_data["principal_email"]
            administrator_email = form.cleaned_data["administrator_email"]

            connection.set_schema_to_public()

            if School.objects.filter(schema_name=schema_name).exists():
                messages.error(request, f"Schema '{schema_name}' already exists.")
                return redirect(request.path)

            if Domain.objects.filter(domain=primary_domain).exists():
                messages.error(request, f"Domain '{primary_domain}' already exists.")
                return redirect(request.path)

            tenant = None

            try:
                connection.set_schema_to_public()

                tenant = School.objects.create(
                    schema_name=schema_name,
                    name=school_name,
                    on_trial=True,
                    is_active=True,
                    paid_until=timezone.now() + timezone.timedelta(days=30),
                )

                # Primary professional domain
                Domain.objects.create(
                    domain=primary_domain,
                    tenant=tenant,
                    is_primary=True,
                )

                # Backup Render/onrender domain
                Domain.objects.get_or_create(
                    domain=fallback_domain,
                    tenant=tenant,
                    defaults={"is_primary": False},
                )

                messages.info(
                    request,
                    f"Tenant '{school_name}' created. Running migrations..."
                )

                connection.set_schema_to_public()

                call_command(
                    "migrate_schemas",
                    schema_name=schema_name,
                    interactive=False,
                    verbosity=2,
                )

                # Confirm required tenant tables exist before creating users
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_schema = %s
                            AND table_name = 'digitallibrary_userprofile'
                        );
                        """,
                        [schema_name],
                    )
                    userprofile_exists = cursor.fetchone()[0]

                if not userprofile_exists:
                    raise Exception(
                        f"Tenant migrations failed. "
                        f"Table digitallibrary_userprofile was not created in schema '{schema_name}'. "
                        f"Run: python manage.py makemigrations digitallibrary "
                        f"then: python manage.py migrate_schemas"
                    )

                with schema_context(schema_name):
                    from digitallibrary.models import UserProfile, SchoolSetting

                    principal, _ = User.objects.get_or_create(
                        username="principal",
                        defaults={
                            "email": principal_email,
                            "first_name": "School",
                            "last_name": "Principal",
                        },
                    )
                    principal.set_password("principal@123")
                    principal.email = principal_email
                    principal.is_staff = True
                    principal.is_superuser = True
                    principal.is_active = True
                    principal.save()

                    profile, _ = UserProfile.objects.get_or_create(user=principal)
                    profile.role = "principal"
                    profile.is_approved = True
                    profile.save()

                    admin, _ = User.objects.get_or_create(
                        username="admin",
                        defaults={
                            "email": administrator_email,
                            "first_name": "School",
                            "last_name": "Admin",
                        },
                    )
                    admin.set_password("admin@123")
                    admin.email = administrator_email
                    admin.is_staff = True
                    admin.is_superuser = True
                    admin.is_active = True
                    admin.save()

                    admin_profile, _ = UserProfile.objects.get_or_create(user=admin)
                    admin_profile.role = "administrator"
                    admin_profile.is_approved = True
                    admin_profile.save()

                    school_setting_kwargs = {
                        "school_name": school_name,
                        "defaults": {
                            "name": school_name,
                            "motto": "Excellence in Education",
                            "primary_color": "#bb1919",
                            "secondary_color": "#0a0a0a",
                            "accent_color": "#ff5a5a",
                            "timezone": "Africa/Nairobi",
                            "currency": "KES",
                            "phone": "+254700000000",
                            "email": f"info@{primary_domain}",
                        },
                    }

                    SchoolSetting.objects.get_or_create(**school_setting_kwargs)

                connection.set_schema_to_public()

                messages.success(
                    request,
                    f"✅ Tenant '{school_name}' created successfully!\n\n"
                    f"🌐 Primary URL: https://{primary_domain}/app/\n"
                    f"🔁 Backup URL: https://{fallback_domain}/app/\n\n"
                    f"👑 PRINCIPAL: principal / principal@123\n"
                    f"⚙️ ADMIN: admin / admin@123"
                )

                return redirect("tenants:tenant_dashboard")

            except Exception as e:
                logger.error(f"Error creating tenant {school_name}: {str(e)}")
                messages.error(request, f"Error creating tenant: {str(e)}")

                connection.set_schema_to_public()

                if tenant:
                    schema_to_drop = tenant.schema_name

                    try:
                        Domain.objects.filter(tenant=tenant).delete()
                    except Exception:
                        pass

                    try:
                        School.objects.filter(id=tenant.id).delete()
                    except Exception:
                        pass

                    try:
                        with connection.cursor() as cursor:
                            cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_to_drop}" CASCADE;')
                    except Exception:
                        pass

                connection.set_schema_to_public()
                return redirect(request.path)

    else:
        form = TenantCreationForm()

    connection.set_schema_to_public()

    existing_tenants = School.objects.all().order_by("-created_on")[:10]

    return render(
        request,
        "tenants/create_tenant.html",
        {
            "form": form,
            "existing_tenants": existing_tenants,
            "total_tenants": School.objects.count(),
        },
    )

@login_required
@user_passes_test(is_superuser)
def tenant_dashboard(request):
    """
    Main tenant management dashboard showing all tenants
    """
    connection.set_schema_to_public()

    tenants = School.objects.all().order_by("-created_on")
    total_tenants = tenants.count()

    tenant_stats = []

    for tenant in tenants:
        primary_domain = tenant.domains.filter(is_primary=True).first()

        users_count = 0

        try:
            with schema_context(tenant.schema_name):
                users_count = User.objects.count()
        except Exception as e:
            print(f"⚠️ Could not count users for {tenant.schema_name}: {e}")
            users_count = 0

        tenant_stats.append({
            "tenant": tenant,
            "domain": primary_domain.domain if primary_domain else "No domain",
            "users_count": users_count,
        })

    context = {
        "tenants": tenant_stats,
        "total_tenants": total_tenants,
    }

    return render(request, "tenants/dashboard.html", context)


@login_required
@user_passes_test(is_superuser)
def tenant_detail(request, tenant_id):
    """
    View detailed information about a specific tenant
    """
    connection.set_schema_to_public()

    tenant = get_object_or_404(School, id=tenant_id)
    domains = tenant.domains.all()
    primary_domain = domains.filter(is_primary=True).first()

    context = {
        "tenant": tenant,
        "domains": domains,
        "primary_domain": primary_domain,
        "tenant_id": tenant_id,
    }

    return render(request, "tenants/tenant_detail.html", context)


@login_required
@user_passes_test(is_superuser)
def tenant_edit(request, tenant_id):
    """
    Edit tenant details
    """
    connection.set_schema_to_public()

    tenant = get_object_or_404(School, id=tenant_id)

    if request.method == "POST":
        form = TenantUpdateForm(request.POST, instance=tenant)

        if form.is_valid():
            form.save()
            messages.success(request, f"Tenant '{tenant.name}' updated successfully!")
            return redirect("tenants:tenant_detail", tenant_id=tenant.id)

    else:
        form = TenantUpdateForm(instance=tenant)

    context = {
        "form": form,
        "tenant": tenant,
    }

    return render(request, "tenants/tenant_edit.html", context)


@login_required
@user_passes_test(is_superuser)
def tenant_delete(request, tenant_id):
    """
    Delete a tenant
    """
    connection.set_schema_to_public()

    tenant = get_object_or_404(School, id=tenant_id)

    if request.method == "POST":
        tenant_name = tenant.name
        schema_name = tenant.schema_name

        tenant.delete()

        try:
            with connection.cursor() as cursor:
                cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
        except Exception as e:
            messages.warning(
                request,
                f"Tenant deleted but schema may need manual cleanup: {e}"
            )

        messages.success(
            request,
            f"Tenant '{tenant_name}' has been deleted successfully!"
        )

        return redirect("tenants:tenant_dashboard")

    context = {
        "tenant": tenant,
    }

    return render(request, "tenants/tenant_delete_confirm.html", context)


@login_required
@user_passes_test(is_superuser)
def reset_tenant_password(request, tenant_id):
    """
    Reset password for a user in a tenant
    """
    connection.set_schema_to_public()

    tenant = get_object_or_404(School, id=tenant_id)

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

                messages.success(
                    request,
                    f"Password for '{username}' in '{tenant.name}' has been reset!"
                )

                return redirect("tenants:tenant_detail", tenant_id=tenant.id)

            except User.DoesNotExist:
                messages.error(
                    request,
                    f"User '{username}' not found in '{tenant.name}'."
                )

    else:
        form = ResetPasswordForm()

    context = {
        "tenant": tenant,
        "form": form,
    }

    return render(request, "tenants/reset_password.html", context)


@login_required
@user_passes_test(is_superuser)
def add_domain(request, tenant_id):
    """
    Add a new domain to a tenant
    """
    connection.set_schema_to_public()

    tenant = get_object_or_404(School, id=tenant_id)

    if request.method == "POST":
        domain_name = request.POST.get("domain")
        is_primary = request.POST.get("is_primary") == "on"

        if domain_name:
            if Domain.objects.filter(domain=domain_name).exists():
                messages.error(request, f"Domain '{domain_name}' already exists!")
            else:
                Domain.objects.create(
                    domain=domain_name,
                    tenant=tenant,
                    is_primary=is_primary,
                )

                if is_primary:
                    tenant.domains.exclude(domain=domain_name).update(is_primary=False)

                messages.success(request, f"Domain '{domain_name}' added successfully!")

    return redirect("tenants:tenant_detail", tenant_id=tenant.id)


@login_required
@user_passes_test(is_superuser)
def remove_domain(request, domain_id):
    """
    Remove a domain from a tenant
    """
    connection.set_schema_to_public()

    domain = get_object_or_404(Domain, id=domain_id)
    tenant_id = domain.tenant.id

    if domain.is_primary:
        messages.error(request, "Cannot remove primary domain.")
    else:
        domain.delete()
        messages.success(request, f"Domain '{domain.domain}' removed successfully!")

    return redirect("tenants:tenant_detail", tenant_id=tenant_id)


@login_required
@user_passes_test(is_superuser)
def set_primary_domain(request, domain_id):
    """
    Set a domain as primary for its tenant
    """
    connection.set_schema_to_public()

    domain = get_object_or_404(Domain, id=domain_id)
    tenant = domain.tenant

    tenant.domains.update(is_primary=False)
    domain.is_primary = True
    domain.save()

    messages.success(request, f"'{domain.domain}' is now the primary domain.")

    return redirect("tenants:tenant_detail", tenant_id=tenant.id)


@login_required
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

    # ------------------------------------------------------------
    # 1. Tenant statistics
    # ------------------------------------------------------------
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
            primary_domain = school.domains.filter(is_primary=True).first()

            user_count = 0

            try:
                with schema_context(school.schema_name):
                    user_count = User.objects.count()
            except Exception as e:
                print(f"⚠️ Could not count users for {school.schema_name}: {e}")
                user_count = 0

            tenant_data.append({
                "school": school,
                "primary_domain": primary_domain.domain if primary_domain else "No domain",
                "user_count": user_count,
            })

    # ------------------------------------------------------------
    # 2. Backup statistics - Django 5.2 safe
    # ------------------------------------------------------------
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

        database_backup_dir.mkdir(parents=True, exist_ok=True)
        media_backup_dir.mkdir(parents=True, exist_ok=True)

        database_backups = []
        media_backups = []

        for pattern in ["*.json", "*.dump", "*.sql", "*.sqlite3", "*.backup"]:
            database_backups.extend(database_backup_dir.glob(pattern))

        for pattern in ["*.tar.gz", "*.zip", "*.tar", "*.gz"]:
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

        backup_stats["database_backups"] = [f.name for f in database_backups[:5]]
        backup_stats["media_backups"] = [f.name for f in media_backups[:5]]
        backup_stats["total_backups"] = len(database_backups) + len(media_backups)

        if database_backups:
            backup_stats["last_backup"] = database_backups[0].name
        elif media_backups:
            backup_stats["last_backup"] = media_backups[0].name

    except Exception as e:
        print(f"⚠️ Backup stats error: {e}")
        backup_stats["error"] = str(e)

    # ------------------------------------------------------------
    # 3. System statistics
    # ------------------------------------------------------------
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
            system_stats["database_size"] = f"{db_size / (1024 ** 3):.2f} GB"
    except Exception as e:
        print(f"⚠️ Could not get database size: {e}")
        system_stats["database_size"] = "N/A"

    # ------------------------------------------------------------
    # 4. Context
    # ------------------------------------------------------------
    context = {
        # Tenant data
        "schools": tenant_data,
        "total_schools": total_schools,
        "active_schools": active_schools,
        "inactive_schools": inactive_schools,
        "trial_schools": trial_schools,
        "paid_schools": paid_schools,
        "expired_schools": expired_schools,
        "total_domains": total_domains,

        # Backup data
        "backup_stats": backup_stats,

        # System data
        "system_stats": system_stats,

        # Current time
        "current_time": timezone.now(),
    }

    return render(request, "tenants/super_admin/unified_dashboard.html", context)
