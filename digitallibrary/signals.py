import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Resource
from .ai_engine import trigger_rebuild_async

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Resource)
def resource_saved(sender, instance: Resource, created, **kwargs):
    # only PDFs with a file
    if instance.resource_type == "PDF" and instance.file:
        logger.info(f"📄 PDF uploaded: {instance.title} - Triggering AI rebuild")
        print(f"📄 PDF uploaded: {instance.title} - Triggering AI rebuild")  # This will show in console
        trigger_rebuild_async()
    else:
        logger.info(f"⏭️ Not a PDF: {instance.resource_type}")