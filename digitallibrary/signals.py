# digitallibrary/signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import ProgrammingError
from .models import Resource, TVDisplay
from .ai_engine import trigger_rebuild_async
from tenants.models import School

logger = logging.getLogger(__name__)


def table_exists(cursor, table_name):
    """Check if a table exists in the current schema"""
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = %s
        )
    """, [table_name])
    return cursor.fetchone()[0]


@receiver(post_save, sender=Resource)
def resource_saved(sender, instance: Resource, created, **kwargs):
    """Trigger AI rebuild when PDF is uploaded"""
    # only PDFs with a file
    if instance.resource_type == "PDF" and instance.file:
        logger.info(f"📄 PDF uploaded: {instance.title} - Triggering AI rebuild")
        print(f"📄 PDF uploaded: {instance.title} - Triggering AI rebuild")
        trigger_rebuild_async()
    else:
        logger.info(f"⏭️ Not a PDF: {instance.resource_type}")


@receiver(post_save, sender=School)
def create_school_tv(sender, instance, created, **kwargs):
    """Automatically create TV display when a new school is created"""
    # Skip for public schema
    if instance.schema_name == 'public':
        return
    
    try:
        from django_tenants.utils import schema_context
        from django.db import connection
        
        # For new tenants, the tables might not exist yet
        if created:
            # Don't try to create TV display immediately for new tenants
            # because migrations might not have run yet
            logger.info(f"🏫 New school created: {instance.name} - TV display will be created after migrations")
            print(f"🏫 New school created: {instance.name} - TV display will be created after migrations")
            return
        
        # For existing schools, try to create/update TV display
        with schema_context(instance.schema_name):
            # Check if TVDisplay table exists
            with connection.cursor() as cursor:
                tv_table_exists = table_exists(cursor, 'digitallibrary_tvdisplay')
            
            if not tv_table_exists:
                logger.info(f"TVDisplay table not yet migrated for {instance.schema_name}, skipping")
                return
            
            # Now safe to access TVDisplay model
            tv, tv_created = TVDisplay.objects.get_or_create(
                school=instance,
                defaults={
                    'name': f"{instance.name} TV",
                    'accent_color': '#3b82f6',
                    'is_active': True
                }
            )
            
            if tv_created:
                logger.info(f"✅ TV display created for {instance.name}")
                print(f"✅ TV display created for {instance.name}")
            else:
                # Update name if it's the default
                if tv.name in ["School TV", f"School TV"]:
                    tv.name = f"{instance.name} TV"
                    tv.save(update_fields=['name'])
                    logger.info(f"📺 TV display name updated for {instance.name}")
                    
    except ProgrammingError as e:
        # Table doesn't exist yet - this is normal for new tenants
        logger.warning(f"TVDisplay table not ready for {instance.name}: {e}")
    except Exception as e:
        logger.error(f"Error creating TV display for {instance.name}: {e}")


@receiver(post_save, sender=TVDisplay)
def tv_display_saved(sender, instance, created, **kwargs):
    """Log when TV display settings are updated"""
    if created:
        logger.info(f"🎬 New TV display created: {instance.name}")
        print(f"🎬 New TV display created: {instance.name}")
    else:
        logger.info(f"📺 TV display updated: {instance.name}")