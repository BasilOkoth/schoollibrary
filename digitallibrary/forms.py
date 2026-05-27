# digitallibrary/forms.py

import os
import random
from datetime import datetime
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
    Announcement,
    Category,
    Class,
    FeePayment,
    FeeStructure,
    Resource,
    Student,
    Subject,
    Exam,
    Feedback,
    FeeComponent,
    StudentResult,
    PerformanceSummary,
    Grade,
    PaperSet,
    PaperResource,
    UserProfile,
    SchoolSetting,
    PrintJob,
    ActivityLog,
    SMSLog,
    TeacherSubject,
    GradingSystem,
    GradeScale,
    TeacherGradingPreference,
    TVDisplay,
    TVContent,
    CBEGradingPathway,
    SubjectGradingConfig,
    FeeBalance,
    HistoricalArrears,
)

# Import tenants models
from tenants.models import School, Domain

# ========== CSS CLASSES ==========

TEXT_INPUT_CLASSES = (
    "w-full rounded-xl border border-slate-700 bg-slate-950/90 "
    "px-3 py-2.5 text-sm font-semibold text-slate-100 "
    "placeholder-slate-500 outline-none transition "
    "focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
)

SELECT_CLASSES = (
    "w-full rounded-xl border border-slate-700 bg-slate-950/90 "
    "px-3 py-2.5 pr-10 text-sm font-semibold text-slate-100 "
    "outline-none transition appearance-none cursor-pointer "
    "focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
)

TEXTAREA_CLASSES = (
    "w-full rounded-xl border border-slate-700 bg-slate-950/90 "
    "px-3 py-2.5 text-sm font-semibold text-slate-100 "
    "placeholder-slate-500 outline-none transition "
    "focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
)

FILE_INPUT_CLASSES = (
    "w-full rounded-xl border border-slate-700 bg-slate-950/90 "
    "px-3 py-2 text-sm text-slate-300 "
    "file:mr-3 file:rounded-lg file:border-0 "
    "file:bg-emerald-500/15 file:px-3 file:py-2 "
    "file:text-xs file:font-bold file:text-emerald-300 "
    "hover:file:bg-emerald-500/20"
)

CHECKBOX_CLASSES = (
    "h-4 w-4 rounded border-slate-600 bg-slate-900 "
    "text-emerald-500 focus:ring-emerald-500/30"
)


def apply_dark_widget_classes(form: forms.Form) -> None:
    """Apply dark theme classes to all form widgets"""
    for field in form.fields.values():
        widget = field.widget
        existing = widget.attrs.get("class", "")

        if isinstance(widget, forms.Select):
            widget.attrs["class"] = f"{existing} {SELECT_CLASSES}".strip()
        elif isinstance(widget, forms.Textarea):
            widget.attrs["class"] = f"{existing} {TEXTAREA_CLASSES}".strip()
        elif isinstance(widget, forms.CheckboxInput):
            widget.attrs["class"] = f"{existing} {CHECKBOX_CLASSES}".strip()
        elif isinstance(widget, (forms.ClearableFileInput, forms.FileInput)):
            widget.attrs["class"] = f"{existing} {FILE_INPUT_CLASSES}".strip()
        else:
            widget.attrs["class"] = f"{existing} {TEXT_INPUT_CLASSES}".strip()


# ========== AUTHENTICATION FORMS ==========

class LoginForm(AuthenticationForm):
    """Custom login form with dark styling"""
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "class": TEXT_INPUT_CLASSES,
                "placeholder": "Username",
                "autocomplete": "username",
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": TEXT_INPUT_CLASSES,
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        )
    )


# ========== RESOURCE FORMS ==========

class ResourceFilterForm(forms.Form):
    """Form for filtering resources in the library"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': TEXT_INPUT_CLASSES,
            'placeholder': 'Search by title, author, or description...',
            'id': 'searchInput'
        })
    )
    
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(is_active=True),
        required=False,
        empty_label="All Subjects",
        widget=forms.Select(attrs={
            'class': SELECT_CLASSES,
            'id': 'subjectFilter'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={
            'class': SELECT_CLASSES,
            'id': 'categoryFilter'
        })
    )
    
    grade = forms.ChoiceField(
        choices=[('', 'All Grades')],
        required=False,
        widget=forms.Select(attrs={
            'class': SELECT_CLASSES,
            'id': 'gradeFilter'
        })
    )
    
    year = forms.ChoiceField(
        choices=[('', 'All Years')],
        required=False,
        widget=forms.Select(attrs={
            'class': SELECT_CLASSES,
            'id': 'yearFilter'
        })
    )
    
    resource_type = forms.ChoiceField(
        choices=[('', 'All Types'), ('PDF', 'PDF'), ('DOC', 'Word'), ('VIDEO', 'Video'), ('OTHER', 'Other')],
        required=False,
        widget=forms.Select(attrs={
            'class': SELECT_CLASSES,
            'id': 'typeFilter'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate grade choices
        grades = Resource.objects.exclude(grade__isnull=True).exclude(grade='').values_list('grade', flat=True).distinct()
        self.fields['grade'].choices = [('', 'All Grades')] + [(g, g) for g in grades if g]
        
        # Populate year choices
        years = Resource.objects.exclude(year__isnull=True).exclude(year='').exclude(year='N/A').values_list('year', flat=True).distinct().order_by('-year')
        self.fields['year'].choices = [('', 'All Years')] + [(y, y) for y in years if y]
        
        apply_dark_widget_classes(self)


class ResourceForm(forms.ModelForm):
    """Form for creating and editing resources"""
    
    class Meta:
        model = Resource
        fields = [
            "title",
            "author",
            "description",
            "grade",
            "year",
            "subject",
            "category",
            "paper_type",
            "resource_type",
            "cover_image",
            "file",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Enter resource title"}),
            "author": forms.TextInput(attrs={"placeholder": "Enter author name"}),
            "description": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Enter resource description"}
            ),
            "grade": forms.Select(),
            "year": forms.Select(),
            "subject": forms.Select(),
            "category": forms.Select(),
            "paper_type": forms.Select(),
            "resource_type": forms.Select(),
            "cover_image": forms.ClearableFileInput(),
            "file": forms.ClearableFileInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["subject"].queryset = Subject.objects.all().order_by("name")
        self.fields["subject"].empty_label = "--- Select Subject ---"
        self.fields["subject"].required = False
        self.fields["subject"].label = "Subject"

        self.fields["category"].queryset = Category.objects.all().order_by("name")
        self.fields["category"].empty_label = "--- Select Category ---"
        self.fields["category"].required = False
        self.fields["category"].label = "Category"

        current_year = timezone.now().year
        year_choices = [("", "Select Year")]
        for year in range(current_year + 5, 1949, -1):
            year_choices.append((str(year), str(year)))
        year_choices.append(("N/A", "N/A (No specific year)"))

        self.fields["year"].widget = forms.Select(choices=year_choices)
        self.fields["year"].required = False

        self.fields["paper_type"].widget = forms.Select(
            choices=[
                ("", "Select Paper Type"),
                ("Paper 1", "Paper 1"),
                ("Paper 2", "Paper 2"),
                ("Paper 3", "Paper 3"),
                ("Practical", "Practical"),
                ("Marking Scheme", "Marking Scheme"),
                ("Revision", "Revision"),
                ("Notes", "Notes"),
                ("N/A", "General Resource"),
            ]
        )

        self.fields["resource_type"].widget = forms.Select(
            choices=[
                ("", "Select Resource Type"),
                ("PDF", "PDF"),
                ("DOC", "Word Document"),
                ("VIDEO", "Video"),
                ("OTHER", "Other"),
            ]
        )

        if self.instance and self.instance.pk:
            self.fields["file"].required = False
            self.fields["cover_image"].required = False

        apply_dark_widget_classes(self)


# ========== FEE STRUCTURE FORM ==========

class FeeStructureForm(forms.ModelForm):
    """Simplified form that only uses fields that exist in the model"""
    
    class Meta:
        model = FeeStructure
        fields = ['academic_year', 'term', 'student_class', 'deadline', 'late_fee_penalty']
        widgets = {
            'academic_year': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-green-500',
                'placeholder': 'e.g., 2024-2025'
            }),
            'term': forms.Select(attrs={
                'class': 'w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-green-500'
            }),
            'student_class': forms.Select(attrs={
                'class': 'w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-green-500'
            }),
            'deadline': forms.DateInput(attrs={
                'type': 'date',
                'class': TEXT_INPUT_CLASSES
            }),
            'late_fee_penalty': forms.NumberInput(attrs={
                'class': TEXT_INPUT_CLASSES,
                'placeholder': 'e.g., 5.00',
                'step': '0.01'
            }),
        }


# ========== ANNOUNCEMENT FORMS ==========

class AnnouncementForm(forms.ModelForm):
    """Form for creating and editing announcements"""
    
    expiry_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    expiry_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
    )

    class Meta:
        model = Announcement
        fields = [
            "title",
            "content",
            "target_audience",
            "is_featured",
            "attachment",
            "expires_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Enter announcement title"}),
            "content": forms.Textarea(attrs={"rows": 6}),
            "target_audience": forms.Select(),
            "is_featured": forms.CheckboxInput(),
            "attachment": forms.ClearableFileInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.expires_at:
            self.initial["expiry_date"] = self.instance.expires_at.date()
            self.initial["expiry_time"] = self.instance.expires_at.time()

        apply_dark_widget_classes(self)


class AnnouncementFilterForm(forms.Form):
    """Form for filtering announcements"""
    
    AUDIENCE_FILTER_CHOICES = [
        ("", "All Audiences"),
        ("all", "Everyone"),
        ("teachers", "Teachers Only"),
        ("students", "Students Only"),
        ("admin", "Administrators Only"),
        ("staff", "Staff Only"),
    ]

    STATUS_FILTER_CHOICES = [
        ("", "All Status"),
        ("active", "Active Only"),
        ("expired", "Expired Only"),
        ("featured", "Featured Only"),
    ]

    audience = forms.ChoiceField(
        choices=AUDIENCE_FILTER_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASSES}),
    )
    status = forms.ChoiceField(
        choices=STATUS_FILTER_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASSES}),
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Search announcements...",
            "autocomplete": "off",
            "class": TEXT_INPUT_CLASSES,
        }),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": TEXT_INPUT_CLASSES}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": TEXT_INPUT_CLASSES}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


class BulkAnnouncementForm(forms.Form):
    """Form for bulk creating announcements"""
    
    titles = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 5,
            "placeholder": "Enter one title per line...",
            "class": TEXTAREA_CLASSES,
        }),
        help_text="Enter each announcement title on a new line",
    )
    content_template = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 5,
            "placeholder": "Enter template content. Use {title} as placeholder...",
            "class": TEXTAREA_CLASSES,
        }),
        help_text="Content template. Use {title} to insert the title",
    )
    target_audience = forms.ChoiceField(
        choices=Announcement.AUDIENCE_CHOICES,
        widget=forms.Select(attrs={'class': SELECT_CLASSES}),
    )
    is_featured = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
    )
    attachment = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': FILE_INPUT_CLASSES}),
    )
    expires_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": TEXT_INPUT_CLASSES}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


# ========== STUDENT FORMS ==========

class StudentForm(forms.ModelForm):
    """
    Form for creating and editing students with CBC curriculum subjects.
    Handles class assignment, pathway selection, and subject management.
    """
    
    new_class = forms.CharField(
        required=False,
        label="Add New Class",
        help_text="Type a class name here if it is not in the dropdown.",
        widget=forms.TextInput(attrs={
            "placeholder": "Example: Grade 10",
            "class": TEXT_INPUT_CLASSES
        })
    )
    
    class Meta:
        model = Student
        fields = [
            "admission_number",
            "upi_number",
            "first_name",
            "last_name",
            "middle_name",
            "gender",
            "current_class",
            "admission_year",
            "parent_name",
            "parent_phone",
            "parent_alternative_phone",
            "parent_email",
            "physical_address",
            "is_active",
        ]
        widgets = {
            "admission_number": forms.TextInput(attrs={"placeholder": "Admission number", "class": TEXT_INPUT_CLASSES}),
            "upi_number": forms.TextInput(attrs={"placeholder": "UPI number", "class": TEXT_INPUT_CLASSES}),
            "first_name": forms.TextInput(attrs={"placeholder": "First name", "class": TEXT_INPUT_CLASSES}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name", "class": TEXT_INPUT_CLASSES}),
            "middle_name": forms.TextInput(attrs={"placeholder": "Middle name (optional)", "class": TEXT_INPUT_CLASSES}),
            "gender": forms.Select(attrs={"class": SELECT_CLASSES}),
            "current_class": forms.Select(attrs={"class": SELECT_CLASSES}),
            "admission_year": forms.NumberInput(attrs={"min": 2000, "max": 2035, "placeholder": "e.g., 2024", "class": TEXT_INPUT_CLASSES}),
            "parent_name": forms.TextInput(attrs={"placeholder": "Parent / guardian full name", "class": TEXT_INPUT_CLASSES}),
            "parent_phone": forms.TextInput(attrs={"placeholder": "e.g., 0712345678 or +254712345678", "class": TEXT_INPUT_CLASSES}),
            "parent_alternative_phone": forms.TextInput(attrs={"placeholder": "Alternative phone number", "class": TEXT_INPUT_CLASSES}),
            "parent_email": forms.EmailInput(attrs={"placeholder": "parent@example.com", "class": TEXT_INPUT_CLASSES}),
            "physical_address": forms.Textarea(attrs={"rows": 2, "placeholder": "Student's home address", "class": TEXTAREA_CLASSES}),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["admission_year"].initial = timezone.now().year

        self.fields["current_class"].queryset = Class.objects.all().order_by("name")
        self.fields["current_class"].empty_label = "--- Select a class ---"
        self.fields["current_class"].required = False

        self.fields["gender"].required = False
        self.fields["gender"].initial = "N"
        
        self.fields["parent_phone"].help_text = "Enter Kenyan phone number (e.g., 0712345678 or +254712345678)"
        self.fields["parent_alternative_phone"].help_text = "Optional secondary contact number"
        
        if self.instance.pk and self.instance.parent_phone:
            self.fields["parent_phone"].initial = self.instance.parent_phone

        apply_dark_widget_classes(self)

    def clean_admission_number(self):
        admission = self.cleaned_data.get("admission_number")
        if admission:
            instance = getattr(self, "instance", None)
            if instance and instance.pk:
                if Student.objects.filter(admission_number=admission).exclude(pk=instance.pk).exists():
                    raise forms.ValidationError("A student with this admission number already exists.")
            else:
                if Student.objects.filter(admission_number=admission).exists():
                    raise forms.ValidationError("A student with this admission number already exists.")
        return admission


class StudentSearchForm(forms.Form):
    """Form for searching students"""
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Search by name, admission number...", "class": TEXT_INPUT_CLASSES})
    )
    class_filter = forms.ModelChoiceField(queryset=Class.objects.all().order_by("name"), required=False, empty_label="All Classes", widget=forms.Select(attrs={"class": SELECT_CLASSES}))
    gender_filter = forms.ChoiceField(choices=[("", "All"), ("M", "Male"), ("F", "Female"), ("O", "Other")], required=False, widget=forms.Select(attrs={"class": SELECT_CLASSES}))
    status_filter = forms.ChoiceField(choices=[("", "All"), ("active", "Active"), ("inactive", "Inactive")], required=False, widget=forms.Select(attrs={"class": SELECT_CLASSES}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


class BulkStudentUploadForm(forms.Form):
    """Form for bulk uploading students via Excel/CSV"""
    
    excel_file = forms.FileField(
        label='Excel/CSV File',
        help_text='Upload an Excel (.xlsx, .xls) or CSV file with student data',
        widget=forms.ClearableFileInput(attrs={
            'class': FILE_INPUT_CLASSES, 
            'accept': '.xlsx,.xls,.csv'
        })
    )
    
    def clean_excel_file(self):
        file = self.cleaned_data['excel_file']
        ext = file.name.split('.')[-1].lower()
        if ext not in ['xlsx', 'xls', 'csv']:
            raise forms.ValidationError('Please upload an Excel (.xlsx, .xls) or CSV file')
        if file.size > 5 * 1024 * 1024:
            raise forms.ValidationError('File size must be less than 5MB')
        return file


# ========== FEE COMPONENT FORMS ==========

class FeeComponentForm(forms.ModelForm):
    class Meta:
        model = FeeComponent
        fields = ['name', 'amount', 'is_optional', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g., Tuition Fee', 'class': TEXT_INPUT_CLASSES}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00', 'class': TEXT_INPUT_CLASSES}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': TEXTAREA_CLASSES}),
            'is_optional': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


class FeePaymentForm(forms.ModelForm):
    class Meta:
        model = FeePayment
        fields = ['student', 'amount', 'payment_method', 'transaction_id', 'term', 'academic_year', 'remarks']
        widgets = {
            'student': forms.HiddenInput(),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': TEXT_INPUT_CLASSES}),
            'payment_method': forms.Select(attrs={'class': SELECT_CLASSES}),
            'transaction_id': forms.TextInput(attrs={'placeholder': 'MPESA/Bank Reference', 'class': TEXT_INPUT_CLASSES}),
            'term': forms.Select(attrs={'class': SELECT_CLASSES}),
            'academic_year': forms.Select(attrs={'class': SELECT_CLASSES}),
            'remarks': forms.Textarea(attrs={'rows': 2, 'class': TEXTAREA_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        year_choices = [(current_year, str(current_year)), (current_year + 1, str(current_year + 1))]
        self.fields['academic_year'].widget = forms.Select(choices=year_choices, attrs={'class': SELECT_CLASSES})
        if not self.instance.pk:
            self.fields['academic_year'].initial = current_year
        apply_dark_widget_classes(self)


class FeeBalanceFilterForm(forms.Form):
    academic_year = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': SELECT_CLASSES}))
    term = forms.ChoiceField(choices=[("", "All"), (1, "Term 1"), (2, "Term 2"), (3, "Term 3")], required=False, widget=forms.Select(attrs={'class': SELECT_CLASSES}))
    status = forms.ChoiceField(choices=[("", "All"), ("PAID", "Paid"), ("PARTIAL", "Partial"), ("DEFAULTING", "Defaulting")], required=False, widget=forms.Select(attrs={'class': SELECT_CLASSES}))
    student_class = forms.ModelChoiceField(queryset=Class.objects.all().order_by("name"), required=False, empty_label="All Classes", widget=forms.Select(attrs={'class': SELECT_CLASSES}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        self.fields['academic_year'].widget = forms.Select(choices=[("", "All"), (current_year, current_year), (current_year - 1, current_year - 1)], attrs={'class': SELECT_CLASSES})
        apply_dark_widget_classes(self)


# ========== FEEDBACK FORM ==========

class FeedbackForm(forms.ModelForm):
    rating = forms.ChoiceField(
        choices=[
            ('', 'Select rating'),
            (1, '⭐ - Poor'),
            (2, '⭐⭐ - Fair'),
            (3, '⭐⭐⭐ - Good'),
            (4, '⭐⭐⭐⭐ - Very Good'),
            (5, '⭐⭐⭐⭐⭐ - Excellent'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'star-rating-input'}),
        required=False,
        label='Rate Your Experience'
    )
    
    class Meta:
        model = Feedback
        fields = ['feedback_type', 'priority', 'subject', 'message', 'rating', 'screenshot']
        widgets = {
            'feedback_type': forms.Select(attrs={'class': SELECT_CLASSES}),
            'priority': forms.Select(attrs={'class': SELECT_CLASSES}),
            'subject': forms.TextInput(attrs={'class': TEXT_INPUT_CLASSES, 'placeholder': 'Brief summary of your feedback...'}),
            'message': forms.Textarea(attrs={'rows': 4, 'class': TEXTAREA_CLASSES, 'placeholder': 'Please provide detailed information...'}),
            'screenshot': forms.ClearableFileInput(attrs={'class': FILE_INPUT_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)
        
        self.fields['feedback_type'].choices = [
            ('bug', '🐛 Bug Report - Something isn\'t working'),
            ('feature', '💡 Feature Request - I have an idea'),
            ('improvement', '📈 Improvement - Make something better'),
            ('general', '💬 General Feedback - Just sharing thoughts'),
            ('issue', '🚨 System Issue - Critical problem'),
        ]
        
        self.fields['priority'].choices = [
            ('low', '🟢 Low - Not urgent'),
            ('medium', '🟡 Medium - Normal priority'),
            ('high', '🟠 High - Important'),
            ('urgent', '🔴 Urgent - Critical issue'),
        ]


# ========== GRADE FORMS ==========

class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ['grade', 'min_score', 'max_score', 'points', 'description']
        widgets = {
            'grade': forms.TextInput(attrs={'class': TEXT_INPUT_CLASSES}),
            'min_score': forms.NumberInput(attrs={'class': TEXT_INPUT_CLASSES}),
            'max_score': forms.NumberInput(attrs={'class': TEXT_INPUT_CLASSES}),
            'points': forms.NumberInput(attrs={'class': TEXT_INPUT_CLASSES}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': TEXTAREA_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


# ========== EXAM FORMS ==========

class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'exam_type', 'term', 'academic_year', 'student_class', 'max_score', 'exam_date', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': TEXT_INPUT_CLASSES}),
            'exam_type': forms.Select(attrs={'class': SELECT_CLASSES}),
            'term': forms.Select(attrs={'class': SELECT_CLASSES}),
            'academic_year': forms.TextInput(attrs={'class': TEXT_INPUT_CLASSES}),
            'student_class': forms.Select(attrs={'class': SELECT_CLASSES}),
            'max_score': forms.NumberInput(attrs={'class': TEXT_INPUT_CLASSES}),
            'exam_date': forms.DateInput(attrs={'type': 'date', 'class': TEXT_INPUT_CLASSES}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': TEXTAREA_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student_class'].queryset = Class.objects.all().order_by('name')
        self.fields['student_class'].required = False
        if not self.instance.pk:
            self.fields['academic_year'].initial = str(timezone.now().year)
        apply_dark_widget_classes(self)


# ========== RESULTS ENTRY FORMS ==========

class StudentResultForm(forms.ModelForm):
    class Meta:
        model = StudentResult
        fields = ['student', 'exam', 'subject', 'score', 'remarks']
        widgets = {
            'student': forms.Select(attrs={'class': SELECT_CLASSES}),
            'exam': forms.Select(attrs={'class': SELECT_CLASSES}),
            'subject': forms.Select(attrs={'class': SELECT_CLASSES}),
            'score': forms.NumberInput(attrs={'class': TEXT_INPUT_CLASSES, 'step': '0.01'}),
            'remarks': forms.Textarea(attrs={'rows': 2, 'class': TEXTAREA_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.filter(is_active=True)
        self.fields['subject'].queryset = Subject.objects.filter(is_active=True)
        apply_dark_widget_classes(self)


class BulkResultForm(forms.Form):
    """Form for bulk result entry selection"""
    
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.filter(is_active=True), 
        widget=forms.Select(attrs={'class': SELECT_CLASSES})
    )
    student_class = forms.ModelChoiceField(
        queryset=Class.objects.all(), 
        required=False, 
        widget=forms.Select(attrs={'class': SELECT_CLASSES})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


class ExcelResultsUploadForm(forms.Form):
    """Form for uploading results via Excel"""
    
    excel_file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': FILE_INPUT_CLASSES, 
            'accept': '.xlsx,.xls,.csv'
        })
    )
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.filter(is_active=True), 
        widget=forms.Select(attrs={'class': SELECT_CLASSES})
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(is_active=True), 
        widget=forms.Select(attrs={'class': SELECT_CLASSES})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


class ResultEntryForm(forms.Form):
    """Form for entering student results with grading system selection"""
    
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': SELECT_CLASSES}),
        label="Select Exam"
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': SELECT_CLASSES}),
        label="Select Subject"
    )
    
    grading_system = forms.ModelChoiceField(
        queryset=GradingSystem.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASSES, 'id': 'grading_system'}),
        label="Grading System (Optional)"
    )
    
    use_teacher_preference = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES, 'id': 'use_preference'}),
        label="Use my saved grading preference"
    )
    
    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)
        
        if teacher and hasattr(teacher, 'profile') and teacher.profile.school:
            school = teacher.profile.school
            self.fields['grading_system'].queryset = GradingSystem.objects.filter(
                forms.models.Q(school=school) | forms.models.Q(school__isnull=True),
                is_active=True
            )
        
        apply_dark_widget_classes(self)


class ResultGridForm(forms.Form):
    """Form for the results entry grid"""
    
    def __init__(self, students, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for student in students:
            self.fields[f'score_{student.id}'] = forms.DecimalField(
                required=False,
                max_digits=5,
                decimal_places=2,
                min_value=0,
                max_value=100,
                widget=forms.NumberInput(attrs={
                    'class': 'score-input w-24 rounded border border-gray-700 bg-gray-900 px-2 py-1 text-white text-center',
                    'step': '0.01',
                    'min': '0',
                    'max': '100',
                    'data-student-id': student.id,
                    'data-student-name': f"{student.first_name} {student.last_name}"
                })
            )


# ========== PAPER SET FORMS ==========

class PaperResourceForm(forms.ModelForm):
    """Form for paper resources"""
    
    class Meta:
        model = PaperResource
        fields = ['paper_set', 'kind', 'file', 'title']
        widgets = {
            'paper_set': forms.Select(attrs={'class': SELECT_CLASSES}),
            'kind': forms.Select(attrs={'class': SELECT_CLASSES}),
            'file': forms.ClearableFileInput(attrs={'class': FILE_INPUT_CLASSES}),
            'title': forms.TextInput(attrs={'class': TEXT_INPUT_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


class PaperSetFilterForm(forms.Form):
    """Form for filtering paper sets"""
    
    grade = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': SELECT_CLASSES}))
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(is_active=True), 
        required=False, 
        empty_label="All Subjects", 
        widget=forms.Select(attrs={'class': SELECT_CLASSES})
    )
    year = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': SELECT_CLASSES}))
    paper_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(PaperSet.PAPER_TYPES), 
        required=False, 
        widget=forms.Select(attrs={'class': SELECT_CLASSES})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        grades = PaperSet.objects.values_list('grade', flat=True).distinct().order_by('grade')
        self.fields['grade'].choices = [('', 'All Grades')] + [(g, g) for g in grades if g]
        years = PaperSet.objects.values_list('year', flat=True).distinct().order_by('-year')
        self.fields['year'].choices = [('', 'All Years')] + [(y, y) for y in years if y]
        apply_dark_widget_classes(self)


# ========== PARENT PORTAL FORMS ==========

class ParentLoginForm(forms.Form):
    phone = forms.CharField(
        label="Phone Number",
        max_length=20,
        widget=forms.TextInput(attrs={
            "placeholder": "Enter parent phone number e.g. 0712345678",
            "class": TEXT_INPUT_CLASSES
        })
    )

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip().replace(" ", "")
        if phone.startswith("+254"):
            phone = "0" + phone[4:]
        elif phone.startswith("254"):
            phone = "0" + phone[3:]
        if not phone.startswith("0") or len(phone) < 10:
            raise ValidationError("Enter a valid Kenyan phone number.")
        return phone


class ParentOTPForm(forms.Form):
    otp_code = forms.CharField(
        label="OTP Code",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            "placeholder": "Enter 6-digit OTP",
            "class": TEXT_INPUT_CLASSES
        })
    )


# ========== GRADING SYSTEM FORMS ==========

class GradingSystemForm(forms.ModelForm):
    """Form for creating/editing grading systems"""
    
    class Meta:
        model = GradingSystem
        fields = ['name', 'description', 'system_type', 'subject', 'is_active', 'is_default', 'is_subject_specific']
        widgets = {
            'name': forms.TextInput(attrs={'class': TEXT_INPUT_CLASSES}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': TEXTAREA_CLASSES}),
            'system_type': forms.Select(attrs={'class': SELECT_CLASSES}),
            'subject': forms.Select(attrs={'class': SELECT_CLASSES}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
            'is_default': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
            'is_subject_specific': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subject'].queryset = Subject.objects.filter(is_active=True).order_by('name')
        self.fields['subject'].required = False
        self.fields['subject'].empty_label = "--- All Subjects ---"
        apply_dark_widget_classes(self)


class GradeScaleForm(forms.ModelForm):
    """Form for creating/editing grade scales"""
    
    class Meta:
        model = GradeScale
        fields = ['grade', 'custom_grade', 'min_score', 'max_score', 'points', 'remark', 'color_code', 'sort_order']
        widgets = {
            'grade': forms.Select(attrs={'class': SELECT_CLASSES}),
            'custom_grade': forms.TextInput(attrs={'class': TEXT_INPUT_CLASSES}),
            'min_score': forms.NumberInput(attrs={'class': TEXT_INPUT_CLASSES, 'step': '0.01'}),
            'max_score': forms.NumberInput(attrs={'class': TEXT_INPUT_CLASSES, 'step': '0.01'}),
            'points': forms.NumberInput(attrs={'class': TEXT_INPUT_CLASSES, 'step': '0.01'}),
            'remark': forms.TextInput(attrs={'class': TEXT_INPUT_CLASSES}),
            'color_code': forms.TextInput(attrs={'class': TEXT_INPUT_CLASSES, 'type': 'color'}),
            'sort_order': forms.NumberInput(attrs={'class': TEXT_INPUT_CLASSES}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


class GradingPreferenceForm(forms.ModelForm):
    """Form for teachers to set their grading preferences"""
    
    class Meta:
        model = TeacherGradingPreference
        fields = ['grading_choice', 'custom_grading_system', 'cbe_pathway', 'is_global']
        widgets = {
            'grading_choice': forms.Select(attrs={'class': SELECT_CLASSES, 'id': 'grading-choice'}),
            'custom_grading_system': forms.Select(attrs={'class': SELECT_CLASSES, 'id': 'custom-system'}),
            'cbe_pathway': forms.Select(attrs={'class': SELECT_CLASSES, 'id': 'cbe-pathway'}),
            'is_global': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
        }
    
    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        exam = kwargs.pop('exam', None)
        subject = kwargs.pop('subject', None)
        super().__init__(*args, **kwargs)
        self.fields['custom_grading_system'].queryset = GradingSystem.objects.filter(is_active=True)
        self.fields['cbe_pathway'].queryset = CBEGradingPathway.objects.filter(is_active=True)
        apply_dark_widget_classes(self)


class TeacherGradingPreferenceForm(forms.ModelForm):
    """Form for teachers to set their grading preferences with subject-specific options"""
    
    class Meta:
        model = TeacherGradingPreference
        fields = ['grading_choice', 'custom_grading_system', 'cbe_pathway', 'subject_grading_config', 'is_global']
        widgets = {
            'grading_choice': forms.Select(attrs={'class': SELECT_CLASSES, 'id': 'grading-choice'}),
            'custom_grading_system': forms.Select(attrs={'class': SELECT_CLASSES, 'id': 'custom-system'}),
            'cbe_pathway': forms.Select(attrs={'class': SELECT_CLASSES, 'id': 'cbe-pathway'}),
            'subject_grading_config': forms.Select(attrs={'class': SELECT_CLASSES, 'id': 'subject-config'}),
            'is_global': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
        }
    
    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        exam = kwargs.pop('exam', None)
        subject = kwargs.pop('subject', None)
        super().__init__(*args, **kwargs)
        self.fields['custom_grading_system'].queryset = GradingSystem.objects.filter(is_active=True)
        self.fields['cbe_pathway'].queryset = CBEGradingPathway.objects.filter(is_active=True)
        if subject:
            self.fields['subject_grading_config'].queryset = SubjectGradingConfig.objects.filter(subject=subject, is_active=True)
        else:
            self.fields['subject_grading_config'].queryset = SubjectGradingConfig.objects.filter(is_active=True)
        self.fields['subject_grading_config'].required = False
        self.fields['subject_grading_config'].empty_label = "-- No subject-specific config --"
        apply_dark_widget_classes(self)


# ========== TV DISPLAY FORMS ==========

class TVContentForm(forms.ModelForm):
    """Form for adding/editing TV content"""
    
    class Meta:
        model = TVContent
        fields = ['content_type', 'title', 'message', 'image', 'priority', 
                  'start_date', 'end_date', 'display_duration', 'is_featured', 'is_active']
        widgets = {
            'content_type': forms.Select(attrs={'class': SELECT_CLASSES}),
            'title': forms.TextInput(attrs={'class': TEXT_INPUT_CLASSES, 'placeholder': 'Enter title'}),
            'message': forms.Textarea(attrs={'rows': 4, 'class': TEXTAREA_CLASSES, 'placeholder': 'Enter message'}),
            'image': forms.ClearableFileInput(attrs={'class': FILE_INPUT_CLASSES}),
            'priority': forms.Select(attrs={'class': SELECT_CLASSES}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': TEXT_INPUT_CLASSES}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': TEXT_INPUT_CLASSES}),
            'display_duration': forms.NumberInput(attrs={'class': TEXT_INPUT_CLASSES, 'min': 5, 'max': 60}),
            'is_featured': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['start_date'].initial = timezone.now()
            self.fields['display_duration'].initial = 10
        apply_dark_widget_classes(self)


# ========== TENANT FORMS ==========

class TenantCreationForm(forms.Form):
    school_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Kandaria High School'
        })
    )
    
    schema_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., kandaria (no spaces)'
        }),
        help_text="Lowercase, no spaces or special characters"
    )
    
    domain = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., kandaria.shulehub.org'
        }),
        help_text="Full domain where school will be accessed"
    )
    
    principal_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'principal@kandaria.ac.ke'
        })
    )
    
    administrator_email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'admin@kandaria.ac.ke'
        })
    )


class DomainUpdateForm(forms.ModelForm):
    """Form for updating domain"""
    class Meta:
        model = Domain
        fields = ['domain', 'is_primary']
        widgets = {
            'domain': forms.TextInput(attrs={'class': 'form-control'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ResetPasswordForm(forms.Form):
    """Form for resetting tenant admin password"""
    username = forms.ChoiceField(choices=[], widget=forms.Select(attrs={'class': 'form-control'}))
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=8,
        help_text="Minimum 8 characters"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        users = kwargs.pop('users', [])
        super().__init__(*args, **kwargs)
        self.fields['username'].choices = [(u.username, f"{u.username} ({u.email})") for u in users]
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        
        return cleaned_data


class HistoricalArrearsForm(forms.Form):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), label="Select Student")
    amount = forms.DecimalField(max_digits=10, decimal_places=2, label="Arrears Amount (KES)")
    from_class = forms.ModelChoiceField(queryset=Class.objects.all(), required=False, label="From Class")
    from_academic_year = forms.CharField(max_length=9, required=False, label="From Academic Year (e.g., 2023-2024)")
    term = forms.ChoiceField(choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')], label="Term")
    notes = forms.CharField(widget=forms.Textarea, required=False, label="Notes")
# ========== BULK RESULT FORM ==========

class BulkResultForm(forms.Form):
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.all(),
        empty_label="Select Exam",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    student_class = forms.ModelChoiceField(
        queryset=Class.objects.all(),
        empty_label="Select Class",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['exam'].queryset = Exam.objects.all().order_by('-academic_year', '-created_at')
        self.fields['student_class'].queryset = Class.objects.all().order_by('name')