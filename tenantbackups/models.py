import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from tenants.models import School


class TenantBackup(models.Model):
    """
    Stores one isolated backup for one school tenant.

    This model must exist in the public/shared schema so the
    super administrator can manage backups for all schools.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("restoring", "Restoring"),
        ("restored", "Restored"),
    ]

    BACKUP_TYPE_CHOICES = [
        ("manual", "Manual"),
        ("scheduled", "Scheduled"),
        (
            "pre_restore",
            "Pre-restore Safety Backup",
        ),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name="tenant_backups",
    )

    tenant_schema = models.CharField(
        max_length=63,
        db_index=True,
        editable=False,
    )

    tenant_name = models.CharField(
        max_length=200,
        editable=False,
    )

    backup_type = models.CharField(
        max_length=20,
        choices=BACKUP_TYPE_CHOICES,
        default="manual",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )

    backup_file = models.FileField(
        upload_to="tenant_backups/%Y/%m/%d/",
        max_length=500,
        blank=True,
        null=True,
    )

    filename = models.CharField(
        max_length=255,
        blank=True,
    )

    file_size = models.PositiveBigIntegerField(
        default=0,
        help_text="Backup file size in bytes.",
    )

    checksum = models.CharField(
        max_length=64,
        blank=True,
        help_text=(
            "SHA-256 checksum used to verify "
            "backup integrity."
        ),
    )

    database_format = models.CharField(
        max_length=20,
        default="postgres_custom",
        help_text=(
            "For example: postgres_custom or json."
        ),
    )

    includes_media = models.BooleanField(
        default=False,
    )

    is_verified = models.BooleanField(
        default=False,
    )

    verification_message = models.TextField(
        blank=True,
    )

    error_message = models.TextField(
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tenant_backups",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    restored_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    restored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restored_tenant_backups",
    )

    notes = models.TextField(
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=[
                    "tenant_schema",
                    "-created_at",
                ]
            ),
            models.Index(
                fields=[
                    "school",
                    "-created_at",
                ]
            ),
            models.Index(
                fields=["status"]
            ),
            models.Index(
                fields=["backup_type"]
            ),
        ]

        verbose_name = "Tenant Backup"
        verbose_name_plural = "Tenant Backups"

    def __str__(self):
        return (
            f"{self.tenant_name} "
            f"({self.tenant_schema}) - "
            f"{self.created_at:%Y-%m-%d %H:%M}"
        )

    def clean(self):
        super().clean()

        if not self.school_id:
            raise ValidationError(
                "A school tenant must be selected."
            )

        school_schema = getattr(
            self.school,
            "schema_name",
            "",
        )

        if school_schema == "public":
            raise ValidationError(
                (
                    "The public schema cannot be backed "
                    "up using TenantBackup."
                )
            )

        if (
            self.tenant_schema
            and self.tenant_schema != school_schema
        ):
            raise ValidationError(
                (
                    "The stored tenant schema does not "
                    "match the selected school."
                )
            )

    def save(self, *args, **kwargs):
        if self.school_id:
            self.tenant_schema = (
                self.school.schema_name
            )
            self.tenant_name = self.school.name

        if self.backup_file:
            self.filename = Path(
                self.backup_file.name
            ).name

            try:
                self.file_size = (
                    self.backup_file.size
                )
            except (
                OSError,
                ValueError,
                AttributeError,
            ):
                pass

        self.full_clean()

        super().save(
            *args,
            **kwargs,
        )

    @property
    def size_display(self):
        size = self.file_size or 0

        if size < 1024:
            return f"{size} B"

        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"

        if size < 1024 * 1024 * 1024:
            return (
                f"{size / (1024 * 1024):.1f} MB"
            )

        return (
            f"{size / (1024 * 1024 * 1024):.1f} GB"
        )

    @property
    def can_restore(self):
        """
        A backup may only be restored when it has been
        completed, verified, and has a stored file.
        """
        return (
            self.status == "completed"
            and self.is_verified
            and bool(self.backup_file)
            and self.tenant_schema != "public"
        )


class TenantRestoreLog(models.Model):
    """
    Records one restore operation for one tenant backup.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    backup = models.ForeignKey(
        TenantBackup,
        on_delete=models.PROTECT,
        related_name="restore_logs",
    )

    school = models.ForeignKey(
        School,
        on_delete=models.PROTECT,
        related_name="tenant_restore_logs",
    )

    tenant_schema = models.CharField(
        max_length=63,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_restore_actions",
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    error_message = models.TextField(
        blank=True,
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-started_at"]

        indexes = [
            models.Index(
                fields=[
                    "tenant_schema",
                    "-started_at",
                ]
            ),
            models.Index(
                fields=["status"]
            ),
        ]

        verbose_name = "Tenant Restore Log"
        verbose_name_plural = (
            "Tenant Restore Logs"
        )

    def __str__(self):
        return (
            f"Restore {self.tenant_schema} from "
            f"{self.backup.filename}"
        )

    def clean(self):
        super().clean()

        if self.tenant_schema == "public":
            raise ValidationError(
                (
                    "The public schema cannot be "
                    "restored here."
                )
            )

        if self.school_id:
            school_schema = getattr(
                self.school,
                "schema_name",
                "",
            )

            if school_schema != self.tenant_schema:
                raise ValidationError(
                    (
                        "The selected school does not "
                        "match the restore schema."
                    )
                )

        if self.backup_id:
            backup_schema = getattr(
                self.backup,
                "tenant_schema",
                "",
            )

            if backup_schema != self.tenant_schema:
                raise ValidationError(
                    (
                        "The backup belongs to a "
                        "different tenant."
                    )
                )

            if (
                self.school_id
                and self.backup.school_id
                != self.school_id
            ):
                raise ValidationError(
                    (
                        "The backup belongs to a "
                        "different school."
                    )
                )

    def save(self, *args, **kwargs):
        if self.backup_id:
            if not self.school_id:
                self.school = self.backup.school

            if not self.tenant_schema:
                self.tenant_schema = (
                    self.backup.tenant_schema
                )

        self.full_clean()

        super().save(
            *args,
            **kwargs,
        )
