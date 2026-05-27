# tenants/signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.management import call_command
from .models import School

logger = logging.getLogger(__name__)


@receiver(post_save, sender=School)
def tenant_after_migration(sender, instance, created, **kwargs):
    """Run post-migration setup after tenant schema is migrated"""
    if created and instance.schema_name != 'public':
        try:
            from django_tenants.utils import schema_context
            from django.db import connection
            from django.contrib.auth.models import User
            
            # Wait for migrations to complete by checking if tables exist
            with schema_context(instance.schema_name):
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'digitallibrary_tvdisplay'
                        )
                    """)
                    table_exists = cursor.fetchone()[0]
                
                if table_exists:
                    # Now safe to create TV display
                    from digitallibrary.models import TVDisplay
                    tv, created = TVDisplay.objects.get_or_create(
                        school=instance,
                        defaults={
                            'name': f"{instance.name} TV",
                            'accent_color': '#3b82f6',
                            'is_active': True
                        }
                    )
                    if created:
                        logger.info(f"✅ TV display created for {instance.name} after migration")
                    
        except Exception as e:
            logger.warning(f"Post-migration setup for {instance.name}: {e}")