from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('digitallibrary', '0010_alter_feedback_options'),
    ]

    operations = [
        # This migration just marks that the Feedback table already exists
        migrations.RunSQL(
            sql="SELECT 1 FROM digitallibrary_feedback LIMIT 1;",
            reverse_sql="SELECT 1;",
        ),
    ]