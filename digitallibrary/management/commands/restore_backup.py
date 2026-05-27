from django.core.management.base import BaseCommand
from django.core.management import call_command
import os
from django.conf import settings

class Command(BaseCommand):
    help = 'Restore database and media from backup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-file',
            type=str,
            help='Specific backup file to restore (leave empty for latest)',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List available backups',
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_backups()
            return
        
        self.stdout.write('⚠️  WARNING: This will overwrite your current data!')
        confirm = input('Type "YES" to continue: ')
        
        if confirm != 'YES':
            self.stdout.write('Restore cancelled.')
            return
        
        try:
            # Restore database
            self.stdout.write('Restoring database...')
            if options['backup_file']:
                call_command('dbrestore', backup_name=options['backup_file'])
            else:
                call_command('dbrestore')
            
            # Restore media files
            self.stdout.write('Restoring media files...')
            if options['backup_file']:
                call_command('mediarestore', backup_name=options['backup_file'])
            else:
                call_command('mediarestore')
            
            self.stdout.write(self.style.SUCCESS('✓ Restore completed successfully!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Restore failed: {str(e)}'))

    def list_backups(self):
        """List available backups"""
        backup_dir = settings.BASE_DIR / 'backups/database'
        media_dir = settings.BASE_DIR / 'backups/media'
        
        self.stdout.write('\n📁 Database Backups:')
        if backup_dir.exists():
            for f in sorted(backup_dir.glob('*.dump'), reverse=True):
                size = f.stat().st_size / 1024 / 1024
                self.stdout.write(f'  • {f.name} ({size:.1f} MB)')
        else:
            self.stdout.write('  No database backups found')
        
        self.stdout.write('\n📁 Media Backups:')
        if media_dir.exists():
            for f in sorted(media_dir.glob('*.tar.gz'), reverse=True):
                size = f.stat().st_size / 1024 / 1024
                self.stdout.write(f'  • {f.name} ({size:.1f} MB)')
        else:
            self.stdout.write('  No media backups found')