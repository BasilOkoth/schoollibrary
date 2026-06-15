from django.urls import path

from . import views


app_name = "backups"


urlpatterns = [
    path(
        "",
        views.backup_dashboard,
        name="dashboard",
    ),
    path(
        "all/create/",
        views.backup_all_tenants,
        name="backup_all_tenants",
    ),
    path(
        "school/<str:school_id>/create/",
        views.backup_single_tenant,
        name="backup_single_tenant",
    ),
    path(
        "<uuid:backup_id>/restore/",
        views.restore_tenant_backup,
        name="restore_tenant_backup",
    ),
]
