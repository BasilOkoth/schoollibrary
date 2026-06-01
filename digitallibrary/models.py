# digitallibrary/models.py

from django.db import models
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from storages.backends.s3boto3 import S3Boto3Storage
from django.db import models
from django.contrib.auth.models import User
from django_tenants.models import TenantMixin
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
# ============================================================
# SCHOOL SETTINGS & CORE MODELS
# ============================================================
from storages.backends.s3boto3 import S3Boto3Storage
class SchoolSetting(models.Model):
    """Global branding for the intranet"""
    name = models.CharField(max_length=255, default="Our School Library")
    motto = models.CharField(max_length=500, blank=True)
    logo = models.ImageField(upload_to="branding/", storage=S3Boto3Storage(),blank=True, null=True)
    
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
    
    CATEGORY_CHOICES = [
        ('compulsory', 'Compulsory'),
        ('arts_sports', 'Arts & Sports Science'),
        ('social_sciences', 'Social Sciences'),
        ('stem', 'STEM'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    
    code = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        help_text="Subject code (e.g., MATH, ENG)"
    )
    
    description = models.TextField(blank=True, null=True)
    
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='compulsory',
        db_index=True
    )
    
    is_compulsory = models.BooleanField(default=False, db_index=True)
    
    is_active = models.BooleanField(default=True, db_index=True)
    
    order = models.IntegerField(default=0, help_text="Display order within category")
    
    applicable_classes = models.ManyToManyField(
        'Class', 
        blank=True, 
        related_name='subjects_offered',
        help_text="Which classes can take this subject"
    )
    
    # ADD THIS - Link subject to its CBE pathway (one pathway per subject)
    cbe_pathway = models.ForeignKey(
        'CBEGradingPathway',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects_in_pathway',  # Changed from 'subjects' to avoid conflict
        help_text="CBE Pathway this subject belongs to"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'order', 'name']
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"
        indexes = [
            models.Index(fields=['category', 'is_compulsory', 'is_active']),
            models.Index(fields=['name']),
            models.Index(fields=['cbe_pathway']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.code and self.name:
            self.code = self.name.replace(' ', '_').replace('/', '_').replace('-', '_').upper()[:20]
        
        if self.order == 0:
            category_order = {'compulsory': 100, 'arts_sports': 200, 'social_sciences': 300, 'stem': 400}
            self.order = category_order.get(self.category, 500)
        
        super().save(*args, **kwargs)
    
    @property
    def category_display(self):
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category)
    
    @property
    def is_elective(self):
        return not self.is_compulsory
    
    @property
    def uses_cbe_grading(self):
        return self.cbe_pathway is not None
    
    @classmethod
    def get_compulsory_subjects(cls):
        return cls.objects.filter(is_compulsory=True, is_active=True)
    
    @classmethod
    def get_elective_subjects(cls):
        return cls.objects.filter(is_compulsory=False, is_active=True)
    
    @classmethod
    def get_subjects_by_category(cls, category):
        if category == 'compulsory':
            return cls.objects.filter(is_compulsory=True, is_active=True)
        return cls.objects.filter(category=category, is_active=True)
    
    def get_available_for_classes(self):
        return self.applicable_classes.all()
    
    def is_available_for_class(self, class_obj):
        return self.applicable_classes.filter(id=class_obj.id).exists()
class School(TenantMixin):
    # Existing fields
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    logo = models.ImageField(upload_to='school_logos/', blank=True, null=True)
    motto = models.CharField(max_length=200, blank=True)
    principal_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # NEW: Subscription/Billing Fields (ADD THESE)
    paid_until = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Subscription paid until date"
    )
    on_trial = models.BooleanField(
        default=True, 
        help_text="Whether the school is on trial period"
    )
    
    # NEW: Grading System Selection (UPDATED with 'custom' option)
    GRADING_SYSTEM_CHOICES = [
        ('traditional', 'Traditional (8-4-4) - A to E'),
        ('cbc', 'CBC/CBE - EE1 to BE2'),
        ('both', 'Both Systems (Traditional & CBC)'),
        ('custom', 'Custom Grading System (School Defined)'),
    ]
    
    grading_system = models.CharField(
        max_length=20,
        choices=GRADING_SYSTEM_CHOICES,
        default='traditional',
        help_text="Select the grading system used by the school"
    )
    
    # NEW: Link to custom grading system (if 'custom' is selected)
    custom_grading_system = models.ForeignKey(
        'digitallibrary.GradingSystem', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='schools_using',
        help_text="Select the custom grading system if 'Custom' is selected above"
    )
    
    # NEW: Academic Settings
    academic_year_start = models.DateField(null=True, blank=True, help_text="Start date of current academic year")
    academic_year_end = models.DateField(null=True, blank=True, help_text="End date of current academic year")
    current_term = models.IntegerField(default=1, choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')])
    
    # NEW: Pass Mark Configuration (per school flexibility)
    pass_mark = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=40.00,
        help_text="Minimum percentage required to pass (Default: 40% for 8-4-4, 41% for CBC)"
    )
    
    # NEW: Grading Scale Customization (optional override)
    use_custom_grading = models.BooleanField(default=False, help_text="Use custom grading scale instead of standard")
    
    # NEW: School Contact Person
    contact_person = models.CharField(max_length=100, blank=True, help_text="Primary contact person name")
    contact_phone = models.CharField(max_length=20, blank=True, help_text="Contact person phone number")
    
    # NEW: School Colors/Branding
    primary_color = models.CharField(max_length=7, default='#2c3e50', help_text="School primary color (Hex code)")
    secondary_color = models.CharField(max_length=7, default='#3498db', help_text="School secondary color (Hex code)")
    
    auto_create_schema = True
    
    def __str__(self):
        return self.name
    
    def get_grading_system_display_name(self):
        """Return display name for grading system"""
        return dict(self.GRADING_SYSTEM_CHOICES).get(self.grading_system, 'Traditional')
    
    def get_pass_mark(self):
        """Get appropriate pass mark based on grading system"""
        if self.use_custom_grading:
            return float(self.pass_mark)
        elif self.grading_system == 'cbc':
            return 41.00  # CBC pass mark
        else:
            return 40.00  # Traditional pass mark
    
    def get_current_academic_year(self):
        """Get current academic year based on dates"""
        from django.utils import timezone
        if self.academic_year_start and self.academic_year_end:
            now = timezone.now().date()
            if self.academic_year_start <= now <= self.academic_year_end:
                return self.academic_year_start.year
        return timezone.now().year
    
    def get_active_grading_system(self):
        """Get the active GradingSystem object for this school"""
        from digitallibrary.models import GradingSystem
        if self.grading_system == 'custom' and self.custom_grading_system:
            return self.custom_grading_system
        else:
            # Return the default grading system for this school type
            return GradingSystem.objects.filter(
                school=self,
                system_type=self.grading_system,
                is_active=True,
                is_default=True
            ).first()
    
    def is_active_subscription(self):
        """Check if the school has an active subscription"""
        from django.utils import timezone
        if self.on_trial:
            return True
        if self.paid_until and self.paid_until >= timezone.now():
            return True
        return False
    
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
        
        # Auto-create default grading system for new tenants
        if is_new and self.schema_name != 'public':
            try:
                self.create_tenant_admin()
                self._create_default_grading_system()
                print(f"✅ Auto-created admin users and grading system for {self.name}")
            except Exception as e:
                print(f"⚠ Could not auto-create: {e}")
    
    def _create_default_grading_system(self):
        """Create default grading system for the school"""
        from digitallibrary.models import GradingSystem, GradingScale
        
        # Create grading system based on school's choice
        system_name = f"{self.name} - {self.get_grading_system_display_name()}"
        
        grading_system = GradingSystem.objects.create(
            name=system_name,
            system_type=self.grading_system if self.grading_system != 'custom' else 'default',
            created_by=None,  # Will be set later when admin exists
            school=self,
            is_active=True,
            is_default=True
        )
        
        # Create grading scales based on system type
        if self.grading_system == 'traditional':
            grades_data = [
                ('A', 80, 100, 12, 'Excellent'),
                ('A-', 75, 79, 11, 'Very Good'),
                ('B+', 70, 74, 10, 'Good'),
                ('B', 65, 69, 9, 'Above Average'),
                ('B-', 60, 64, 8, 'Average'),
                ('C+', 55, 59, 7, 'Satisfactory'),
                ('C', 50, 54, 6, 'Acceptable'),
                ('C-', 45, 49, 5, 'Below Average'),
                ('D+', 40, 44, 4, 'Weak'),
                ('D', 35, 39, 3, 'Very Weak'),
                ('D-', 30, 34, 2, 'Poor'),
                ('E', 0, 29, 1, 'Very Poor'),
            ]
        elif self.grading_system == 'cbc':
            grades_data = [
                ('EE1', 90, 100, 8, 'Exceptional/Excellent'),
                ('EE2', 75, 89, 7, 'Very Good'),
                ('ME1', 58, 74, 6, 'Good'),
                ('ME2', 41, 57, 5, 'Fair'),
                ('AE1', 31, 40, 4, 'Needs Improvement'),
                ('AE2', 21, 30, 3, 'Below Average'),
                ('BE1', 11, 20, 2, 'Well Below Average'),
                ('BE2', 0, 10, 1, 'Minimal'),
            ]
        else:  # both or custom
            grades_data = [
                ('A/EE1', 90, 100, 12, 'Excellent/Exceptional'),
                ('A-/EE2', 75, 89, 11, 'Very Good'),
                ('B+/ME1', 70, 74, 10, 'Good'),
                ('B/ME2', 65, 69, 9, 'Above Average'),
                ('B-/ME2', 60, 64, 8, 'Average'),
                ('C+/AE1', 55, 59, 7, 'Satisfactory'),
                ('C/AE1', 50, 54, 6, 'Acceptable'),
                ('C-/AE2', 45, 49, 5, 'Below Average'),
                ('D+/AE2', 40, 44, 4, 'Weak'),
                ('D/BE1', 35, 39, 3, 'Very Weak'),
                ('D-/BE2', 30, 34, 2, 'Poor'),
                ('E/BE2', 0, 29, 1, 'Very Poor'),
            ]
        
        for grade, min_score, max_score, points, remark in grades_data:
            GradingScale.objects.create(
                grading_system=grading_system,
                grade=grade,
                min_score=min_score,
                max_score=max_score,
                points=points,
                remark=remark,
                is_active=True
            )
        
        print(f"✓ Created default grading system with {len(grades_data)} grades for {self.name}")
        return grading_system
    
    class Meta:
        verbose_name = "School"
        verbose_name_plural = "Schools"
        ordering = ['name']

class CustomGradingScale(models.Model):
    """Allow schools to define their own grading scale"""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='grading_scales')
    grade_letter = models.CharField(max_length=5)
    grade_name = models.CharField(max_length=50)
    min_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    max_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    points = models.IntegerField(default=0)
    status = models.CharField(max_length=10, choices=[('PASS', 'Pass'), ('FAIL', 'Fail')])
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['min_percentage']
        unique_together = ['school', 'grade_letter']
    
    def __str__(self):
        return f"{self.school.name} - {self.grade_letter} ({self.min_percentage}%-{self.max_percentage}%)"

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

# Add to your existing UserProfile model in digitallibrary/models.py

class UserProfile(models.Model):
    """Assign roles to users with approval system"""
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('principal', 'Principal'),
        ('bursar', 'Bursar/Accountant'),
        ('teacher', 'Teacher'),
        ('secretary', 'Secretary'),
        ('student', 'Student'),
        ('parent', 'Parent'),
    ]
    
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teacher')
    is_approved = models.BooleanField(default=False)
    
    # Contact information
    phone = models.CharField(max_length=15, blank=True, null=True)  # Changed from phone_number to phone
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    
    # Parent specific fields
    children = models.ManyToManyField('Student', blank=True, related_name='parents')
    
    # Profile picture
    avatar = models.ImageField(upload_to='profiles/', blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()}){' ✓' if self.is_approved else ' ✗'}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
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
    score = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Grade information - INCREASED MAX LENGTHS
    grade = models.CharField(max_length=10, blank=True, null=True)  # Changed from 5 to 10
    points = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    grade_remark = models.CharField(max_length=200, blank=True, null=True)  # Changed from 100 to 200
    grading_system_used = models.CharField(max_length=30, blank=True, null=True, choices=[
        ('traditional', 'Traditional Grade System'),
        ('cbe', 'KNEC Competency-Based Education'),
        ('custom', 'Custom Teacher Grading'),
    ])  # Changed from 20 to 30
    
    # Result metadata
    remarks = models.TextField(blank=True, null=True)
    teacher_comment = models.TextField(blank=True, null=True)
    entered_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='entered_results')
    
    # CBE Specific fields - INCREASED MAX LENGTHS
    competency_level = models.CharField(max_length=30, blank=True, null=True, choices=[
        ('EE1', 'Exceeding Expectations Level 1'),
        ('EE2', 'Exceeding Expectations Level 2'),
        ('ME1', 'Meeting Expectations Level 1'),
        ('ME2', 'Meeting Expectations Level 2'),
        ('AE2', 'Approaching Expectations Level 2'),
        ('AE1', 'Approaching Expectations Level 1'),
        ('BE2', 'Below Expectations Level 2'),
        ('BE1', 'Below Expectations Level 1'),
    ])  # Changed from 20 to 30
    performance_trend = models.CharField(max_length=200, blank=True, null=True)  # Changed from 50 to 200
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'exam', 'subject']
        ordering = ['-exam__academic_year', '-exam__term', 'subject__name']
        indexes = [
            models.Index(fields=['student', 'exam', 'subject']),
            models.Index(fields=['grade']),
            models.Index(fields=['competency_level']),
        ]
    
    def save(self, *args, **kwargs):
        """Calculate grade based on student's pathway and grading system"""
        if self.score is not None:
            grade_info = self.get_grade_info()
            if grade_info:
                self.grade = grade_info.get('grade')
                self.points = grade_info.get('points', 0)
                self.grade_remark = grade_info.get('remark', '')
                self.grading_system_used = grade_info.get('system', 'traditional')
                
                # Set CBE specific fields
                if self.grading_system_used == 'cbe':
                    self.competency_level = grade_info.get('grade')
                    self.performance_trend = grade_info.get('performance_trend', '')
        
        super().save(*args, **kwargs)
    
    def get_grade_info(self):
        """Get grade information based on student's pathway and grading system"""
        from .models import TeacherGradingPreference, CBEGradingPathway, Grade
        from .views import get_grade_for_score
        
        # Check if student is in CBE pathway
        if self.student and hasattr(self.student, 'pathway') and self.student.pathway:
            try:
                cbe_pathway = CBEGradingPathway.objects.filter(
                    pathway_type=self.student.pathway,
                    is_active=True
                ).first()
                
                if cbe_pathway and cbe_pathway.grading_system:
                    grade_obj = cbe_pathway.grading_system.grades.filter(
                        min_score__lte=self.score,
                        max_score__gte=self.score
                    ).first()
                    
                    if grade_obj:
                        return {
                            'grade': grade_obj.grade,
                            'points': grade_obj.points,
                            'remark': grade_obj.remark,
                            'system': 'cbe',
                            'performance_trend': self.get_cbe_performance_trend(grade_obj.grade)
                        }
            except Exception as e:
                print(f"CBE grade lookup error: {e}")
        
        # Check for custom teacher grading for this exam/subject
        if self.exam and self.subject:
            try:
                preference = TeacherGradingPreference.objects.filter(
                    exam=self.exam,
                    subject=self.subject
                ).first()
                
                if preference and preference.use_custom_grading and preference.custom_grading_system:
                    grade_obj = preference.custom_grading_system.grades.filter(
                        min_score__lte=self.score,
                        max_score__gte=self.score
                    ).first()
                    
                    if grade_obj:
                        return {
                            'grade': grade_obj.grade,
                            'points': grade_obj.points,
                            'remark': grade_obj.remark,
                            'system': 'custom'
                        }
            except Exception as e:
                print(f"Custom grading lookup error: {e}")
        
        # Default traditional grading system
        try:
            grade_obj = Grade.objects.filter(
                min_score__lte=self.score,
                max_score__gte=self.score
            ).first()
            
            if grade_obj:
                return {
                    'grade': grade_obj.grade,
                    'points': grade_obj.points,
                    'remark': grade_obj.remark,
                    'system': 'traditional'
                }
        except Exception as e:
            print(f"Traditional grading lookup error: {e}")
        
        # Fallback grading if no system is configured
        if self.score >= 80:
            return {'grade': 'A', 'points': 12, 'remark': 'Excellent', 'system': 'traditional'}
        elif self.score >= 70:
            return {'grade': 'B', 'points': 9, 'remark': 'Good', 'system': 'traditional'}
        elif self.score >= 60:
            return {'grade': 'C', 'points': 6, 'remark': 'Average', 'system': 'traditional'}
        elif self.score >= 50:
            return {'grade': 'D', 'points': 3, 'remark': 'Below Average', 'system': 'traditional'}
        else:
            return {'grade': 'E', 'points': 1, 'remark': 'Fail', 'system': 'traditional'}
    
    def get_cbe_performance_trend(self, grade):
        """Get performance trend description for CBE grades"""
        trends = {
            'EE1': 'Exceptional performance beyond grade level expectations',
            'EE2': 'Outstanding performance exceeding expectations',
            'ME1': 'Consistently meeting grade level expectations',
            'ME2': 'Adequately meeting core expectations',
            'AE2': 'Making progress toward meeting expectations',
            'AE1': 'Beginning to approach grade level expectations',
            'BE2': 'Limited progress, needs significant support',
            'BE1': 'Minimal progress, intensive intervention required',
        }
        return trends.get(grade, 'Performance level recorded')
    
    @property
    def is_passing(self):
        """Check if student passed based on grading system"""
        if self.grading_system_used == 'cbe':
            # In CBE, EE1, EE2, ME1, ME2 are passing
            passing_grades = ['EE1', 'EE2', 'ME1', 'ME2']
            return self.grade in passing_grades
        else:
            # Traditional: grades A-D are passing, E is fail
            failing_grades = ['E', 'F']
            return self.grade not in failing_grades if self.grade else False
    
    @property
    def performance_level(self):
        """Get human-readable performance level"""
        if self.grading_system_used == 'cbe':
            levels = {
                'EE1': 'Exceeding Expectations',
                'EE2': 'Exceeding Expectations',
                'ME1': 'Meeting Expectations',
                'ME2': 'Meeting Expectations',
                'AE2': 'Approaching Expectations',
                'AE1': 'Approaching Expectations',
                'BE2': 'Below Expectations',
                'BE1': 'Below Expectations',
            }
            return levels.get(self.grade, 'Not Assessed')
        else:
            levels = {
                'A': 'Excellent',
                'B': 'Good',
                'C': 'Average',
                'D': 'Below Average',
                'E': 'Fail',
            }
            return levels.get(self.grade, 'Not Assessed')
    
    def __str__(self):
        return f"{self.student} - {self.exam} - {self.subject}: {self.score}% ({self.grade})"
# ============================================================
# # ============================================================
# ============================================================
# ============================================================
# RESOURCE MODELS
# ============================================================

# Remove this import:
# from cloudinary.models import CloudinaryField

# Add this import:
from django.core.files.storage import default_storage


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

    # S3 STORAGE - Use FileField instead of CloudinaryField
    file = models.FileField(
        upload_to='resources/%Y/%m/%d/',  # Organize by year/month/day
        storage=S3Boto3Storage(),
        max_length=500,
        blank=True,
        null=True
    )
    
    # Optional cover image (also goes to S3)
    cover_image = models.ImageField(
        upload_to='covers/%Y/%m/%d/',
        
        blank=True,
        null=True
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
        """Returns correct URL for file download from S3"""
        if self.file:
            return self.file.url
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
    """Student profile linked to fees with soft delete support"""
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('N', 'Not Specified'),
    ]

    PATHWAY_CHOICES = [
        ('arts_sports', 'Arts & Sports Science'),
        ('social_sciences', 'Social Sciences'),
        ('stem', 'Science, Technology, Engineering & Mathematics'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('transferred', 'Transferred Out'),
        ('graduated', 'Graduated'),
        ('suspended', 'Suspended'),
        ('withdrawn', 'Withdrawn'),
        ('deactivated', 'Deactivated'),
        ('archived', 'Archived'),
    ]
    
    TRANSFER_REASON_CHOICES = [
        ('transfer', 'Transferred to Another School'),
        ('graduated', 'Graduated/Completed'),
        ('withdrawn', 'Withdrawn by Parents'),
        ('suspended', 'Suspended'),
        ('expelled', 'Expelled'),
        ('deceased', 'Deceased'),
        ('other', 'Other Reason'),
    ]
    
    admission_number = models.CharField(max_length=20, unique=True)
    upi_number = models.CharField(max_length=20, blank=True, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='N')
    
    current_class = models.ForeignKey(
        Class,
        on_delete=models.SET_NULL,
        null=True,
        related_name='students'
    )

    pathway = models.CharField(
        max_length=30,
        choices=PATHWAY_CHOICES,
        blank=True,
        null=True
    )

    subjects = models.ManyToManyField(
        Subject,
        blank=True,
        related_name='students'
    )

    admission_year = models.IntegerField()
    
    # ========== SOFT DELETE & STATUS FIELDS ==========
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='active',
        db_index=True
    )
    is_active = models.BooleanField(default=True, db_index=True)  # Keep for backward compatibility
    
    # Soft delete tracking
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='deleted_students'
    )
    transfer_reason = models.CharField(
        max_length=30, 
        choices=TRANSFER_REASON_CHOICES, 
        blank=True, 
        null=True
    )
    transfer_reason_other = models.TextField(blank=True, help_text="Detailed reason for transfer/deactivation")
    transfer_date = models.DateField(null=True, blank=True)
    transfer_to_school = models.CharField(max_length=200, blank=True, help_text="Name of school transferred to (if applicable)")
    
    # Archive tracking
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='archived_students'
    )
    
    # Additional student info
    parent_name = models.CharField(max_length=200, blank=True, null=True)
    parent_phone = models.CharField(max_length=15, blank=True, null=True)
    parent_alternative_phone = models.CharField(max_length=15, blank=True)
    parent_email = models.EmailField(blank=True)
    
    physical_address = models.TextField(blank=True)
    
    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['current_class', 'last_name', 'first_name']
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['deleted_at']),
            models.Index(fields=['admission_number', 'status']),
        ]
    
    def __str__(self):
        status_icon = '✓' if self.is_active else '✗'
        gender_symbol = '♂' if self.gender == 'M' else '♀' if self.gender == 'F' else '⚥'
        return f"{status_icon} {gender_symbol} {self.admission_number} - {self.first_name} {self.last_name}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    # ========== SOFT DELETE METHODS ==========
    
    def soft_delete(self, user, reason=None, reason_type='other', transfer_to=None):
        """
        Soft delete a student - marks as inactive and archives records
        """
        from django.utils import timezone
        from .models import StudentActionLog
        
        self.is_active = False
        self.status = 'deactivated'
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.transfer_reason = reason_type
        self.transfer_reason_other = reason or ''
        self.transfer_date = timezone.now().date()
        self.transfer_to_school = transfer_to or ''
        
        # Archive the student
        self.archived_at = timezone.now()
        self.archived_by = user
        
        self.save()
        
        # Log the action
        StudentActionLog.objects.create(
            student=self,
            action='deactivated',
            performed_by=user,
            reason=reason or reason_type,
            details={
                'reason_type': reason_type,
                'transfer_to': transfer_to,
                'previous_status': 'active'
            }
        )
        
        return True
    
    def reactivate(self, user, reason=None):
        """
        Reactivate a soft-deleted student
        """
        from django.utils import timezone
        from .models import StudentActionLog
        
        self.is_active = True
        self.status = 'active'
        self.deleted_at = None
        self.deleted_by = None
        self.transfer_reason = None
        self.transfer_reason_other = ''
        self.transfer_date = None
        self.transfer_to_school = ''
        
        self.save()
        
        StudentActionLog.objects.create(
            student=self,
            action='reactivated',
            performed_by=user,
            reason=reason or 'Student reactivated',
            details={'previous_status': 'deactivated'}
        )
        
        return True
    
    def archive(self, user, reason=None):
        """
        Archive student without fully deactivating (for graduates)
        """
        from django.utils import timezone
        from .models import StudentActionLog
        
        self.status = 'archived'
        self.is_active = False
        self.archived_at = timezone.now()
        self.archived_by = user
        
        self.save()
        
        StudentActionLog.objects.create(
            student=self,
            action='archived',
            performed_by=user,
            reason=reason or 'Student archived',
            details={'status': 'archived'}
        )
        
        return True
    
    def mark_graduated(self, user):
        """
        Mark student as graduated
        """
        from django.utils import timezone
        from .models import StudentActionLog
        
        self.status = 'graduated'
        self.is_active = False
        self.transfer_reason = 'graduated'
        self.transfer_date = timezone.now().date()
        
        self.save()
        
        StudentActionLog.objects.create(
            student=self,
            action='graduated',
            performed_by=user,
            reason='Student graduated',
            details={'graduation_date': timezone.now().date().isoformat()}
        )
        
        return True
    
    def transfer_out(self, user, transfer_to=None, reason=None):
        """
        Mark student as transferred to another school
        """
        from django.utils import timezone
        from .models import StudentActionLog
        
        self.status = 'transferred'
        self.is_active = False
        self.transfer_reason = 'transfer'
        self.transfer_reason_other = reason or ''
        self.transfer_date = timezone.now().date()
        self.transfer_to_school = transfer_to or ''
        
        self.save()
        
        StudentActionLog.objects.create(
            student=self,
            action='transferred',
            performed_by=user,
            reason=reason or 'Student transferred out',
            details={'transfer_to': transfer_to, 'transfer_date': str(timezone.now().date())}
        )
        
        return True
    
    def is_deleted(self):
        """Check if student is soft deleted"""
        return not self.is_active or self.deleted_at is not None
    
    def can_be_permanently_deleted(self):
        """Check if student can be permanently deleted (after retention period)"""
        from django.utils import timezone
        from datetime import timedelta
        
        if self.deleted_at:
            retention_days = 90  # 90 days retention period
            return timezone.now() > self.deleted_at + timedelta(days=retention_days)
        return False
    
    # ========== FEE MANAGEMENT METHODS ==========
    
    def get_total_fees_expected(self, academic_year=None, term=None):
        """Calculate total fees expected for the student"""
        from .models import FeeStructure
        
        total = 0
        
        if academic_year and term and self.current_class:
            try:
                fee_structure = FeeStructure.objects.get(
                    student_class=self.current_class,
                    academic_year=academic_year,
                    term=term
                )
                total += fee_structure.total_fees or 0
            except FeeStructure.DoesNotExist:
                pass
        
        return total
    
    def get_total_fees_paid(self, academic_year=None, term=None):
        """Calculate total fees paid by the student"""
        from .models import FeePayment
        from django.db.models import Sum
        
        filters = {'student': self}
        if academic_year:
            filters['academic_year'] = academic_year
        if term:
            filters['term'] = term
            
        payments = FeePayment.objects.filter(**filters)
        total = payments.aggregate(total=Sum('amount'))['total'] or 0
        return total
    
    def get_fee_balance(self, academic_year=None, term=None):
        """Calculate current fee balance (arrears)"""
        if not academic_year or not term:
            from .models import Term
            active_term = Term.objects.filter(is_active=True).first()
            if active_term:
                academic_year = academic_year or active_term.academic_year
                term = term or active_term.term_number
            else:
                return 0
        
        expected = self.get_total_fees_expected(academic_year, term)
        paid = self.get_total_fees_paid(academic_year, term)
        return expected - paid
    
    def get_total_historical_arrears(self):
        """Get total historical arrears for this student"""
        from .models import HistoricalArrears
        from django.db.models import Sum
        
        total = HistoricalArrears.objects.filter(
            student=self, 
            is_settled=False
        ).aggregate(total=Sum('amount'))['total'] or 0
        return total
    
    def get_total_outstanding_balance(self, academic_year=None, term=None):
        """Calculate total outstanding including current balance and historical arrears"""
        current_balance = self.get_fee_balance(academic_year, term)
        historical_arrears = self.get_total_historical_arrears()
        return current_balance + historical_arrears
    
    def get_fee_balance_object(self, academic_year, term):
        """Get or create FeeBalance object for this student"""
        from .models import FeeBalance
        
        if term:
            term = int(term)
        
        balance_obj, created = FeeBalance.objects.get_or_create(
            student=self,
            academic_year=academic_year,
            term=term,
            defaults={
                'total_expected': self.get_total_fees_expected(academic_year, term),
                'total_paid': self.get_total_fees_paid(academic_year, term),
                'balance': self.get_fee_balance(academic_year, term),
                'status': 'PARTIAL'
            }
        )
        
        if not created:
            balance_obj.total_expected = self.get_total_fees_expected(academic_year, term)
            balance_obj.total_paid = self.get_total_fees_paid(academic_year, term)
            balance_obj.balance = self.get_fee_balance(academic_year, term)
            balance_obj.save()
        
        return balance_obj
    
    def get_payment_history(self, academic_year=None, term=None):
        """Get all payments with receipt numbers"""
        filters = {'student': self}
        if academic_year:
            filters['academic_year'] = academic_year
        if term:
            filters['term'] = term
        return self.fee_payments.filter(**filters).order_by('-payment_date')
    
    def get_historical_arrears_details(self):
        """Get all historical arrears for this student"""
        from .models import HistoricalArrears
        return HistoricalArrears.objects.filter(student=self, is_settled=False)
    
    def has_outstanding_balance(self, academic_year=None, term=None):
        """Check if student has any outstanding balance"""
        return self.get_total_outstanding_balance(academic_year, term) > 0
    
    def get_payment_summary_by_term(self):
        """Get payment summary grouped by academic year and term"""
        from .models import FeePayment
        from django.db.models import Sum
        
        return self.fee_payments.values(
            'academic_year', 'term'
        ).annotate(
            total_paid=Sum('amount')
        ).order_by('-academic_year', '-term')
    
    def get_fee_structure_history(self):
        """Get all fee structures applicable to this student's class"""
        from .models import FeeStructure
        
        if self.current_class:
            return FeeStructure.objects.filter(
                student_class=self.current_class
            ).order_by('-academic_year', '-term')
        return FeeStructure.objects.none()


class StudentActionLog(models.Model):
    """Track all student status changes"""
    
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('enrolled', 'Enrolled'),
        ('transferred', 'Transferred Out'),
        ('graduated', 'Graduated'),
        ('suspended', 'Suspended'),
        ('reactivated', 'Reactivated'),
        ('deactivated', 'Deactivated'),
        ('archived', 'Archived'),
        ('updated', 'Information Updated'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='action_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    reason = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['student', 'action']),
            models.Index(fields=['-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.student.admission_number} - {self.action} by {self.performed_by} at {self.timestamp}"

class FeePayment(models.Model):
    """Fee payment records"""
    
    # Add PAYMENT_METHODS as a class attribute
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('mpesa', 'M-Pesa'),
        ('bank', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('card', 'Card'),
    ]
    
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='fee_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    receipt_number = models.CharField(max_length=50, unique=True, blank=True)
    academic_year = models.CharField(max_length=9)
    term = models.IntegerField(choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')])
    remarks = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Receipt fields
    receipt_generated = models.BooleanField(default=False)
    receipt_pdf = models.FileField(upload_to='receipts/', blank=True, null=True)
    
    class Meta:
        ordering = ['-payment_date']
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        super().save(*args, **kwargs)
    
    def generate_receipt_number(self):
        """Generate a unique receipt number"""
        import random
        import string
        year = datetime.now().strftime('%Y')
        prefix = f"RCP/{year}/"
        
        # Get the last receipt number
        last_receipt = FeePayment.objects.filter(
            receipt_number__startswith=prefix
        ).order_by('-receipt_number').first()
        
        if last_receipt:
            try:
                last_num = int(last_receipt.receipt_number.split('/')[-1])
                new_num = last_num + 1
            except:
                new_num = 1
        else:
            new_num = 1
        
        return f"{prefix}{new_num:06d}"
    
    def __str__(self):
        return f"{self.receipt_number} - {self.student} - {self.amount}"

class FeeBalance(models.Model):
    """Current balance for each student per term with historical arrears tracking"""
    
    STATUS_CHOICES = [
        ('PAID', 'Fully Paid'),
        ('PARTIAL', 'Partially Paid'),
        ('DEFAULTING', 'Defaulting'),
        ('OVERPAID', 'Overpaid'),
        ('EXEMPTED', 'Exempted'),
        ('CARRIED_FORWARD', 'Carried Forward from Previous Class'),  # ADD THIS
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_balances')
    term = models.IntegerField(choices=FeeStructure.TERM_CHOICES)
    academic_year = models.CharField(max_length=9)
    
    total_expected = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DEFAULTING')
    credit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # NEW FIELDS FOR HISTORICAL ARREARS TRACKING
    carried_over_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, 
                                                help_text="Arrears carried from previous classes")
    previous_class = models.ForeignKey('Class', on_delete=models.SET_NULL, null=True, blank=True, 
                                        related_name='carried_balances', 
                                        help_text="Which class the arrears originated from")
    previous_academic_year = models.CharField(max_length=9, blank=True, null=True, 
                                               help_text="Academic year when arrears originated (e.g., 2022-2023)")
    historical_notes = models.TextField(blank=True, null=True, 
                                         help_text="Notes about historical arrears (e.g., 'From Form 1 Term 3')")
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'term', 'academic_year']
        ordering = ['-academic_year', '-term', 'student']
    
    def save(self, *args, **kwargs):
        # Include carried over balance in calculation
        actual_balance = self.total_expected - self.total_paid + self.carried_over_balance

        if actual_balance == 0:
            self.status = 'PAID'
            self.balance = 0
            self.credit_amount = 0
        elif actual_balance < 0:
            self.status = 'PAID'
            self.balance = 0
            self.credit_amount = abs(actual_balance)
        else:
            # Check if this is a carried forward balance
            if self.carried_over_balance > 0 and self.total_paid == 0:
                self.status = 'CARRIED_FORWARD'
            else:
                self.status = 'PARTIAL' if self.total_paid > 0 else 'DEFAULTING'
            self.balance = actual_balance
            self.credit_amount = 0

        super().save(*args, **kwargs)
    
    @property
    def total_arrears(self):
        """Calculate total arrears including carried over amounts"""
        return self.balance + self.carried_over_balance
    
    @property
    def is_historical_arrears(self):
        """Check if this balance contains historical arrears"""
        return self.carried_over_balance > 0
    
    def __str__(self):
        if self.status == 'OVERPAID':
            return f"{self.student.get_full_name()} - {self.academic_year} T{self.term}: Credit KES {self.credit_amount:,.2f}"
        elif self.status == 'PAID':
            return f"{self.student.get_full_name()} - {self.academic_year} T{self.term}: FULLY PAID"
        elif self.status == 'CARRIED_FORWARD':
            return f"{self.student.get_full_name()} - {self.academic_year} T{self.term}: Carried Forward KES {self.carried_over_balance:,.2f} from {self.previous_academic_year or 'previous class'}"
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

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewing', 'Under Review'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
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
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedback'
    
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
    
    def get_priority_display(self):
        """Return priority display name"""
        return dict(self.PRIORITY_CHOICES).get(self.priority, 'Medium')
    
    def get_status_display(self):
        """Return status display name"""
        return dict(self.STATUS_CHOICES).get(self.status, 'Pending')
    
    def get_feedback_type_display(self):
        """Return feedback type display name"""
        return dict(self.FEEDBACK_TYPES).get(self.feedback_type, 'General')
    
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
    
    @property
    def is_high_priority(self):
        """Check if feedback is high priority"""
        return self.priority in ['high', 'urgent', 'critical']
    
    @property
    def days_pending(self):
        """Calculate days since creation if still pending"""
        if self.status == 'pending' and self.created_at:
            delta = timezone.now() - self.created_at
            return delta.days
        return 0


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
# ============================================================
# PARENT PORTAL MODELS
# ============================================================

class ParentOTP(models.Model):
    """OTP authentication for parent portal"""

    phone = models.CharField(max_length=20, db_index=True)

    otp_code = models.CharField(max_length=6)

    is_used = models.BooleanField(default=False)

    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.phone} - {self.otp_code}"

    def is_expired(self):
        return timezone.now() > self.expires_at

    @classmethod
    def generate_otp(cls):
        import random
        return str(random.randint(100000, 999999))
class StudentSubject(models.Model):
    """Simple tracking of which subjects each student takes"""
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='subjects_taken')
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, related_name='students_taking')
    registered_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['student', 'subject']  # Prevents duplicate registrations
        ordering = ['subject__name']
    
    def __str__(self):
        return f"{self.student.admission_number} - {self.subject.name}"
# =========================
# digitallibrary/models.py - Grading System Section

# =========================
# GRADING SYSTEM MODELS
# =========================

class GradingSystem(models.Model):
    """Custom grading system for different exams - School customizable"""
    
    SYSTEM_TYPES = [
        ('default', 'Default System'),
        ('custom', 'Custom Teacher Grading'),
        ('cbe', 'Competency-Based Education (CBE)'),
        ('letter', 'Letter Grade System (A, B, C, D, E)'),
        ('numerical', 'Numerical Grade System (75-100, 50-74, etc.)'),
        ('pass_fail', 'Pass/Fail System'),
        ('subject_specific', 'Subject-Specific Grading'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=100, help_text="e.g., KCSE Grading System, CBE Pathway A, etc.")
    description = models.TextField(blank=True, null=True, help_text="Optional description of this grading system")
    system_type = models.CharField(max_length=20, choices=SYSTEM_TYPES, default='default')
    
    # Relationships
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='grading_systems')
    school = models.ForeignKey('tenants.School', on_delete=models.CASCADE, null=True, blank=True, 
                               related_name='grading_systems', help_text="School that owns this grading system")
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, null=True, blank=True, 
                             related_name='grading_systems', help_text="Specific exam this grading applies to")
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, null=True, blank=True,
                               help_text="Specific subject this grading applies to")
    
    # Status Flags
    is_active = models.BooleanField(default=True, help_text="Whether this grading system is currently active")
    is_default = models.BooleanField(default=False, help_text="Use this as the school's default grading system")
    is_archived = models.BooleanField(default=False, help_text="Archive old grading systems")
    is_subject_specific = models.BooleanField(default=False, help_text="Is this grading system specific to a subject?")
    
    # Grading Configuration
    passing_score = models.DecimalField(max_digits=5, decimal_places=2, default=50.00,
                                        help_text="Minimum passing score")
    max_score = models.DecimalField(max_digits=5, decimal_places=2, default=100.00,
                                    help_text="Maximum possible score")
    min_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00,
                                    help_text="Minimum possible score")
    
    # For raw score grading (e.g., 0-50 marks)
    max_raw_score = models.DecimalField(max_digits=6, decimal_places=2, default=100.00, null=True, blank=True,
                                        help_text="Maximum raw score if different from percentage")
    
    # Grade Calculation Method
    CALCULATION_METHODS = [
        ('percentage', 'Percentage Based'),
        ('points', 'Points Based'),
        ('weighted', 'Weighted Average'),
        ('competency', 'Competency Level'),
        ('raw_score', 'Raw Score Based'),
    ]
    calculation_method = models.CharField(max_length=20, choices=CALCULATION_METHODS, default='percentage')
    
    # Grade Calculation Type
    GRADE_CALCULATION_TYPES = [
        ('standard', 'Standard (Higher score = Better grade)'),
        ('reverse', 'Reverse (Lower score = Better grade, e.g., Golf)'),
        ('competency', 'Competency-Based'),
    ]
    grade_calculation_type = models.CharField(max_length=20, choices=GRADE_CALCULATION_TYPES, default='standard')
    
    # Display Settings
    show_points = models.BooleanField(default=True, help_text="Show grade points")
    show_remark = models.BooleanField(default=True, help_text="Show grade remarks (Excellent, Good, etc.)")
    show_percentage = models.BooleanField(default=True, help_text="Show percentage in reports")
    
    # Subject-specific settings
    applicable_subjects = models.ManyToManyField('Subject', blank=True, related_name='applicable_grading_systems',
                                                  help_text="Subjects this grading system applies to")
    applicable_classes = models.ManyToManyField('Class', blank=True, related_name='applicable_grading_systems',
                                                 help_text="Classes this grading system applies to")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_default', '-is_active', 'name']
        
    def __str__(self):
        school_name = f" [{self.school.name}]" if self.school else ""
        default_marker = " ★" if self.is_default else ""
        subject_info = f" - {self.subject.name}" if self.subject else ""
        return f"{self.name}{subject_info}{default_marker} ({self.system_type}){school_name}"
    
    def get_grades(self):
        """Get all active grades for this system"""
        return self.grades.filter(is_active=True).order_by('-min_score')
    
    def get_grade_for_score(self, score, max_possible=None):
        """Get grade details for a given score, optionally scaling to percentage"""
        # Convert raw score to percentage if max_possible provided
        if max_possible and max_possible != 100:
            percentage = (score / max_possible) * 100
            score = percentage
        
        # Handle reverse grading (lower score = better grade)
        if self.grade_calculation_type == 'reverse':
            # Convert score to inverted percentage
            score = 100 - score
        
        try:
            grade = self.grades.filter(
                min_score__lte=score,
                max_score__gte=score,
                is_active=True
            ).first()
            return grade
        except:
            return None
    
    def calculate_grade(self, score, max_possible=None):
        """Calculate grade, points, and remark for a score"""
        grade_obj = self.get_grade_for_score(score, max_possible)
        if grade_obj:
            # Determine if passing based on calculation type
            is_passing = False
            if self.grade_calculation_type == 'reverse':
                is_passing = score <= self.passing_score
            else:
                # Convert to percentage if needed
                compare_score = score
                if max_possible and max_possible != 100:
                    compare_score = (score / max_possible) * 100
                is_passing = compare_score >= self.passing_score
            
            return {
                'grade': grade_obj.grade,
                'points': grade_obj.points,
                'remark': grade_obj.remark,
                'is_passing': is_passing
            }
        return {
            'grade': 'N/A',
            'points': 0,
            'remark': 'Not Graded',
            'is_passing': False
        }
    
    def save(self, *args, **kwargs):
        # If this is set as default, unset other defaults for the same school
        if self.is_default and self.school:
            GradingSystem.objects.filter(
                school=self.school, 
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)
    
    def duplicate(self):
        """Create a copy of this grading system"""
        new_system = GradingSystem.objects.create(
            name=f"{self.name} (Copy)",
            description=self.description,
            system_type=self.system_type,
            created_by=self.created_by,
            school=self.school,
            is_active=False,
            passing_score=self.passing_score,
            max_score=self.max_score,
            min_score=self.min_score,
            calculation_method=self.calculation_method,
            show_points=self.show_points,
            show_remark=self.show_remark,
            show_percentage=self.show_percentage,
            is_subject_specific=self.is_subject_specific,
            max_raw_score=self.max_raw_score,
            grade_calculation_type=self.grade_calculation_type,
        )
        # Copy all grade scales
        for grade in self.grades.all():
            GradeScale.objects.create(
                grading_system=new_system,
                grade=grade.grade,
                min_score=grade.min_score,
                max_score=grade.max_score,
                points=grade.points,
                remark=grade.remark,
                description=grade.description,
                is_active=grade.is_active,
                color_code=grade.color_code
            )
        # Copy many-to-many relationships
        new_system.applicable_subjects.set(self.applicable_subjects.all())
        new_system.applicable_classes.set(self.applicable_classes.all())
        return new_system
    
    def is_applicable_to_subject(self, subject):
        """Check if this grading system applies to a specific subject"""
        if self.subject:
            return self.subject == subject
        return self.applicable_subjects.filter(id=subject.id).exists()
    
    def is_applicable_to_class(self, class_obj):
        """Check if this grading system applies to a specific class"""
        if self.applicable_classes.exists():
            return self.applicable_classes.filter(id=class_obj.id).exists()
        return True  # If no classes specified, applies to all
    
    @classmethod
    def get_applicable_grading_systems_for_subject(cls, subject, academic_year=None, term=None):
        """Get applicable grading systems for a subject"""
        from django.db import models
        systems = cls.objects.filter(
            models.Q(subject=subject) | models.Q(applicable_subjects=subject),
            is_active=True
        )
        if academic_year and term:
            # Also check subject configs
            configs = SubjectGradingConfig.objects.filter(
                subject=subject,
                academic_year=academic_year,
                term=term,
                is_active=True
            )
            if configs.exists():
                systems = systems | cls.objects.filter(id__in=configs.values('grading_system_id'))
        return systems.distinct()


class GradeScale(models.Model):
    """Individual grade scale within a grading system"""
    
    GRADES = [
        ('A+', 'A+ (Excellent)'),
        ('A', 'A (Very Good)'),
        ('A-', 'A- (Good)'),
        ('B+', 'B+ (Above Average)'),
        ('B', 'B (Average)'),
        ('B-', 'B- (Below Average)'),
        ('C+', 'C+ (Satisfactory)'),
        ('C', 'C (Fair)'),
        ('C-', 'C- (Poor)'),
        ('D+', 'D+ (Very Poor)'),
        ('D', 'D (Fail)'),
        ('E', 'E (Fail)'),
        ('PASS', 'Pass'),
        ('FAIL', 'Fail'),
    ]
    
    grading_system = models.ForeignKey(GradingSystem, on_delete=models.CASCADE, related_name='grades')
    grade = models.CharField(max_length=10, choices=GRADES, help_text="e.g., A, B+, C-, Pass, Fail")
    custom_grade = models.CharField(max_length=20, blank=True, null=True, help_text="Custom grade label if not using standard")
    
    min_score = models.DecimalField(max_digits=5, decimal_places=2, help_text="Minimum score for this grade")
    max_score = models.DecimalField(max_digits=5, decimal_places=2, help_text="Maximum score for this grade")
    points = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Grade points (e.g., 12 for A)")
    
    remark = models.CharField(max_length=200, blank=True, help_text="e.g., Excellent, Good, Fair, Fail")
    description = models.TextField(blank=True, help_text="Detailed description of this grade level")
    
    # CBE specific fields
    is_competency = models.BooleanField(default=False, help_text="Is this a competency level?")
    competency_level = models.CharField(max_length=20, blank=True, null=True, 
                                        choices=[
                                            ('EE', 'Exceeding Expectations'),
                                            ('ME', 'Meeting Expectations'),
                                            ('AE', 'Approaching Expectations'),
                                            ('BE', 'Below Expectations'),
                                        ])
    
    # Visual settings
    color_code = models.CharField(max_length=7, blank=True, null=True, 
                                  help_text="Hex color code for this grade (e.g., #4CAF50)")
    sort_order = models.IntegerField(default=0, help_text="Order to display grades")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-min_score', 'sort_order']
        unique_together = ['grading_system', 'grade']
    
    def __str__(self):
        return f"{self.grade}: {self.min_score}% - {self.max_score}% ({self.remark})"
    
    @property
    def display_grade(self):
        """Return custom grade or standard grade"""
        return self.custom_grade if self.custom_grade else self.grade
    
    def get_color(self):
        """Get color for this grade"""
        if self.color_code:
            return self.color_code
        # Default colors based on grade
        colors = {
            'A+': '#10B981', 'A': '#10B981', 'A-': '#34D399',
            'B+': '#3B82F6', 'B': '#3B82F6', 'B-': '#60A5FA',
            'C+': '#F59E0B', 'C': '#F59E0B', 'C-': '#FBBF24',
            'D+': '#EF4444', 'D': '#EF4444', 'E': '#DC2626',
            'PASS': '#10B981', 'FAIL': '#EF4444',
        }
        return colors.get(self.grade, '#6B7280')


class SubjectGradingConfig(models.Model):
    """Configure grading for specific subjects - allows different subjects to have different grading criteria"""
    
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, related_name='grading_configs')
    grading_system = models.ForeignKey(GradingSystem, on_delete=models.CASCADE, related_name='subject_configs')
    academic_year = models.CharField(max_length=9, help_text="e.g., 2024-2025")
    term = models.IntegerField(choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')], null=True, blank=True)
    
    # Subject-specific settings
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100.00, 
                                    help_text="Maximum possible score for this subject")
    passing_score = models.DecimalField(max_digits=5, decimal_places=2, default=50.00, 
                                        help_text="Minimum passing score for this subject")
    
    # Component weighting (for subjects with multiple assessments)
    exam_weight = models.DecimalField(max_digits=5, decimal_places=2, default=70.00, 
                                      help_text="Weight for final exam")
    coursework_weight = models.DecimalField(max_digits=5, decimal_places=2, default=30.00, 
                                           help_text="Weight for coursework")
    practical_weight = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, null=True, blank=True,
                                           help_text="Weight for practical component")
    
    # Additional settings
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True, help_text="Additional notes about this grading configuration")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['subject', 'academic_year', 'term']
        ordering = ['subject__name', '-academic_year', 'term']
        verbose_name = "Subject Grading Configuration"
        verbose_name_plural = "Subject Grading Configurations"
    
    def __str__(self):
        term_text = f" Term {self.term}" if self.term else ""
        return f"{self.subject.name} - {self.academic_year}{term_text} ({self.grading_system.name})"
    
    def calculate_grade(self, score):
        """Calculate grade based on this subject's configuration"""
        if self.max_score != 100:
            # Convert to percentage if different max score
            percentage = (score / self.max_score) * 100
        else:
            percentage = score
        
        return self.grading_system.calculate_grade(percentage)
    
    def calculate_weighted_score(self, exam_score, coursework_score, practical_score=None):
        """Calculate weighted total score from components"""
        total = (exam_score * self.exam_weight / 100) + (coursework_score * self.coursework_weight / 100)
        if practical_score and self.practical_weight:
            total += (practical_score * self.practical_weight / 100)
        return total


class TeacherGradingPreference(models.Model):
    """Teacher's preference for grading system - Supports multiple grading types"""
    
    GRADING_CHOICES = [
        ('traditional', '📊 Traditional Grade System (Default)'),
        ('custom', '⚙️ My Custom Grading System'),
        ('cbe', '🎯 Competency-Based Education (CBE)'),
        ('school_default', '🏫 School Default System'),
        ('exam_specific', '📝 Exam Specific Grading'),
        ('subject_specific', '📚 Subject Specific Grading'),
    ]
    
    # Relationships
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='grading_preferences')
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, null=True, blank=True, 
                             related_name='teacher_grading_preferences')
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='teacher_grading_preferences')
    
    # Grading choice
    grading_choice = models.CharField(
        max_length=20, 
        choices=GRADING_CHOICES, 
        default='traditional',
        help_text="Select which grading system to use"
    )
    
    # Custom grading system (used when grading_choice is 'custom')
    custom_grading_system = models.ForeignKey(
        GradingSystem, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='teacher_preferences',
        help_text="Select a custom grading system you've created"
    )
    
    # CBE pathway (used when grading_choice is 'cbe')
    cbe_pathway = models.ForeignKey(
        'CBEGradingPathway', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='teacher_preferences',
        help_text="Select a CBE pathway for competency-based grading"
    )
    
    # Subject grading config (used when grading_choice is 'subject_specific')
    subject_grading_config = models.ForeignKey(
        SubjectGradingConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='teacher_preferences',
        help_text="Select a subject-specific grading configuration"
    )
    
    # Legacy fields (keep for backward compatibility)
    use_custom_grading = models.BooleanField(default=False, help_text="Legacy field - use grading_choice instead")
    use_cbe_pathways = models.BooleanField(default=False, help_text="Legacy field - use grading_choice instead")
    
    # Preference scope
    is_global = models.BooleanField(
        default=False,
        help_text="Apply this preference to all your exams and subjects"
    )
    
    is_active = models.BooleanField(default=True, help_text="Whether this preference is currently active")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_global', '-updated_at']
        unique_together = ['teacher', 'exam', 'subject']
        indexes = [
            models.Index(fields=['teacher', 'grading_choice']),
            models.Index(fields=['teacher', 'exam', 'subject']),
            models.Index(fields=['teacher', 'is_global']),
        ]
    
    def __str__(self):
        exam_name = self.exam.name if self.exam else "All Exams"
        subject_name = self.subject.name if self.subject else "All Subjects"
        scope = " (Global)" if self.is_global else f" - {exam_name} - {subject_name}"
        return f"{self.teacher.get_full_name() or self.teacher.username} - {self.get_grading_choice_display()}{scope}"
    
    def get_grading_system(self):
        """Get the actual grading system object based on the choice"""
        if self.grading_choice == 'custom' and self.custom_grading_system:
            return self.custom_grading_system
        elif self.grading_choice == 'cbe' and self.cbe_pathway:
            return self.cbe_pathway.grading_system
        elif self.grading_choice == 'subject_specific' and self.subject_grading_config:
            return self.subject_grading_config.grading_system
        elif self.grading_choice == 'school_default':
            # Get the school's default grading system
            school = self.teacher.profile.school if hasattr(self.teacher, 'profile') else None
            if school:
                return GradingSystem.objects.filter(
                    school=school, 
                    is_default=True, 
                    is_active=True
                ).first()
            return GradingSystem.objects.filter(is_default=True, is_active=True).first()
        return None
    
    def calculate_grade(self, score, subject=None):
        """Calculate grade based on the teacher's preference"""
        from .models import Grade
        
        if self.grading_choice == 'subject_specific' and self.subject_grading_config:
            return self.subject_grading_config.calculate_grade(score)
        elif self.grading_choice == 'custom' and self.custom_grading_system:
            return self.custom_grading_system.calculate_grade(score)
        elif self.grading_choice == 'cbe' and self.cbe_pathway:
            return self.cbe_pathway.grading_system.calculate_grade(score)
        elif self.grading_choice == 'school_default':
            grading_system = self.get_grading_system()
            if grading_system:
                return grading_system.calculate_grade(score)
        
        # Default traditional grading
        grade_obj = Grade.objects.filter(
            min_score__lte=score,
            max_score__gte=score
        ).first()
        
        if grade_obj:
            return {
                'grade': grade_obj.grade,
                'points': grade_obj.points,
                'remark': grade_obj.description or 'Standard Grade',
                'is_passing': score >= 50
            }
        
        return {
            'grade': 'N/A',
            'points': 0,
            'remark': 'Not Graded',
            'is_passing': False
        }
    
    def get_display_info(self):
        """Get display information about the current grading preference"""
        info = {
            'type': self.get_grading_choice_display(),
            'icon': self.get_grading_icon(),
            'description': self.get_grading_description(),
            'system_name': None
        }
        
        if self.grading_choice == 'custom' and self.custom_grading_system:
            info['system_name'] = self.custom_grading_system.name
            info['description'] = f"Using custom grading system: {self.custom_grading_system.name}"
        elif self.grading_choice == 'cbe' and self.cbe_pathway:
            info['system_name'] = self.cbe_pathway.name
            info['description'] = f"Using CBE pathway: {self.cbe_pathway.name}"
        elif self.grading_choice == 'subject_specific' and self.subject_grading_config:
            info['system_name'] = self.subject_grading_config.grading_system.name
            info['description'] = f"Using subject-specific grading for {self.subject_grading_config.subject.name}"
        elif self.grading_choice == 'school_default':
            system = self.get_grading_system()
            if system:
                info['system_name'] = system.name
                info['description'] = f"Using school default: {system.name}"
        
        return info
    
    def get_grading_icon(self):
        """Get an icon for the grading type"""
        icons = {
            'traditional': '📊',
            'custom': '⚙️',
            'cbe': '🎯',
            'school_default': '🏫',
            'exam_specific': '📝',
            'subject_specific': '📚',
        }
        return icons.get(self.grading_choice, '📋')
    
    def get_grading_description(self):
        """Get a description of the grading type"""
        descriptions = {
            'traditional': 'Standard letter grades (A, B, C, D, E) based on percentage scores',
            'custom': 'Your own custom grading system with personalized grade boundaries',
            'cbe': 'Competency-Based Education grading with performance levels (EE, ME, AE, BE)',
            'school_default': 'The school\'s default grading system',
            'exam_specific': 'Grading system specifically for this exam type',
            'subject_specific': 'Grading system specifically for this subject',
        }
        return descriptions.get(self.grading_choice, 'Custom grading configuration')
    
    def save(self, *args, **kwargs):
        # Handle legacy fields for backward compatibility
        if self.use_custom_grading and not self.grading_choice:
            self.grading_choice = 'custom'
        elif self.use_cbe_pathways and not self.grading_choice:
            self.grading_choice = 'cbe'
        
        # If this is global, ensure no other global preference exists for this teacher
        if self.is_global:
            TeacherGradingPreference.objects.filter(
                teacher=self.teacher,
                is_global=True
            ).exclude(id=self.id).update(is_global=False)
        
        super().save(*args, **kwargs)


class CBEGradingPathway(models.Model):
    """CBE specific grading pathways"""
    
    PATHWAY_TYPES = [
        ('creative_arts', 'Creative Arts'),
        ('sports', 'Sports & Physical Education'),
        ('stem', 'Science, Technology, Engineering & Math'),
        ('humanities', 'Humanities & Social Sciences'),
        ('vocational', 'Vocational & Technical'),
        ('business', 'Business & Entrepreneurship'),
        ('languages', 'Languages & Communications'),
    ]
    
    name = models.CharField(max_length=100)
    pathway_type = models.CharField(max_length=50, choices=PATHWAY_TYPES)
    description = models.TextField(blank=True)
    subjects = models.ManyToManyField('Subject', related_name='cbe_pathways')
    grading_system = models.ForeignKey(GradingSystem, on_delete=models.CASCADE, related_name='cbe_pathways')
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.pathway_type})"


# Alias for backward compatibility
GradingScale = GradeScale
# digitallibrary/models.py

class HistoricalArrears(models.Model):
    """Track historical arrears brought forward from previous classes/years"""
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='historical_arrears')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    original_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, related_name='arrears_originated')
    original_academic_year = models.CharField(max_length=9)
    original_term = models.IntegerField(choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')])
    notes = models.TextField(blank=True, null=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_settled = models.BooleanField(default=False)
    settled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Historical Arrears"
    
    def __str__(self):
        return f"{self.student.admission_number} - KES {self.amount} from {self.original_academic_year} T{self.original_term}"
# digitallibrary/models.py - Add these models

class TVDisplay(models.Model):
    """School TV Display - One per school"""
    
    LAYOUT_CHOICES = [
        ('split', 'Split Screen (2 columns)'),
        ('grid', 'Grid Layout (4 quadrants)'),
        ('full', 'Full Screen'),
        ('sidebar', 'Main + Sidebar'),
    ]
    
    THEME_CHOICES = [
        ('dark', 'Dark Theme (Modern)'),
        ('light', 'Light Theme (Classic)'),
        ('school', 'School Colors'),
    ]
    
    # CRITICAL MULTI-TENANT ARCHITECTURE UPDATE:
    # Changed from OneToOneField('tenants.School') to IntegerField to prevent database isolation conflicts 
    # (psycopg2.errors.ForeignKeyViolation) across shared public schemas and isolated tenant schemas on Render.
    school_id = models.IntegerField(unique=True, null=True, blank=True, db_index=True)
    
    # Basic info
    name = models.CharField(max_length=100, default="School TV")
    is_active = models.BooleanField(default=True)
    
    # Display settings
    layout = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default='split')
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default='dark')
    refresh_interval = models.IntegerField(default=30, help_text="Seconds between content refresh")
    display_duration = models.IntegerField(default=10, help_text="Seconds per slide")
    
    # Content visibility
    show_clock = models.BooleanField(default=True)
    show_weather = models.BooleanField(default=True)
    show_news_ticker = models.BooleanField(default=True)
    show_events = models.BooleanField(default=True)
    show_exam_schedule = models.BooleanField(default=True)
    show_noticeboard = models.BooleanField(default=True, help_text="Show announcements from noticeboard")
    
    # Branding
    school_logo = models.ImageField(upload_to='tv_logos/', blank=True, null=True)
    background_image = models.ImageField(upload_to='tv_backgrounds/', blank=True, null=True)
    accent_color = models.CharField(max_length=7, default='#3b82f6', help_text="Primary brand color")
    background_color = models.CharField(max_length=7, default='#0f172a')
    text_color = models.CharField(max_length=7, default='#ffffff')
    
    # Footer
    footer_text = models.CharField(max_length=200, default="ShuleHub TV - Keeping You Informed")
    
    # Weather settings (optional)
    weather_location = models.CharField(max_length=100, blank=True, null=True, help_text="City name for weather (e.g., Nairobi)")
    weather_latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    weather_longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "TV Display"
        verbose_name_plural = "TV Displays"
    
    def __str__(self):
        return f"{self.name} (School ID: {self.school_id})"
    
    def get_tv_url(self, request=None):
        """Get the full TV display URL"""
        if request:
            return f"https://{request.get_host()}/app/tv/"
        return "/app/tv/"
    
    def get_embed_code(self, request=None):
        """Get embed code for iframe"""
        url = self.get_tv_url(request)
        return f'<iframe src="{url}" style="width:100%; height:100vh; border:none;"></iframe>'
    
    @property
    def has_weather_location(self):
        """Check if weather location is set"""
        return bool(self.weather_location or (self.weather_latitude and self.weather_longitude))
    
    @property
    def theme_colors(self):
        """Get theme color scheme"""
        themes = {
            'dark': {
                'bg': '#0f172a',
                'card_bg': '#1e293b',
                'text': '#ffffff',
                'accent': '#3b82f6',
                'border': '#334155'
            },
            'light': {
                'bg': '#f1f5f9',
                'card_bg': '#ffffff',
                'text': '#1e293b',
                'accent': '#2563eb',
                'border': '#cbd5e1'
            },
            'school': {
                'bg': self.background_color or '#0f172a',
                'card_bg': '#1e293b',
                'text': self.text_color or '#ffffff',
                'accent': self.accent_color or '#3b82f6',
                'border': '#334155'
            }
        }
        return themes.get(self.theme, themes['dark'])

class TVContent(models.Model):
    """Content to display on the TV"""
    
    CONTENT_TYPES = [
        ('announcement', '📢 Announcement'),
        ('event', '📅 Upcoming Event'),
        ('exam', '📝 Exam Schedule'),
        ('achievement', '🏆 Achievement'),
        ('quote', '💡 Quote of the Day'),
        ('notice', '📋 Notice Board'),
        ('reminder', '⏰ Reminder'),
        ('emergency', '🚨 Emergency Alert'),
        ('slide', '🖼️ Image Slide'),
    ]
    
    PRIORITY_CHOICES = [
        (1, '🟢 Low'),
        (2, '🔵 Normal'),
        (3, '🟡 High'),
        (4, '🟠 Urgent'),
        (5, '🔴 Critical'),
    ]
    
    tv_display = models.ForeignKey('TVDisplay', on_delete=models.CASCADE, related_name='contents')
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES, default='announcement')
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=2)
    
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, null=True, help_text="Content message (optional for image slides)")
    
    # Image/Photo Upload - This is the key field for displaying photos on TV
    image = models.ImageField(
        upload_to='tv_content/%Y/%m/%d/', 
        blank=True, 
        null=True,
        help_text="Upload image/photo (JPEG, PNG, GIF, WebP) - Max 5MB",
        verbose_name="Upload Photo/Image"
    )
    
    # Optional: Image URL for external images
    image_url = models.URLField(blank=True, null=True, help_text="External image URL (optional)")
    
    link_url = models.URLField(blank=True, null=True, help_text="Optional link for more info")
    
    # Scheduling
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Display settings
    display_duration = models.IntegerField(default=10, help_text="Seconds to display this content")
    is_featured = models.BooleanField(default=False, help_text="Show prominently in hero section")
    is_recurring = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', '-created_at']
        verbose_name = "TV Content"
        verbose_name_plural = "TV Content"
    
    def __str__(self):
        return f"{self.get_content_type_display()}: {self.title}"
    
    def is_current(self):
        """Check if content is currently active"""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date and self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True
    
    @property
    def display_image(self):
        """Get the image URL (from upload or external URL)"""
        if self.image and self.image.url:
            return self.image.url
        if self.image_url:
            return self.image_url
        return None
    
    def get_priority_color(self):
        """Get color class for priority"""
        colors = {
            1: 'text-green-400',
            2: 'text-blue-400',
            3: 'text-yellow-400',
            4: 'text-orange-400',
            5: 'text-red-400'
        }
        return colors.get(self.priority, 'text-gray-400')
    
    def get_priority_label(self):
        """Get priority label with icon"""
        labels = {
            1: '🟢 Low',
            2: '🔵 Normal',
            3: '🟡 High',
            4: '🟠 Urgent',
            5: '🔴 Critical'
        }
        return labels.get(self.priority, 'Normal')
# Add these methods to your Student model if missing

def soft_delete(self, user, reason=None, reason_type='other', transfer_to=None):
    """Soft delete a student"""
    from django.utils import timezone
    
    self.is_active = False
    self.status = 'deactivated'
    self.deleted_at = timezone.now()
    self.deleted_by = user
    self.transfer_reason = reason_type
    self.transfer_reason_other = reason or ''
    self.transfer_date = timezone.now().date()
    self.transfer_to_school = transfer_to or ''
    self.save()
    
    # Create action log
    StudentActionLog.objects.create(
        student=self,
        action='deactivated',
        performed_by=user,
        reason=reason or reason_type,
        details={'reason_type': reason_type, 'transfer_to': transfer_to}
    )

def reactivate(self, user, reason=None):
    """Reactivate a soft-deleted student"""
    from django.utils import timezone
    
    self.is_active = True
    self.status = 'active'
    self.deleted_at = None
    self.deleted_by = None
    self.transfer_reason = None
    self.transfer_reason_other = ''
    self.transfer_date = None
    self.transfer_to_school = ''
    self.save()
    
    # Create action log
    StudentActionLog.objects.create(
        student=self,
        action='reactivated',
        performed_by=user,
        reason=reason or 'Reactivated by admin'
    )
# digitallibrary/models.py

class KNECCBEGrade(models.Model):
    """KNEC CBE Grading System Model"""
    LEVEL_CHOICES = [
        ('EE1', 'Exceeding Expectations 1'),
        ('EE2', 'Exceeding Expectations 2'),
        ('ME1', 'Meeting Expectations 1'),
        ('ME2', 'Meeting Expectations 2'),
        ('AE1', 'Approaching Expectations 1'),
        ('AE2', 'Approaching Expectations 2'),
        ('BE1', 'Below Expectations 1'),
        ('BE2', 'Below Expectations 2'),
    ]
    
    PLACEMENT_CHOICES = [
        ('national', 'National School'),
        ('extra_county', 'Extra-County School'),
        ('county', 'County School'),
        ('sub_county', 'Sub-County School'),
    ]
    
    level = models.CharField(max_length=3, choices=LEVEL_CHOICES, unique=True)
    level_name = models.CharField(max_length=50)
    min_score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    points = models.DecimalField(max_digits=3, decimal_places=0)  # 1-8 points
    placement = models.CharField(max_length=20, choices=PLACEMENT_CHOICES)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)  # For sorting (1-8)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-order']
        verbose_name = "KNEC CBE Grade"
        verbose_name_plural = "KNEC CBE Grades"
    
    def __str__(self):
        return f"{self.level} - {self.level_name} ({self.min_score}-{self.max_score}%)"
    
    @classmethod
    def initialize_default_grades(cls):
        """Initialize default KNEC CBE grading system"""
        default_grades = [
            {
                'level': 'EE1',
                'level_name': 'Exceeding Expectations',
                'min_score': 90,
                'max_score': 100,
                'points': 8,
                'placement': 'national',
                'order': 1,
                'description': 'Demonstrates exceptional technical skills, originality, and initiative. Shows deep understanding and can apply knowledge in complex situations.'
            },
            {
                'level': 'EE2',
                'level_name': 'Exceeding Expectations',
                'min_score': 75,
                'max_score': 89,
                'points': 7,
                'placement': 'national',
                'order': 2,
                'description': 'Consistently performs above expected standards. Shows strong understanding with minor errors.'
            },
            {
                'level': 'ME1',
                'level_name': 'Meeting Expectations',
                'min_score': 58,
                'max_score': 74,
                'points': 6,
                'placement': 'extra_county',
                'order': 3,
                'description': 'Meets all core competencies consistently. Demonstrates good understanding of concepts.'
            },
            {
                'level': 'ME2',
                'level_name': 'Meeting Expectations',
                'min_score': 41,
                'max_score': 57,
                'points': 5,
                'placement': 'extra_county',
                'order': 4,
                'description': 'Meets most core competencies. Shows satisfactory understanding with some support.'
            },
            {
                'level': 'AE1',
                'level_name': 'Approaching Expectations',
                'min_score': 31,
                'max_score': 40,
                'points': 4,
                'placement': 'county',
                'order': 5,
                'description': 'Approaching expected standards. Shows partial understanding with guidance.'
            },
            {
                'level': 'AE2',
                'level_name': 'Approaching Expectations',
                'min_score': 21,
                'max_score': 30,
                'points': 3,
                'placement': 'county',
                'order': 6,
                'description': 'Making progress toward expectations. Requires additional support.'
            },
            {
                'level': 'BE1',
                'level_name': 'Below Expectations',
                'min_score': 11,
                'max_score': 20,
                'points': 2,
                'placement': 'sub_county',
                'order': 7,
                'description': 'Below expected standards. Significant improvement needed with intervention.'
            },
            {
                'level': 'BE2',
                'level_name': 'Below Expectations',
                'min_score': 0,
                'max_score': 10,
                'points': 1,
                'placement': 'sub_county',
                'order': 8,
                'description': 'Far below expected standards. Intensive remediation required.'
            },
        ]
        
        for grade_data in default_grades:
            cls.objects.update_or_create(
                level=grade_data['level'],
                defaults=grade_data
            )


class StudentResult(models.Model):
    """Student Results with CBE grading"""
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='results')
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, related_name='results')
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grade = models.ForeignKey(KNECCBEGrade, on_delete=models.SET_NULL, null=True, blank=True)
    points = models.DecimalField(max_digits=3, decimal_places=0, null=True, blank=True)
    remarks = models.TextField(blank=True)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    entered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'exam', 'subject']
        ordering = ['-exam__created_at']
    
    def save(self, *args, **kwargs):
        # Auto-calculate grade based on score
        if self.score is not None:
            cbe_grade = KNECCBEGrade.objects.filter(
                min_score__lte=self.score,
                max_score__gte=self.score,
                is_active=True
            ).first()
            if cbe_grade:
                self.grade = cbe_grade
                self.points = cbe_grade.points
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.student} - {self.exam} - {self.subject}: {self.get_grade_display()}"
    
    def get_grade_display(self):
        if self.grade:
            return f"{self.grade.level} ({self.grade.level_name})"
        return "Not graded"
