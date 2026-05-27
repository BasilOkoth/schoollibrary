from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Perform full backup (database + media)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--encrypt',
            action='store_true',
            help='Encrypt the backup with GPG',
        )

    def handle(self, *args, **options):
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        self.stdout.write(f'Starting backup at {timestamp}')
        
        try:
            # Backup database
            self.stdout.write('Backing up database...')
            call_command('dbbackup', verbosity=2)
            
            # Backup media files
            self.stdout.write('Backing up media files...')
            call_command('mediabackup', verbosity=2)
            
            self.stdout.write(self.style.SUCCESS(
                f'✓ Backup completed successfully at {timestamp}'
            ))
            
        except Exception as e:
            logger.error(f'Backup failed: {str(e)}')
            self.stdout.write(self.style.ERROR(
                f'✗ Backup failed: {str(e)}'
            ))