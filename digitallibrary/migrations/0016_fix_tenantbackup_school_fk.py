from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0001_initial"),
        ("digitallibrary", "0015_create_missing_tenantbackup_tables"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tenantbackup",
            name="school",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tenant_backups",
                to="tenants.school",
            ),
        ),
        migrations.AlterField(
            model_name="tenantrestorelog",
            name="school",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tenant_restore_logs",
                to="tenants.school",
            ),
        ),
    ]
