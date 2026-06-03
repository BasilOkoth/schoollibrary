# digitallibrary/apps.py

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_default_tenant_data(sender, **kwargs):
    """Create default data for new tenants after migration"""
    from django.contrib.auth.models import User
    from django_tenants.utils import schema_context
    
    try:
        from tenants.models import School
        from .models import Category, Subject, Grade
        
        # Only run in public schema to avoid duplicate creation
        with schema_context('public'):
            # Create default admin if none exists
            if not User.objects.filter(is_superuser=True).exists():
                User.objects.create_superuser(
                    username='superadmin',
                    email='superadmin@shulehub.com',
                    password='SuperAdmin@2025'
                )
                print("✓ Super admin created in public schema")
            
            # Create default categories
            default_categories = ['Exams', 'Notes', 'Schemes of Work', 'Past Papers', 'Revision Materials']
            for cat_name in default_categories:
                Category.objects.get_or_create(
                    name=cat_name, 
                    slug=cat_name.lower().replace(' ', '-')
                )
            
            # Create default subjects
            default_subjects = [
                'Mathematics', 'English', 'Kiswahili', 'Biology', 'Chemistry', 
                'Physics', 'History', 'Geography', 'CRE', 'Business Studies', 
                'Computer Studies', 'Agriculture', 'Home Science', 'Art & Design', 
                'Music', 'Physical Education', 'Arabic', 'French', 'German'
            ]
            for subj_name in default_subjects:
                Subject.objects.get_or_create(name=subj_name)
            
            # Create default grading system (Kenya CBC/KNEC style)
            default_grades = [
                ('A', 80, 100, 12, 'Excellent'),
                ('A-', 75, 79, 11, 'Very Good'),
                ('B+', 70, 74, 10, 'Good'),
                ('B', 65, 69, 9, 'Above Average'),
                ('B-', 60, 64, 8, 'Above Average'),
                ('C+', 55, 59, 7, 'Average'),
                ('C', 50, 54, 6, 'Average'),
                ('C-', 45, 49, 5, 'Below Average'),
                ('D+', 40, 44, 4, 'Below Average'),
                ('D', 35, 39, 3, 'Poor'),
                ('D-', 30, 34, 2, 'Poor'),
                ('E', 0, 29, 1, 'Fail'),
            ]
            
            for grade, min_score, max_score, points, description in default_grades:
                Grade.objects.get_or_create(
                    grade=grade,
                    defaults={
                        'min_score': min_score,
                        'max_score': max_score,
                        'points': points,
                        'description': description
                    }
                )
            print("✓ Default grading system created")
            
            print("✓ Default tenant data initialized successfully")
            
    except Exception as e:
        print(f"Note: Default data creation skipped - {e}")


def setup_tenant_signals(sender, **kwargs):
    """Setup signals for tenant creation"""
    try:
        from . import signals
    except ImportError:
        print("Note: signals.py not found, skipping signal import")


class LibraryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'digitallibrary'
    
    def ready(self):
        """
        Initialize app when Django is ready.
        This runs after all models are loaded.
        """
        import sys
        
        # Skip during initial migration to avoid circular imports
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return
        
        try:
            # Connect post_migrate signal to create default data
            post_migrate.connect(create_default_tenant_data, sender=self)
            
            # Import signals for tenant creation (if they exist)
            setup_tenant_signals(sender=self)
            
        except Exception as e:
            # Don't break the app if signals fail - they'll work on next run
            print(f"Note: Signal setup incomplete: {e}")
