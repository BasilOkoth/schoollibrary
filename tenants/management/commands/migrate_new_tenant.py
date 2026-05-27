from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth.models import User
from django_tenants.utils import schema_context
from django.utils import timezone

from tenants.models import School, Domain


class Command(BaseCommand):
    help = "Create tenant, run migrations, and create admin/principal users"

    def add_arguments(self, parser):
        parser.add_argument("--schema", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--domain", required=True)
        parser.add_argument("--principal-email", default="principal@school.com")
        parser.add_argument("--admin-email", default="admin@school.com")

    def handle(self, *args, **options):
        schema_name = options["schema"].lower().replace(" ", "_")
        school_name = options["name"]
        domain_name = options["domain"].lower()
        principal_email = options["principal_email"]
        admin_email = options["admin_email"]

        if School.objects.filter(schema_name=schema_name).exists():
            self.stderr.write(self.style.ERROR(f"Schema {schema_name} already exists"))
            return

        if Domain.objects.filter(domain=domain_name).exists():
            self.stderr.write(self.style.ERROR(f"Domain {domain_name} already exists"))
            return

        self.stdout.write("Creating tenant...")

        tenant = School.objects.create(
            schema_name=schema_name,
            name=school_name,
            on_trial=True,
            is_active=True,
            paid_until=timezone.now() + timezone.timedelta(days=30),
        )

        Domain.objects.create(
            domain=domain_name,
            tenant=tenant,
            is_primary=True,
        )

        self.stdout.write("Running tenant migrations...")

        call_command(
            "migrate_schemas",
            schema_name=schema_name,
            interactive=False,
            verbosity=1,
        )

        self.stdout.write("Creating tenant users...")

        with schema_context(schema_name):
            from digitallibrary.models import UserProfile, SchoolSetting

            principal, _ = User.objects.get_or_create(
                username="principal",
                defaults={
                    "email": principal_email,
                    "first_name": "School",
                    "last_name": "Principal",
                    "is_staff": True,
                    "is_superuser": True,
                    "is_active": True,
                },
            )
            principal.set_password("principal@123")
            principal.is_staff = True
            principal.is_superuser = True
            principal.is_active = True
            principal.save()

            UserProfile.objects.get_or_create(
                user=principal,
                defaults={
                    "role": "principal",
                    "is_approved": True,
                },
            )

            admin, _ = User.objects.get_or_create(
                username="admin",
                defaults={
                    "email": admin_email,
                    "first_name": "School",
                    "last_name": "Admin",
                    "is_staff": True,
                    "is_superuser": True,
                    "is_active": True,
                },
            )
            admin.set_password("admin@123")
            admin.is_staff = True
            admin.is_superuser = True
            admin.is_active = True
            admin.save()

            UserProfile.objects.get_or_create(
                user=admin,
                defaults={
                    "role": "administrator",
                    "is_approved": True,
                },
            )

            SchoolSetting.objects.get_or_create(
                school_name=school_name,
                defaults={
                    "motto": "Excellence in Education",
                    "primary_color": "#bb1919",
                    "secondary_color": "#0a0a0a",
                    "accent_color": "#ff5a5a",
                    "timezone": "Africa/Nairobi",
                    "currency": "KES",
                    "phone": "+254700000000",
                    "email": f"info@{schema_name}.shulehub.org",
                },
            )

        self.stdout.write(self.style.SUCCESS("Tenant fully created successfully"))
        self.stdout.write(f"URL: http://{domain_name}/app/")
        self.stdout.write("Principal: principal / principal@123")
        self.stdout.write("Admin: admin / admin@123")