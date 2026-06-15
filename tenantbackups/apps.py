from django.apps import AppConfig


class TenantBackupsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tenantbackups"
    verbose_name = "Tenant Backups"
