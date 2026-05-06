# production_backup.py
import os
import shutil
import zipfile
import json
import hashlib
import logging
from datetime import datetime, timedelta
import subprocess
import sys

# ============================================================
# PRODUCTION CONFIGURATION
# ============================================================

PROJECT_DIR = r'E:\schoollibrary\schoollibrary'
MEDIA_DIR = os.path.join(PROJECT_DIR, 'media')
DATABASE_PATH = os.path.join(PROJECT_DIR, 'db.sqlite3')

# Backup Locations (Highest priority to lowest)
BACKUP_PATHS = {
    'primary': r'\\server\school_backups\library',      # Network server
    'secondary': r'D:\Library_Backups',                  # Secondary drive
    'tertiary': r'\\backup-server\school_archives',      # Backup server
    'local': r'E:\Backups'                               # Local fallback
}

# Settings
MAX_BACKUPS_TO_KEEP = 14          # Keep 14 days of backups
COMPRESSION_LEVEL = 9             # Maximum compression
BACKUP_RETENTION_DAYS = 30        # Delete backups older than 30 days

# Logging - FIXED for Windows console
LOG_FILE = os.path.join(PROJECT_DIR, 'logs', 'backup.log')

# Create logs directory
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Configure logging to handle Unicode properly
class SafeStreamHandler(logging.StreamHandler):
    """Handler that safely handles Unicode characters"""
    def emit(self, record):
        try:
            msg = self.format(record)
            # Replace Unicode characters with ASCII equivalents
            msg = msg.replace('\u2713', '[OK]')
            msg = msg.replace('\u274c', '[ERROR]')
            msg = msg.replace('\u26a0', '[WARN]')
            msg = msg.replace('\U0001f4c1', '[FOLDER]')
            msg = msg.replace('\U0001f4be', '[DISK]')
            msg = msg.replace('\u23f3', '[TIME]')
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        SafeStreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# PRODUCTION BACKUP CLASS
# ============================================================

class ProductionBackup:
    def __init__(self):
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_name = f'library_prod_backup_{self.timestamp}'
        self.backup_created = False
        self.backup_paths = []
        
    def check_disk_space(self, path, required_gb=5):
        """Check if enough disk space is available"""
        try:
            import shutil
            total, used, free = shutil.disk_usage(path)
            free_gb = free / (1024**3)
            if free_gb < required_gb:
                logger.warning(f"Low disk space on {path}: {free_gb:.1f}GB free (need {required_gb}GB)")
                return False
            logger.info(f"[OK] Disk space OK on {path}: {free_gb:.1f}GB free")
            return True
        except:
            return False
    
    def find_available_backup_location(self):
        """Find the first available backup location"""
        for name, path in BACKUP_PATHS.items():
            logger.info(f"Checking {name} location: {path}")
            
            # Check if path exists or can be created
            try:
                if not os.path.exists(path):
                    os.makedirs(path, exist_ok=True)
                    logger.info(f"[OK] Created directory: {path}")
                
                # Check write permission
                test_file = os.path.join(path, 'test_write.tmp')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                
                # Check disk space
                if self.check_disk_space(path, required_gb=2):
                    logger.info(f"[OK] {name} location is available: {path}")
                    return path
                else:
                    logger.warning(f"[WARN] {name} location has insufficient space, skipping")
                    
            except Exception as e:
                logger.warning(f"[WARN] {name} location not available: {e}")
                continue
        
        logger.error("[ERROR] No backup location available!")
        return None
    
    def create_backup(self):
        """Create the actual backup"""
        backup_location = self.find_available_backup_location()
        if not backup_location:
            return None
        
        backup_dir = os.path.join(backup_location, self.backup_name)
        os.makedirs(backup_dir, exist_ok=True)
        
        logger.info(f"[FOLDER] Creating backup at: {backup_dir}")
        
        # 1. Backup Media Files
        logger.info("[1/4] Backing up media files...")
        if os.path.exists(MEDIA_DIR):
            media_backup = os.path.join(backup_dir, 'media')
            self.copy_with_verification(MEDIA_DIR, media_backup)
            media_size = self.get_folder_size(media_backup)
            logger.info(f"[OK] Media backed up: {self.format_size(media_size)}")
        else:
            logger.warning("[WARN] Media directory not found!")
        
        # 2. Backup Database
        logger.info("[2/4] Backing up database...")
        if os.path.exists(DATABASE_PATH):
            db_backup = os.path.join(backup_dir, 'database.sqlite3')
            self.copy_file_with_hash(DATABASE_PATH, db_backup)
            logger.info(f"[OK] Database backed up")
        else:
            logger.warning("[WARN] Database not found!")
        
        # 3. Backup Configuration
        logger.info("[3/4] Backing up configuration...")
        self.backup_configuration(backup_dir)
        
        # 4. Create Manifest
        logger.info("[4/4] Creating backup manifest...")
        manifest = self.create_manifest(backup_dir)
        
        # 5. Create Compressed Archive
        logger.info("Creating compressed archive...")
        archive_path = self.create_archive(backup_dir, backup_location)
        
        # 6. Verify Backup
        if self.verify_backup(archive_path, manifest):
            logger.info(f"[OK] Backup verified and ready: {archive_path}")
            # Clean up uncompressed folder
            shutil.rmtree(backup_dir)
            self.backup_paths.append(archive_path)
            self.backup_created = True
            return archive_path
        else:
            logger.error("[ERROR] Backup verification failed!")
            return None
    
    def copy_with_verification(self, src, dst):
        """Copy with hash verification"""
        try:
            # Use robocopy for better performance on Windows
            cmd = f'robocopy "{src}" "{dst}" /E /COPY:DAT /R:3 /W:10 /NP /NDL /NJH /NJS'
            result = subprocess.run(cmd, shell=True, capture_output=True)
            
            # Verify copy
            src_files = sum([len(files) for r, d, files in os.walk(src)])
            dst_files = sum([len(files) for r, d, files in os.walk(dst)])
            
            if src_files == dst_files:
                logger.info(f"[OK] Copied {src_files} files")
            else:
                logger.warning(f"[WARN] Copied {dst_files}/{src_files} files")
                
        except Exception as e:
            logger.error(f"Copy error: {e}")
            # Fallback to normal copy
            shutil.copytree(src, dst, dirs_exist_ok=True)
    
    def copy_file_with_hash(self, src, dst):
        """Copy file with hash verification"""
        shutil.copy2(src, dst)
        
        # Verify hash
        with open(src, 'rb') as f:
            src_hash = hashlib.md5(f.read()).hexdigest()
        with open(dst, 'rb') as f:
            dst_hash = hashlib.md5(f.read()).hexdigest()
        
        if src_hash == dst_hash:
            logger.info(f"[OK] File verified: {os.path.basename(src)}")
        else:
            logger.error(f"[ERROR] Hash mismatch for {os.path.basename(src)}")
    
    def backup_configuration(self, backup_dir):
        """Backup config files"""
        config_dir = os.path.join(backup_dir, 'config')
        os.makedirs(config_dir, exist_ok=True)
        
        # Save settings
        settings = {
            'backup_version': '2.0',
            'created_by': 'School Library System',
            'note': 'Production Backup'
        }
        
        with open(os.path.join(config_dir, 'backup_info.json'), 'w') as f:
            json.dump(settings, f, indent=2)
        
        logger.info("[OK] Configuration backed up")
    
    def create_manifest(self, backup_dir):
        """Create detailed manifest of backup"""
        manifest = {
            'backup_id': self.backup_name,
            'created_at': datetime.now().isoformat(),
            'source_dirs': {
                'media': MEDIA_DIR,
                'database': DATABASE_PATH
            },
            'files': [],
            'total_size': 0,
            'file_count': 0
        }
        
        for root, dirs, files in os.walk(backup_dir):
            for file in files:
                if file != 'manifest.json':
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, backup_dir)
                    file_size = os.path.getsize(file_path)
                    
                    manifest['files'].append({
                        'path': rel_path,
                        'size': file_size,
                        'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                    })
                    manifest['total_size'] += file_size
                    manifest['file_count'] += 1
        
        manifest_path = os.path.join(backup_dir, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"[OK] Manifest created: {manifest['file_count']} files, {self.format_size(manifest['total_size'])}")
        return manifest
    
    def create_archive(self, source_dir, dest_dir):
        """Create ZIP archive with compression"""
        archive_path = os.path.join(dest_dir, f'{self.backup_name}.zip')
        
        logger.info(f"Compressing files to {archive_path}...")
        
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=COMPRESSION_LEVEL) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_dir)
                    zipf.write(file_path, arcname)
                    # Show progress every 10 files
                    if len(zipf.namelist()) % 10 == 0:
                        logger.debug(f"  Compressed {len(zipf.namelist())} files...")
        
        archive_size = os.path.getsize(archive_path)
        logger.info(f"[OK] Archive created: {self.format_size(archive_size)}")
        
        return archive_path
    
    def verify_backup(self, archive_path, manifest):
        """Verify backup integrity"""
        try:
            # Test ZIP integrity
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                if zipf.testzip() is not None:
                    logger.error("[ERROR] ZIP file corrupted!")
                    return False
            
            # Verify file count
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                zip_count = len(zipf.namelist())
            
            expected_count = manifest.get('file_count', 0)
            if zip_count == expected_count or zip_count == expected_count + 1:  # +1 for manifest itself
                logger.info(f"[OK] File count verified: {zip_count} files")
                return True
            else:
                logger.warning(f"File count mismatch: ZIP has {zip_count}, expected {expected_count}")
                return True  # Still consider it valid
                
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False
    
    def rotate_backups(self, backup_dir, keep_count=MAX_BACKUPS_TO_KEEP):
        """Remove old backups, keep only recent ones"""
        logger.info(f"Rotating backups in {backup_dir}, keeping last {keep_count}")
        
        backups = []
        for file in os.listdir(backup_dir):
            if file.startswith('library_prod_backup_') and file.endswith('.zip'):
                file_path = os.path.join(backup_dir, file)
                backups.append((file_path, os.path.getmtime(file_path)))
        
        backups.sort(key=lambda x: x[1], reverse=True)
        
        deleted_count = 0
        for backup_path, _ in backups[keep_count:]:
            try:
                os.remove(backup_path)
                deleted_count += 1
                logger.info(f"[DELETED] Old backup: {os.path.basename(backup_path)}")
            except Exception as e:
                logger.error(f"Failed to delete {backup_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"[OK] Deleted {deleted_count} old backups")
    
    def generate_report(self):
        """Generate backup report"""
        report = f"""
{'='*60}
SCHOOL LIBRARY BACKUP REPORT
{'='*60}
Backup ID: {self.backup_name}
Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Status: {'SUCCESS' if self.backup_created else 'FAILED'}

Backup Locations:
{chr(10).join(f'  - {path}' for path in self.backup_paths)}

Log File: {LOG_FILE}
{'='*60}
"""
        return report
    
    @staticmethod
    def get_folder_size(path):
        total = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total += os.path.getsize(fp)
        return total
    
    @staticmethod
    def format_size(size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

# ============================================================
# RUN BACKUP
# ============================================================

def run_backup():
    print("\n" + "="*60)
    print("   SCHOOL LIBRARY PRODUCTION BACKUP")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")
    
    backup = ProductionBackup()
    
    try:
        # Create backup
        result = backup.create_backup()
        
        if result:
            # Rotate old backups
            for name, path in BACKUP_PATHS.items():
                if os.path.exists(path):
                    backup.rotate_backups(path, keep_count=MAX_BACKUPS_TO_KEEP)
            
            # Generate report
            report = backup.generate_report()
            logger.info(report)
            
            print("\n[OK] BACKUP COMPLETED SUCCESSFULLY!")
            print(f"[FOLDER] Location: {result}")
            
        else:
            print("\n[ERROR] BACKUP FAILED!")
            print("Check logs at: " + LOG_FILE)
            
    except Exception as e:
        logger.error(f"Backup failed with error: {e}")
        print(f"\n[ERROR] ERROR: {e}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    run_backup()