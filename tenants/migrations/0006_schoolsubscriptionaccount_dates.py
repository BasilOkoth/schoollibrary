# Generated manually for ShuleHub subscription start/end dates

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0005_schoolsubscriptionpayment"),
    ]

    operations = [
        migrations.AddField(
            model_name="schoolsubscriptionaccount",
            name="subscription_start_date",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Date when this ShuleHub subscription starts.",
            ),
        ),
        migrations.AddField(
            model_name="schoolsubscriptionaccount",
            name="subscription_end_date",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Date when this ShuleHub subscription ends or expires.",
            ),
        ),
    ]
