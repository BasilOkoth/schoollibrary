import requests
import json
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from digitallibrary.models import School as LocalSchool, Student, Book, Download, Visit

class Command(BaseCommand):
    help = 'Sync school analytics to central dashboard'

    def handle(self, *args, **options):
        self.stdout.write("=" * 50)
        self.stdout.write(f"Starting sync to central dashboard at {timezone.now()}")
        self.stdout.write("=" * 50)

        # Get school info from local settings
        school_id = settings.SCHOOL_ID  # Add this to settings.py
        api_key = settings.API_KEY      # Add this to settings.py
        dashboard_url = settings.DASHBOARD_URL  # Add this to settings.py

        if not dashboard_url:
            self.stdout.write(self.style.ERROR("DASHBOARD_URL not configured in settings"))
            return

        # Collect analytics data
        self.stdout.write("📊 Collecting analytics data...")
        
        analytics_data = {
            "school_id": school_id,
            "api_key": api_key,
            "data": {
                "total_teachers_enrolled": self.get_teacher_count(),
                "total_staff_enrolled": self.get_staff_count(),
                "total_students_enrolled": self.get_student_count(),
                "total_student_visits": self.get_visit_count(),
                "unique_student_devices": self.get_device_count(),
                "total_books_uploaded": self.get_book_count(),
                "total_papers_read": self.get_papers_read_count(),
                "total_downloads": self.get_download_count(),
                "total_messages_sent": self.get_message_count(),
                "total_print_requests": self.get_print_count(),
                "new_students_since_sync": self.get_new_students(),
                "new_books_since_sync": self.get_new_books(),
                "visits_since_sync": self.get_recent_visits(),
                "sync_date": timezone.now().isoformat()
            }
        }

        # Send to central dashboard
        self.stdout.write("📤 Sending data to central dashboard...")
        
        try:
            response = requests.post(
                f"{dashboard_url}/api/sync/",
                json=analytics_data,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                self.stdout.write(self.style.SUCCESS(f"✅ Sync successful: {result.get('message', 'OK')}"))
                
                # Update last sync time in local database
                self.update_last_sync()
                
            else:
                self.stdout.write(self.style.ERROR(f"❌ Sync failed: {response.status_code} - {response.text}"))
                
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"❌ Connection error: {e}"))
            self.stdout.write("⚠️ Will retry on next scheduled run")

        self.stdout.write("=" * 50)

    def get_teacher_count(self):
        from digitallibrary.models import Teacher
        return Teacher.objects.filter(is_active=True).count()

    def get_staff_count(self):
        from digitallibrary.models import Staff
        return Staff.objects.filter(is_active=True).count()

    def get_student_count(self):
        from digitallibrary.models import Student
        return Student.objects.filter(is_active=True).count()

    def get_visit_count(self):
        from digitallibrary.models import Visit
        return Visit.objects.count()

    def get_device_count(self):
        from digitallibrary.models import Device
        return Device.objects.values('device_id').distinct().count()

    def get_book_count(self):
        from digitallibrary.models import Book
        return Book.objects.count()

    def get_papers_read_count(self):
        from digitallibrary.models import PaperRead
        return PaperRead.objects.count()

    def get_download_count(self):
        from digitallibrary.models import Download
        return Download.objects.count()

    def get_message_count(self):
        from digitallibrary.models import Message
        return Message.objects.count()

    def get_print_count(self):
        from digitallibrary.models import PrintRequest
        return PrintRequest.objects.count()

    def get_new_students(self):
        from digitallibrary.models import Student
        from django.utils import timezone
        from datetime import timedelta
        last_day = timezone.now() - timedelta(days=1)
        return Student.objects.filter(created_at__gte=last_day).count()

    def get_new_books(self):
        from digitallibrary.models import Book
        from django.utils import timezone
        from datetime import timedelta
        last_day = timezone.now() - timedelta(days=1)
        return Book.objects.filter(created_at__gte=last_day).count()

    def get_recent_visits(self):
        from digitallibrary.models import Visit
        from django.utils import timezone
        from datetime import timedelta
        last_day = timezone.now() - timedelta(days=1)
        return Visit.objects.filter(created_at__gte=last_day).count()

    def update_last_sync(self):
        from digitallibrary.models import SchoolSyncLog
        SchoolSyncLog.objects.create(
            sync_time=timezone.now(),
            status='success'
        )