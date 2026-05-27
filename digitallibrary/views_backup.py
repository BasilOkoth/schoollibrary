# digitallibrary/views_backup.py

from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse, HttpResponse, HttpResponseNotFound, HttpResponseBadRequest, HttpResponseServerError
from django.core.management import call_command
from django.conf import settings
from django.utils import timezone
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
import os
import json
import io
from pathlib import Path
import tarfile
import glob
import urllib.parse

def format_size(size_bytes):
    """Format file size for display"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


@staff_member_required
def backup_management(request):
    """Main backup management view - Dashboard"""
    backup_dir = settings.DATABASE_BACKUP_DIR
    media_dir = settings.MEDIA_BACKUP_DIR
    
    database_backups = []
    media_backups = []
    all_backups = []
    total_size = 0
    
    # List database backups (JSON, SQL, DUMP files)
    if backup_dir.exists():
        backup_patterns = ['*.json', '*.sql', '*.dump', '*.psql']
        db_files = []
        for pattern in backup_patterns:
            db_files.extend(backup_dir.glob(pattern))
        
        db_files = list(set(db_files))
        db_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        for f in db_files[:20]:
            size = f.stat().st_size
            total_size += size
            backup_info = {
                'name': f.name,
                'path': str(f),
                'size': format_size(size),
                'size_bytes': size,
                'date': timezone.datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'database',
                'extension': f.suffix
            }
            database_backups.append(backup_info)
            all_backups.append(backup_info)
    
    # List media backups
    if media_dir.exists():
        media_files = list(media_dir.glob('*.tar.gz'))
        media_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        for f in media_files[:20]:
            size = f.stat().st_size
            total_size += size
            backup_info = {
                'name': f.name,
                'path': str(f),
                'size': format_size(size),
                'size_bytes': size,
                'date': timezone.datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'media',
                'extension': '.tar.gz'
            }
            media_backups.append(backup_info)
            all_backups.append(backup_info)
    
    # Sort all backups by date (newest first)
    all_backups.sort(key=lambda x: x['date'], reverse=True)
    
    last_backup = all_backups[0]['date'] if all_backups else None
    
    # Get database size
    db_size = "N/A"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_database_size(current_database())")
            db_size_bytes = cursor.fetchone()[0]
            db_size = format_size(db_size_bytes)
    except:
        pass
    
    # Load saved schedule settings
    saved_frequency = 'daily'
    saved_retention = '30'
    config_file = settings.BASE_DIR / 'config' / 'backup_schedule.json'
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                schedule = json.load(f)
                saved_frequency = schedule.get('frequency', 'daily')
                saved_retention = str(schedule.get('retention_days', 30))
        except:
            pass
    
    context = {
        'backups': all_backups,
        'database_backups': database_backups,
        'media_backups': media_backups,
        'backup_count': len(all_backups),
        'total_size': format_size(total_size),
        'last_backup_date': last_backup,
        'total_backups': len(all_backups),
        'db_size': db_size,
        'saved_frequency': saved_frequency,
        'saved_retention': saved_retention,
    }
    return render(request, 'digitallibrary/backup_management.html', context)


@staff_member_required
def schedule_settings(request):
    """Get current schedule settings"""
    config_file = settings.BASE_DIR / 'config' / 'backup_schedule.json'
    settings_data = {
        'frequency': 'daily',
        'retention': '30',
        'time': '02:00'
    }
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                data = json.load(f)
                settings_data['frequency'] = data.get('frequency', 'daily')
                settings_data['retention'] = str(data.get('retention_days', 30))
                settings_data['time'] = data.get('time', '02:00')
        except:
            pass
    
    return JsonResponse(settings_data)


@staff_member_required
def create_backup(request):
    """Create a new backup"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    try:
        backup_type = request.POST.get('backup_type', 'database')
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        created_backups = []
        
        if backup_type in ['database', 'both']:
            # Create database backup using Django's dumpdata
            backup_filename = f"backup_{timestamp}.json"
            backup_path = settings.DATABASE_BACKUP_DIR / backup_filename
            
            from io import StringIO
            from django.core.management import call_command
            
            out = StringIO()
            call_command('dumpdata', exclude=['contenttypes', 'auth.permission'], stdout=out, natural_foreign=True, natural_primary=True)
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(out.getvalue())
            
            created_backups.append(f"Database backup: {backup_filename}")
        
        if backup_type in ['media', 'both']:
            # Create media backup
            media_backup_filename = f"media_backup_{timestamp}.tar.gz"
            media_backup_path = settings.MEDIA_BACKUP_DIR / media_backup_filename
            
            media_root = getattr(settings, 'MEDIA_ROOT', None)
            if not media_root or not os.path.exists(media_root):
                media_root = settings.BASE_DIR / 'media'
            
            if os.path.exists(media_root) and os.listdir(media_root):
                with tarfile.open(media_backup_path, 'w:gz') as tar:
                    tar.add(media_root, arcname='media')
                created_backups.append(f"Media backup: {media_backup_filename}")
            else:
                return JsonResponse({'success': False, 'error': 'No media files found to backup'}, status=400)
        
        return JsonResponse({
            'success': True, 
            'message': 'Backup created successfully!',
            'backups': created_backups
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return JsonResponse({'success': False, 'error': str(e), 'details': error_details}, status=500)


@staff_member_required
def download_backup(request):
    """Download a backup file"""
    import urllib.parse
    import re
    
    # Get parameters
    backup_path = request.GET.get('path', '')
    filename = request.GET.get('filename', '')
    backup_type = request.GET.get('type', 'database')
    
    # If we have a path parameter, clean it up
    if backup_path:
        # Decode URL encoding
        backup_path = urllib.parse.unquote(backup_path)
        
        # Fix Windows path - replace \x08 (backspace) with actual backslash
        backup_path = backup_path.replace('\x08', '\\')
        backup_path = backup_path.replace('%08', '\\')
        backup_path = backup_path.replace('%5C', '\\')
        backup_path = backup_path.replace('%3A', ':')
        
        # Also fix any double backslashes
        backup_path = backup_path.replace('\\\\', '\\')
        
        # Extract just the filename from the path
        filename = os.path.basename(backup_path)
    
    if not filename:
        return HttpResponseBadRequest("No filename specified")
    
    # Clean the filename (remove any path separators)
    filename = os.path.basename(filename)
    
    # Determine which directory to look in
    if backup_type == 'database' or filename.endswith('.json') or filename.endswith('.sql') or filename.endswith('.dump'):
        backup_dir = settings.DATABASE_BACKUP_DIR
    elif backup_type == 'media' or filename.endswith('.tar.gz'):
        backup_dir = settings.MEDIA_BACKUP_DIR
    else:
        return HttpResponseBadRequest("Invalid backup type")
    
    # Construct the full path
    file_path = backup_dir / filename
    
    # Log for debugging
    print(f"Looking for file: {file_path}")
    print(f"Backup directory: {backup_dir}")
    print(f"Files in directory: {list(backup_dir.glob('*'))}")
    
    # Check if file exists
    if not file_path.exists():
        # Try to find the file in the backup directory (case insensitive)
        found = False
        for f in backup_dir.glob("*"):
            if f.name.lower() == filename.lower():
                file_path = f
                found = True
                break
        
        if not found:
            return HttpResponseNotFound(f"File not found: {filename}")
    
    try:
        # Set content type based on file extension
        if filename.endswith('.json'):
            content_type = 'application/json'
        elif filename.endswith('.sql'):
            content_type = 'application/sql'
        elif filename.endswith('.tar.gz'):
            content_type = 'application/gzip'
        else:
            content_type = 'application/octet-stream'
        
        # Open and serve the file
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=content_type,
            as_attachment=True,
            filename=filename
        )
        response['Content-Length'] = file_path.stat().st_size
        return response
        
    except Exception as e:
        return HttpResponseServerError(f"Download failed: {str(e)}")
@staff_member_required
def download_backup_by_name(request, backup_type, filename):
    """Download a backup file directly by name - cleaner URL"""
    import urllib.parse
    
    # Decode filename
    filename = urllib.parse.unquote(filename)
    
    # Clean the filename
    filename = os.path.basename(filename)
    
    # Determine which directory to look in
    if backup_type == 'database':
        backup_dir = settings.DATABASE_BACKUP_DIR
    elif backup_type == 'media':
        backup_dir = settings.MEDIA_BACKUP_DIR
    else:
        return HttpResponseBadRequest("Invalid backup type")
    
    # Construct the full path
    file_path = backup_dir / filename
    
    # Also try to find the file by pattern (in case of partial match)
    if not file_path.exists():
        found = False
        for f in backup_dir.glob("*"):
            if f.name == filename or filename in f.name:
                file_path = f
                found = True
                break
        
        if not found:
            return HttpResponseNotFound(f"File not found: {filename}")
    
    try:
        # Set content type based on file extension
        if filename.endswith('.json'):
            content_type = 'application/json'
        elif filename.endswith('.sql'):
            content_type = 'application/sql'
        elif filename.endswith('.tar.gz'):
            content_type = 'application/gzip'
        else:
            content_type = 'application/octet-stream'
        
        # Open and serve the file
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=content_type,
            as_attachment=True,
            filename=file_path.name
        )
        response['Content-Length'] = file_path.stat().st_size
        return response
        
    except Exception as e:
        return HttpResponseServerError(f"Download failed: {str(e)}")

@staff_member_required
def delete_backup(request):
    """Delete a backup file"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        backup_path = data.get('backup_path', '')
        filename = data.get('filename', '')
        
        # Determine file path
        if backup_path and os.path.exists(backup_path):
            file_path = backup_path
        elif filename:
            # Try to find in backup directories
            file_path = settings.DATABASE_BACKUP_DIR / filename
            if not file_path.exists():
                file_path = settings.MEDIA_BACKUP_DIR / filename
        else:
            return JsonResponse({'success': False, 'error': 'No backup specified'})
        
        if not os.path.exists(file_path):
            return JsonResponse({'success': False, 'error': 'File not found'})
        
        # Delete the file
        os.remove(file_path)
        return JsonResponse({'success': True, 'message': 'Backup deleted successfully!'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@staff_member_required
def restore_backup(request):
    """Restore from a backup file"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        backup_path = data.get('backup_path', '')
        filename = data.get('filename', '')
        backup_type = data.get('backup_type', 'database')
        
        # Determine file path
        if backup_path and os.path.exists(backup_path):
            file_path = backup_path
        elif filename:
            # Try to find in backup directories
            file_path = settings.DATABASE_BACKUP_DIR / filename
            if not file_path.exists():
                file_path = settings.MEDIA_BACKUP_DIR / filename
        
        if not file_path or not os.path.exists(file_path):
            return JsonResponse({'success': False, 'error': 'Backup file not found'})
        
        # Determine backup type from file if not specified
        if not backup_type or backup_type == 'database':
            if str(file_path).endswith('.tar.gz'):
                backup_type = 'media'
            else:
                backup_type = 'database'
        
        if backup_type == 'database':
            # Restore database using loaddata
            call_command('loaddata', str(file_path))
            return JsonResponse({'success': True, 'message': 'Database restored successfully! The page will now reload.'})
        
        elif backup_type == 'media':
            # Restore media files
            media_root = getattr(settings, 'MEDIA_ROOT', None)
            if not media_root:
                media_root = settings.BASE_DIR / 'media'
            
            with tarfile.open(file_path, 'r:gz') as tar:
                tar.extractall(path=settings.BASE_DIR)
            
            return JsonResponse({'success': True, 'message': 'Media restored successfully! The page will now reload.'})
        
        else:
            return JsonResponse({'success': False, 'error': 'Unknown backup type'})
            
    except Exception as e:
        import traceback
        return JsonResponse({'success': False, 'error': str(e), 'traceback': traceback.format_exc()})


@staff_member_required
def save_schedule(request):
    """Save backup schedule settings"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        frequency = data.get('frequency', 'daily')
        retention = data.get('retention', 30)
        backup_time = data.get('time', '02:00')
        
        config_dir = settings.BASE_DIR / 'config'
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = config_dir / 'backup_schedule.json'
        
        schedule_config = {
            'frequency': frequency,
            'retention_days': int(retention),
            'time': backup_time,
            'last_updated': timezone.now().isoformat(),
            'updated_by': request.user.username if request.user.is_authenticated else 'system'
        }
        
        with open(config_file, 'w') as f:
            json.dump(schedule_config, f, indent=2)
        
        return JsonResponse({
            'success': True, 
            'message': f'Schedule saved! Backups will run {frequency} at {backup_time}'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
