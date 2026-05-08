# digitallibrary/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

# ============================================================
# SCHOOL SETTINGS & CORE MODELS
# ============================================================

class SchoolSetting(models.Model):
    """Global branding for the intranet"""
    name = models.CharField(max_length=255, default="Our School Library")
    motto = models.CharField(max_length=500, blank=True)
    logo = models.ImageField(upload_to="branding/", blank=True, null=True)
    
    # ADD THESE FIELDS
    address = models.TextField(blank=True, null=True, help_text="School physical address")
    phone = models.CharField(max_length=20, blank=True, null=True, help_text="School phone number")
    email = models.EmailField(blank=True, null=True, help_text="School email address")
    website = models.URLField(blank=True, null=True, help_text="School website")

    def __str__(self):
        return self.name


class Class(models.Model):
    """School classes/forms (e.g., Form 1A, Form 2B, Form 3C)"""
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=10, blank=True)
    stream = models.CharField(max_length=20, blank=True)
    capacity = models.PositiveIntegerField(default=40)
    
    class_teacher = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='homeroom_class',
        limit_choices_to={'profile__role': 'teacher'}
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
# In digitallibrary/models.py

class Category(models.Model):
    """Categories for resources (e.g., Exams, Notes, Schemes of Work)"""
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Subject(models.Model):
    """School subjects like Mathematics, English, Physics, etc."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, blank=True, null=True, help_text="Subject code (e.g., MATH, ENG)")
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"

    def __str__(self):
        return self.name


from django.db import models
from django.contrib.auth.models import User
from django_tenants.models import TenantMixin
from decimal import Decimal

class School(TenantMixin):
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to='school_logos/', blank=True, null=True)
    motto = models.CharField(max_length=200, blank=True)
    principal_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    auto_create_schema = True
    
    def __str__(self):
        return self.name
    
    def create_tenant_admin(self):
        """Create default admin user for this tenant"""
        from django.contrib.auth.models import User
        from django_tenants.utils import tenant_context
        
        with tenant_context(self):
            # Create main admin
            if not User.objects.filter(username='admin').exists():
                User.objects.create_superuser(
                    username='admin',
                    email=f"admin@{self.schema_name}.com",
                    password='Admin@2024'
                )
                print(f"✓ Admin created for {self.name}")
            
            # Create tenant-specific admin
            admin_name = f"{self.schema_name}_admin" if self.schema_name != 'public' else 'super_admin'
            if not User.objects.filter(username=admin_name).exists():
                User.objects.create_superuser(
                    username=admin_name,
                    email=f"{admin_name}@{self.schema_name}.com",
                    password='Tenant@2024'
                )
                print(f"✓ Created {admin_name} for {self.name}")
    
    def save(self, *args, **kwargs):
        is_new = not self.pk
        super().save(*args, **kwargs)
        
        # Auto-create admin for new tenants
        if is_new and self.schema_name != 'public':
            try:
                self.create_tenant_admin()
                print(f"✅ Auto-created admin users for {self.name}")
            except Exception as e:
                print(f"⚠ Could not auto-create admin: {e}")


# Signal to auto-create admin when tenant is created via admin interface
@receiver(post_save, sender=School)
def auto_create_tenant_admin(sender, instance, created, **kwargs):
    """Automatically create admin when tenant is created"""
    if created and instance.schema_name != 'public':
        try:
            instance.create_tenant_admin()
        except Exception as e:
            print(f"Signal error: {e}")



class Term(models.Model):
    TERM_CHOICES = [
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    ]
    term_number = models.IntegerField(choices=TERM_CHOICES)
    name = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    academic_year = models.CharField(max_length=9)  # e.g., "2024-2025"
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='terms')
    is_active = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['academic_year', 'term_number', 'school']
    
    def __str__(self):
        return f"{self.academic_year} - {self.name}"


class FeeCategory(models.Model):
    name = models.CharField(max_length=100)  # Tuition, Boarding, Transport, etc.
    description = models.TextField(blank=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='fee_categories')
    
    def __str__(self):
        return self.name


class FeeItem(models.Model):
    FREQUENCY_CHOICES = [
        ('termly', 'Termly'),
        ('monthly', 'Monthly'),
        ('annual', 'Annual'),
        ('one_time', 'One Time'),
    ]
    
    name = models.CharField(max_length=200)
    category = models.ForeignKey(FeeCategory, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='termly')
    is_mandatory = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class UserProfile(models.Model):
    """Assign roles to users with approval system"""
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('principal', 'Principal'),
        ('bursar', 'Bursar/Accountant'),
        ('teacher', 'Teacher'),
        ('secretary', 'Secretary'),
        ('student', 'Student'),
    ]
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teacher')
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} ({self.role}){' ✓' if self.is_approved else ' ✗'}"
class FeeStructure(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ]
    
    TERM_CHOICES = [
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    ]
    
    # Existing fields
    academic_year = models.CharField(max_length=9)
    term = models.IntegerField(choices=TERM_CHOICES)
    student_class = models.ForeignKey('Class', on_delete=models.CASCADE, related_name='fee_structures', null=True, blank=True)
    total_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deadline = models.DateField()
    late_fee_penalty = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # NEW FIELDS
    name = models.CharField(max_length=200, blank=True, null=True, help_text="Name of the fee structure")
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    payment_deadline = models.DateField(null=True, blank=True)
    payment_terms = models.TextField(blank=True, help_text="Payment terms and conditions")
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    class Meta:
        unique_together = ['student_class', 'term', 'academic_year']
        ordering = ['-academic_year', 'student_class__name']
    
    def __str__(self):
        class_name = self.student_class.name if self.student_class else "All Classes"
        return f"{self.name or class_name} - Term {self.term} ({self.academic_year})"
    
    def calculate_total(self):
        """Calculate total fees from all components"""
        total = sum(component.amount for component in self.custom_fees.all())
        self.total_fees = total
        return total
    
    def save(self, *args, **kwargs):
        """Override save to set name and calculate total"""
        if not self.name:
            class_name = self.student_class.name if self.student_class else "All Classes"
            self.name = f"{class_name} - Term {self.term} {self.academic_year}"
        super().save(*args, **kwargs)
        self.calculate_total()
        super().save(update_fields=['total_fees'])
# Add to digitallibrary/models.py

class TeacherSubject(models.Model):
    """Assign subjects to teachers"""
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subjects_taught')
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, related_name='teachers')
    class_assigned = models.ForeignKey('Class', on_delete=models.CASCADE, null=True, blank=True)
    academic_year = models.CharField(max_length=9)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['teacher', 'subject', 'academic_year']
    
    def __str__(self):
        return f"{self.teacher.username} - {self.subject.name}"


class ExamResultSummary(models.Model):
    """Summary of results for an exam (for class teacher compilation)"""
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, related_name='summaries')
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='exam_summaries')
    total_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overall_grade = models.CharField(max_length=2, blank=True)
    rank = models.IntegerField(null=True, blank=True)
    compiled_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['exam', 'student']
        ordering = ['rank']
    
    def __str__(self):
        return f"{self.student} - {self.exam.name}: Rank {self.rank}"
# Add to digitallibrary/models.py

from django.db.models.signals import post_save
from django.dispatch import receiver

# @receiver(post_save, sender=User)
# def create_teacher_profile(sender, instance, created, **kwargs):
#     if created and hasattr(instance, 'profile') and instance.profile.role == 'teacher':
#         # Auto-assign subjects based on class subjects
#         pass


class FeeComponent(models.Model):
    """Individual fee components (Tuition, Transport, etc.)"""

    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.CASCADE,
        related_name='custom_fees'
    )

    name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_optional = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name}: KES {self.amount}"
# Keep ONLY this version of StudentResult (delete the other one)
class StudentResult(models.Model):
    """Individual student results for each exam and subject"""
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='results')
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, related_name='results')
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, related_name='results')
    score = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=2, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    entered_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='entered_results')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'exam', 'subject']
        ordering = ['-exam__academic_year', '-exam__term', 'subject__name']
    
    def save(self, *args, **kwargs):
        if self.score is not None:
            from .models import Grade
            grade_obj = Grade.objects.filter(
                min_score__lte=self.score,
                max_score__gte=self.score
            ).first()
            if grade_obj:
                self.grade = grade_obj.grade
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.student} - {self.exam} - {self.subject}: {self.score}"

# ============================================================
# # ============================================================
# ============================================================
# ============================================================
# RESOURCE MODELS
# ============================================================

from cloudinary.models import CloudinaryField


class Resource(models.Model):

    class ResourceType(models.TextChoices):
        PDF = "PDF", "PDF"
        DOC = "DOC", "Word Document"
        VIDEO = "VIDEO", "Video"
        OTHER = "OTHER", "Other"

    class PaperType(models.TextChoices):
        P1 = "Paper 1", "Paper 1"
        P2 = "Paper 2", "Paper 2"
        PRAC = "Practical", "Practical"
        MARKING_SCHEME = "Marking Scheme", "Marking Scheme"
        REVISION = "Revision", "Revision"
        NOTES = "Notes", "Notes"
        NA = "N/A", "General Resource"

    # BASIC RESOURCE DETAILS
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    grade = models.CharField(max_length=50, default="General", help_text="e.g. Grade 10, Form 4")
    year = models.CharField(max_length=10, blank=True, null=True, help_text="Year of publication/exam")
    paper_type = models.CharField(max_length=20, choices=PaperType.choices, default=PaperType.NA)

    # RELATIONSHIPS
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True, related_name="resources")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="resources")
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="uploaded_resources")

    # RESOURCE TYPE
    resource_type = models.CharField(max_length=20, choices=ResourceType.choices, default=ResourceType.PDF)
    author = models.CharField(max_length=200, blank=True)

    # CLOUDINARY STORAGE - FIXED FOR PDFs
    # Use CloudinaryField with resource_type="raw" for PDFs
    file = CloudinaryField(
        "file",
        resource_type="raw",  # This ensures PDFs use /raw/upload URL
        folder="resources",
    )
    
    # Optional cover image (stays as image)
    cover_image = CloudinaryField(
        "image",
        blank=True,
        null=True,
        folder="covers",
        resource_type="image",
    )

    # METADATA
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    views = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["subject", "grade"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["year"]),
        ]

    def __str__(self):
        year_display = f" [{self.year}]" if self.year else ""
        return f"{self.title} ({self.grade}){year_display}"

    def increment_views(self):
        self.views += 1
        self.save(update_fields=["views"])

    @property
    def file_url(self):
        """Returns correct URL for file download"""
        if self.file:
            # Force raw resource type for all files
            return self.file.build_url(resource_type="raw", attachment=True)
        return ""

# ============================================================
# PRINTING MODELS
# ============================================================

class PrintJob(models.Model):
    """Tracks teacher printing requests with full workflow"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Printing', 'Printing'),
        ('Completed', 'Completed'),
    ]
    
    COLOR_CHOICES = [
        ('bw', 'Black & White'),
        ('color', 'Color'),
    ]
    
    file = models.FileField(upload_to="print_queue/")
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="print_jobs")
    copies = models.PositiveIntegerField(default=1)
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default='bw')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    downloaded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    completed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='completed_print_jobs'
    )
    
    downloaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='downloaded_print_jobs'
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.file.name} - {self.teacher.username} ({self.status})"
    
    def mark_as_downloaded(self, user=None):
        self.downloaded = True
        self.status = 'Printing'
        if user:
            self.downloaded_by = user
        self.save(update_fields=['downloaded', 'status', 'downloaded_by'])
    
    def mark_as_completed(self, user=None):
        self.status = 'Completed'
        self.completed_at = timezone.now()
        if user:
            self.completed_by = user
        self.save(update_fields=['status', 'completed_at', 'completed_by'])


# ============================================================
# NOTIFICATION MODELS
# ============================================================

class Notification(models.Model):
    """Notification system for print jobs and other events"""
    
    NOTIFICATION_TYPES = [
        ('print_job', 'Print Job'),
        ('print_downloaded', 'Print Job Downloaded'),
        ('print_completed', 'Print Completed'),
        ('announcement', 'Announcement'),
        ('system', 'System'),
    ]
    
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    sender = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='sent_notifications'
    )
    notification_type = models.CharField(
        max_length=20, 
        choices=NOTIFICATION_TYPES,
        default='print_job'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.recipient.username} - {self.title}"
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at'])
    
    @classmethod
    def get_unread_count(cls, user):
        return cls.objects.filter(recipient=user, is_read=False).count()
    
    @classmethod
    def create_print_job_notification(cls, print_job):
        recipients = User.objects.filter(
            profile__role__in=['secretary', 'admin']
        )
        if not recipients.exists():
            return []
        
        teacher_name = print_job.teacher.get_full_name() or print_job.teacher.username
        
        notifications = []
        for recipient in recipients:
            notification = cls(
                recipient=recipient,
                sender=print_job.teacher,
                notification_type='print_job',
                title=f"New Print Job from {teacher_name}",
                message=f"File: {print_job.file.name}\nCopies: {print_job.copies}\nColor: {print_job.get_color_display()}",
                link=f"/printing/job/{print_job.id}/"
            )
            notifications.append(notification)
        
        if notifications:
            cls.objects.bulk_create(notifications)
        return notifications
    
    @classmethod
    def create_print_downloaded_notification(cls, print_job):
        downloaded_by_name = "Secretary"
        if print_job.downloaded_by:
            downloaded_by_name = print_job.downloaded_by.get_full_name() or print_job.downloaded_by.username
        
        notification = cls(
            recipient=print_job.teacher,
            sender=print_job.downloaded_by,
            notification_type='print_downloaded',
            title=f"Print Job Downloaded: {print_job.file.name}",
            message=f"Your print job has been downloaded by {downloaded_by_name} and is now printing.\nCopies: {print_job.copies}",
            link=f"/printing/job/{print_job.id}/"
        )
        notification.save()
        return notification
    
    @classmethod
    def create_print_completed_notification(cls, print_job):
        completed_by_name = "Secretary"
        if print_job.completed_by:
            completed_by_name = print_job.completed_by.get_full_name() or print_job.completed_by.username
        
        notification = cls(
            recipient=print_job.teacher,
            sender=print_job.completed_by,
            notification_type='print_completed',
            title=f"Print Job Completed: {print_job.file.name}",
            message=f"Your print job has been completed by {completed_by_name}.\nCopies: {print_job.copies}",
            link=f"/printing/job/{print_job.id}/"
        )
        notification.save()
        return notification


# ============================================================
# ANNOUNCEMENT MODELS
# ============================================================

class Announcement(models.Model):
    """School announcements and notices with target audience and read tracking"""
    
    AUDIENCE_CHOICES = [
        ('all', 'Everyone (Students & Teachers)'),
        ('teachers', 'Teachers Only'),
        ('students', 'Students Only'),
        ('admin', 'Administrators Only'),
        ('staff', 'All Staff (Teachers & Admins)'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="announcements")
    is_featured = models.BooleanField(default=False)
    
    target_audience = models.CharField(
        max_length=20, 
        choices=AUDIENCE_CHOICES, 
        default='all',
        help_text="Who should see this announcement?"
    )
    
    attachment = models.FileField(
        upload_to='announcements/', 
        blank=True, 
        null=True,
        help_text="Optional: Upload a PDF, DOC, or other document related to this announcement"
    )
    
    expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Optional: Set an expiry date for this announcement"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_featured', '-created_at']
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        indexes = [
            models.Index(fields=['-created_at', 'is_featured']),
            models.Index(fields=['target_audience']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return self.title
    
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def read_count(self):
        return self.read_receipts.filter(read=True).count()
    
    def target_count(self):
        # Simplified - implement based on audience
        return 0
    
    def read_percentage(self):
        target = self.target_count()
        if target == 0:
            return 0
        return (self.read_count() / target) * 100


class AnnouncementRead(models.Model):
    announcement = models.ForeignKey('Announcement', on_delete=models.CASCADE, related_name='read_receipts')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['announcement', 'user']
    
    @classmethod
    def get_unread_count(cls, user):
        """Get number of unread announcements for a user"""
        if not user.is_authenticated:
            return 0
        return cls.objects.filter(
            user=user,
            read=False
        ).count()
    
    @classmethod
    def mark_as_read(cls, announcement, user):
        """Mark an announcement as read for a user"""
        obj, created = cls.objects.get_or_create(
            announcement=announcement,
            user=user
        )
        if not obj.read:
            obj.read = True
            obj.read_at = timezone.now()
            obj.save()

class ActivityLog(models.Model):
    """Track important actions in the system"""
    ACTION_CHOICES = [
        ('upload', 'Resource Uploaded'),
        ('download', 'File Downloaded'),
        ('print_submit', 'Print Job Submitted'),
        ('print_download', 'Print Job Downloaded'),
        ('print_complete', 'Print Job Completed'),
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('resource_view', 'Resource Viewed'),
        ('announcement_view', 'Announcement Viewed'),
        ('announcement_create', 'Announcement Created'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"


# ============================================================
# FEES MANAGEMENT MODELS
# ============================================================

class Student(models.Model):
    """Student profile linked to fees"""
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('N', 'Not Specified'),
    ]
    
    admission_number = models.CharField(max_length=20, unique=True)
    upi_number = models.CharField(max_length=20, blank=True, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='N')
    
    current_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, related_name='students')
    admission_year = models.IntegerField()
    is_active = models.BooleanField(default=True)
    
    parent_name = models.CharField(max_length=200)
    parent_phone = models.CharField(max_length=15)
    parent_alternative_phone = models.CharField(max_length=15, blank=True)
    parent_email = models.EmailField(blank=True)
    
    physical_address = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['current_class', 'last_name', 'first_name']
    
    def __str__(self):
        gender_symbol = '♂' if self.gender == 'M' else '♀' if self.gender == 'F' else '⚥'
        return f"{gender_symbol} {self.admission_number} - {self.first_name} {self.last_name}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"


class FeePayment(models.Model):
    """Individual payment record"""
    
    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('MPESA', 'M-PESA'),
        ('BANK', 'Bank Transfer'),
        ('CHEQUE', 'Cheque'),
    ]
    
    receipt_number = models.CharField(max_length=50, unique=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='CASH')
    transaction_id = models.CharField(max_length=100, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    term = models.IntegerField(choices=FeeStructure.TERM_CHOICES, default=1)
    academic_year = models.CharField(max_length=9, default='2026')
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"{self.receipt_number} - {self.student.get_full_name()}: KES {self.amount:,.2f}"


class FeeBalance(models.Model):
    """Current balance for each student per term"""
    
    STATUS_CHOICES = [
        ('PAID', 'Fully Paid'),
        ('PARTIAL', 'Partially Paid'),
        ('DEFAULTING', 'Defaulting'),
        ('OVERPAID', 'Overpaid'),
        ('EXEMPTED', 'Exempted'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_balances')
    term = models.IntegerField(choices=FeeStructure.TERM_CHOICES)
    academic_year = models.CharField(max_length=9)
    
    total_expected = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DEFAULTING')
    credit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'term', 'academic_year']
        ordering = ['-academic_year', '-term', 'student']
    
    def save(self, *args, **kwargs):
        actual_balance = self.total_expected - self.total_paid

        if actual_balance == 0:
            self.status = 'PAID'
            self.balance = 0
            self.credit_amount = 0
        elif actual_balance < 0:
            self.status = 'PAID'
            self.balance = 0
            self.credit_amount = abs(actual_balance)
        else:
            self.status = 'PARTIAL' if self.total_paid > 0 else 'DEFAULTING'
            self.balance = actual_balance
            self.credit_amount = 0

        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.status == 'OVERPAID':
            return f"{self.student.get_full_name()} - {self.academic_year} T{self.term}: Credit KES {self.credit_amount:,.2f}"
        elif self.status == 'PAID':
            return f"{self.student.get_full_name()} - {self.academic_year} T{self.term}: FULLY PAID"
        else:
            return f"{self.student.get_full_name()} - {self.academic_year} T{self.term}: Balance KES {self.balance:,.2f} ({self.status})"


# ============================================================
# PERFORMANCE ANALYSIS MODELS
# ============================================================

class Grade(models.Model):
    """Grade boundaries"""
    GRADE_CHOICES = [
        ('A', 'A (Excellent)'),
        ('A-', 'A- (Very Good)'),
        ('B+', 'B+ (Good)'),
        ('B', 'B (Above Average)'),
        ('B-', 'B- (Average)'),
        ('C+', 'C+ (Satisfactory)'),
        ('C', 'C (Fair)'),
        ('C-', 'C- (Below Average)'),
        ('D+', 'D+ (Poor)'),
        ('D', 'D (Very Poor)'),
        ('E', 'E (Fail)'),
    ]
    
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES, unique=True)
    min_score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    points = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    description = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"{self.grade} ({self.min_score} - {self.max_score})"
    
    class Meta:
        ordering = ['-min_score']


class Exam(models.Model):
    """Exam/Assessment types"""
    TERM_CHOICES = [
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    ]
    
    EXAM_TYPES = [
        ('end_of_term', 'End of Term'),
        ('mid_term', 'Mid Term'),
        ('opener', 'Opener'),
        ('mock', 'Mock Exam'),
        ('kcse', 'KCSE'),
        ('continuous_assessment', 'Continuous Assessment'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=100)
    exam_type = models.CharField(max_length=25, choices=EXAM_TYPES, default='end_of_term')
    term = models.IntegerField(choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=9)
    student_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, blank=True, related_name='exams')
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    exam_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-academic_year', '-term', 'student_class__name']
        unique_together = ['name', 'term', 'academic_year', 'student_class']
    
    def __str__(self):
        class_info = f" [{self.student_class.name}]" if self.student_class else " [All Classes]"
        return f"{self.name} ({self.academic_year} Term {self.term}){class_info}"
    
    def get_students_for_exam(self):
        if self.student_class:
            return Student.objects.filter(current_class=self.student_class, is_active=True)
        return Student.objects.filter(is_active=True)




class PerformanceSummary(models.Model):
    """Overall performance summary for a student per term/year"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='performance_summaries')
    academic_year = models.CharField(max_length=9)
    term = models.IntegerField(choices=Exam.TERM_CHOICES)
    total_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_points = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    average_points = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overall_grade = models.CharField(max_length=2, blank=True, null=True)
    rank_in_class = models.IntegerField(default=0)
    subjects_passed = models.IntegerField(default=0)
    subjects_failed = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'academic_year', 'term']
        ordering = ['-academic_year', '-term']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.academic_year} Term {self.term}: Avg {self.average_score} ({self.overall_grade})"


# ============================================================
# FEEDBACK MODEL
# ============================================================

class Feedback(models.Model):
    """User feedback for the system"""
    
    FEEDBACK_TYPES = [
        ('bug', 'Bug Report'),
        ('feature', 'Feature Request'),
        ('improvement', 'Improvement'),
        ('general', 'General Feedback'),
        ('issue', 'System Issue'),
        ('training', 'Training Request'),
        ('suggestion', 'Suggestion'),
        ('complaint', 'Complaint'),
        ('inquiry', 'Inquiry'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
        ('critical', 'Critical'),
    ]
    
    # User information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks', null=True, blank=True)
    user_role = models.CharField(max_length=50, blank=True, null=True, help_text="Role of the user (principal, teacher, admin, etc.)")
    user_email = models.EmailField(blank=True, null=True)
    user_name = models.CharField(max_length=200, blank=True, null=True)
    
    # Feedback content
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES, default='general')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    rating = models.IntegerField(default=0, help_text="1-5 rating", null=True, blank=True)
    page_url = models.CharField(max_length=500, blank=True)
    screenshot = models.ImageField(upload_to='feedback_screenshots/', blank=True, null=True)
    
    # School tracking - ENHANCED
    school_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    school_name = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    school_location = models.CharField(max_length=200, blank=True, null=True)
    school_email = models.EmailField(blank=True, null=True)
    school_phone = models.CharField(max_length=20, blank=True, null=True)
    school_domain = models.CharField(max_length=255, blank=True, null=True)
    school_subdomain = models.CharField(max_length=100, blank=True, null=True)
    
    # Device/Browser info
    browser_info = models.CharField(max_length=500, blank=True, null=True)
    device_type = models.CharField(max_length=50, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    # Status tracking
    status = models.CharField(
        max_length=20, 
        choices=[
            ('pending', 'Pending'),
            ('reviewing', 'Under Review'),
            ('in_progress', 'In Progress'),
            ('resolved', 'Resolved'),
            ('closed', 'Closed'),
            ('rejected', 'Rejected'),
        ],
        default='pending'
    )
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    admin_response = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_feedbacks')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Internal notes
    internal_notes = models.TextField(blank=True, help_text="Internal staff notes")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school_id', 'created_at']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['feedback_type', 'created_at']),
        ]
    
    def __str__(self):
        if self.school_name:
            return f"[{self.school_name}] {self.subject[:50]} - {self.user_name or 'Anonymous'}"
        return f"[No School] {self.subject[:50]} - {self.user_name or 'Anonymous'}"
    
    def get_school_display(self):
        """Return formatted school info"""
        if self.school_name:
            parts = [self.school_name]
            if self.school_location:
                parts.append(f"({self.school_location})")
            if self.school_id:
                parts.append(f"[{self.school_id}]")
            return " ".join(parts)
        return "Unknown School"
    
    def get_user_display(self):
        """Return formatted user info"""
        if self.user_name:
            return f"{self.user_name} ({self.user_role or 'User'})"
        if self.user:
            return f"{self.user.get_full_name() or self.user.username} ({self.user_role or 'User'})"
        if self.user_email:
            return f"{self.user_email} ({self.user_role or 'User'})"
        return "Anonymous User"
    
    def get_priority_color(self):
        """Return color for priority display"""
        colors = {
            'critical': '#dc2626',  # Red
            'urgent': '#ea580c',    # Orange
            'high': '#f59e0b',      # Amber
            'medium': '#10b981',    # Green
            'low': '#6b7280',       # Gray
        }
        return colors.get(self.priority, '#6b7280')
    
    def get_status_color(self):
        """Return color for status display"""
        colors = {
            'pending': '#f59e0b',     # Amber
            'reviewing': '#3b82f6',   # Blue
            'in_progress': '#8b5cf6', # Purple
            'resolved': '#10b981',    # Green
            'closed': '#6b7280',      # Gray
            'rejected': '#dc2626',    # Red
        }
        return colors.get(self.status, '#6b7280')
    
    def mark_resolved(self, admin_response=None):
        """Mark feedback as resolved"""
        self.is_resolved = True
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        if admin_response:
            self.admin_response = admin_response
        self.save()
    
    def respond(self, response_text, admin_user):
        """Add admin response to feedback"""
        self.admin_response = response_text
        self.assigned_to = admin_user
        self.status = 'reviewing'
        self.save()


class FeedbackAttachment(models.Model):
    """Additional attachments for feedback"""
    feedback = models.ForeignKey(Feedback, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='feedback_attachments/')
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="File size in bytes", default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Attachment for {self.feedback.subject[:30]}"

class SMSLog(models.Model):
    """Track SMS messages sent to parents/students"""
    
    CATEGORY_CHOICES = [
        ('fee_reminder', 'Fee Reminder'),
        ('exam_results', 'Exam Results'),
        ('attendance', 'Attendance Alert'),
        ('general', 'General Announcement'),
        ('emergency', 'Emergency'),
    ]
    
    recipient = models.CharField(max_length=15)
    recipient_name = models.CharField(max_length=200, blank=True)
    student = models.ForeignKey(Student, on_delete=models.SET_NULL, null=True, blank=True, related_name='sms_logs')
    message = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    status = models.CharField(max_length=20, default='pending')
    response = models.TextField(blank=True, null=True)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_sms')
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"SMS to {self.recipient} - {self.category}"


# ============================================================
# PAPER SET MODELS (For organized exam papers)
# ============================================================

class PaperSet(models.Model):
    """Organized collection of exam papers with proper hierarchy"""
    
    PAPER_TYPES = [
        ('PP1', 'Paper 1'),
        ('PP2', 'Paper 2'),
        ('PP3', 'Paper 3'),
        ('PP4', 'Paper 4'),
        ('PR', 'Practical'),
        ('OP', 'Oral'),
        ('CAT', 'CAT'),
        ('MID', 'Mid-term'),
        ('END', 'End of Term'),
        ('MOCK', 'Mock'),
        ('PRE', 'Preliminary'),
        ('KCSE', 'KCSE'),
        ('KPSEA', 'KPSEA'),
    ]
    
    EXAM_TYPES = [
        ('internal', 'Internal School Exam'),
        ('national', 'National Exam'),
        ('district', 'District/County Exam'),
    ]
    
    # Hierarchy
    grade = models.CharField(max_length=50, help_text="e.g., Form 4, Grade 8")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='paper_sets', null=True, blank=True)
    year = models.CharField(max_length=10, db_index=True)
    term = models.CharField(max_length=20, blank=True, null=True)
    
    # Paper details
    paper_type = models.CharField(max_length=10, choices=PAPER_TYPES, default='END')
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPES, default='internal')
    
    # Metadata
    title = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    view_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['-year', 'grade', 'subject__name']
        unique_together = ['grade', 'subject', 'year', 'term', 'paper_type']
        indexes = [
            models.Index(fields=['grade', 'year']),
            models.Index(fields=['subject', 'year']),
            models.Index(fields=['is_featured']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.title:
            subject_name = self.subject.name if self.subject else "General"
            term_text = f" - {self.term}" if self.term else ""
            self.title = f"{self.grade} {subject_name} {self.get_paper_type_display()} ({self.year}){term_text}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.title


class PaperResource(models.Model):
    """Resources linked to PaperSets"""
    
    KIND_CHOICES = [
        ('Q', 'Questions'),
        ('MS', 'Marking Scheme'),
        ('N', 'Notes'),
        ('V', 'Video'),
        ('S', 'Syllabus'),
        ('P', 'Past Papers'),
        ('T', 'Timetable'),
        ('R', 'Revision'),
    ]
    
    paper_set = models.ForeignKey(PaperSet, on_delete=models.CASCADE, related_name='resources')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, db_index=True)
    file = models.FileField(upload_to='papers/')
    
    title = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    file_hash = models.CharField(max_length=64, blank=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['kind', '-uploaded_at']
        unique_together = ['paper_set', 'kind']
        indexes = [
            models.Index(fields=['paper_set', 'kind']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.title:
            self.title = f"{self.paper_set.title} - {self.get_kind_display()}"
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.title