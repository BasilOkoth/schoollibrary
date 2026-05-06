# digitallibrary/forms.py

import os
import random
from datetime import datetime
from django import forms
from .models import FeeStructure, Class
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import FeeStructure
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
    PaperSet,      # ADD THIS
    PaperResource, # ADD THIS
)


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


# ========== FEE STRUCTURE FORM - WORKING VERSION (KEEP THIS ONE) ==========
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
                'class': 'w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-green-500'
            }),
            'late_fee_penalty': forms.NumberInput(attrs={
                'class': 'w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white focus:border-green-500',
                'placeholder': 'e.g., 5.00',
                'step': '0.01'
            }),
        }
        labels = {
            'academic_year': 'Academic Year',
            'term': 'Term',
            'student_class': 'Class Level',
            'deadline': 'Payment Deadline',
            'late_fee_penalty': 'Late Fee Penalty (%)',
        }


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
        self.fields["subject"].help_text = "Select the subject this resource belongs to"

        self.fields["category"].queryset = Category.objects.all().order_by("name")
        self.fields["category"].empty_label = "--- Select Category ---"
        self.fields["category"].required = False
        self.fields["category"].label = "Category"
        self.fields["category"].help_text = "Select resource category (e.g., Exam, Notes, etc.)"

        current_year = timezone.now().year
        year_choices = [("", "Select Year")]
        for year in range(current_year + 5, 1949, -1):
            year_choices.append((str(year), str(year)))
        year_choices.append(("N/A", "N/A (No specific year)"))

        self.fields["year"].widget = forms.Select(choices=year_choices)
        self.fields["year"].required = False
        self.fields["year"].label = "Year"
        self.fields["year"].help_text = (
            "Select the year of publication/exam or N/A for general resources"
        )

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

    def clean(self):
        cleaned_data = super().clean()

        subject = cleaned_data.get("subject")
        paper_type = cleaned_data.get("paper_type")
        year = cleaned_data.get("year")

        if paper_type in ["Paper 1", "Paper 2", "Paper 3", "Practical"] and not subject:
            self.add_error("subject", "Subject is required for exam papers")

        if year and year != "N/A":
            try:
                year_int = int(year)
                current_year = timezone.now().year
                if year_int < 1900 or year_int > current_year + 5:
                    self.add_error("year", f"Year must be between 1900 and {current_year + 5}")
            except ValueError:
                self.add_error("year", "Invalid year format")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.cleaned_data.get("file"):
            if instance.pk and instance.file:
                try:
                    if os.path.isfile(instance.file.path):
                        os.remove(instance.file.path)
                except Exception:
                    pass
            instance.file = self.cleaned_data["file"]

        if self.cleaned_data.get("cover_image"):
            if instance.pk and instance.cover_image:
                try:
                    if os.path.isfile(instance.cover_image.path):
                        os.remove(instance.cover_image.path)
                except Exception:
                    pass
            instance.cover_image = self.cleaned_data["cover_image"]

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class AnnouncementForm(forms.ModelForm):
    """Form for creating and editing announcements"""
    
    expiry_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Optional: Select expiry date",
    )
    expiry_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time"}),
        help_text="Optional: Select expiry time (defaults to midnight)",
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

        self.fields["target_audience"].help_text = "Select who should see this announcement"
        self.fields["is_featured"].help_text = "Featured announcements appear at the top"
        self.fields["attachment"].help_text = "Optional: Upload a PDF, DOC, or image"

        apply_dark_widget_classes(self)

    def clean(self):
        cleaned_data = super().clean()

        expiry_date = cleaned_data.get("expiry_date")
        expiry_time = cleaned_data.get("expiry_time")

        if expiry_date:
            from datetime import datetime, time
            from django.utils.timezone import make_aware

            expiry_datetime = datetime.combine(
                expiry_date,
                expiry_time if expiry_time else time(23, 59, 59),
            )
            cleaned_data["expires_at"] = make_aware(expiry_datetime)

        if cleaned_data.get("expires_at") and cleaned_data["expires_at"] <= timezone.now():
            self.add_error("expiry_date", "Expiry date must be in the future")

        return cleaned_data

    def save(self, commit=True):
        announcement = super().save(commit=False)

        if self.cleaned_data.get("expires_at"):
            announcement.expires_at = self.cleaned_data["expires_at"]

        if commit:
            announcement.save()

        return announcement


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
        widget=forms.Select(),
    )
    status = forms.ChoiceField(
        choices=STATUS_FILTER_CHOICES,
        required=False,
        widget=forms.Select(),
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search announcements...",
                "autocomplete": "off",
            }
        ),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


class BulkAnnouncementForm(forms.Form):
    """Form for bulk creating announcements"""
    
    titles = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Enter one title per line...",
            }
        ),
        help_text="Enter each announcement title on a new line",
    )
    content_template = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": "Enter template content. Use {title} as placeholder...",
            }
        ),
        help_text="Content template. Use {title} to insert the title",
    )
    target_audience = forms.ChoiceField(
        choices=Announcement.AUDIENCE_CHOICES,
        widget=forms.Select(),
    )
    is_featured = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(),
    )
    attachment = forms.FileField(
        required=False,
        widget=forms.FileInput(),
    )
    expires_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


class StudentForm(forms.ModelForm):
    """Form for creating and editing students with class dropdown and add-new-class feature"""

    new_class = forms.CharField(
        required=False,
        label="Add New Class",
        help_text="Type a class name here if it is not in the dropdown.",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Example: Grade 4 East, Form 3A, Year 7",
                "class": "w-full"
            }
        ),
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
            "admission_number": forms.TextInput(attrs={"placeholder": "Admission number"}),
            "upi_number": forms.TextInput(attrs={"placeholder": "UPI number"}),
            "first_name": forms.TextInput(attrs={"placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name"}),
            "middle_name": forms.TextInput(attrs={"placeholder": "Middle name"}),
            "gender": forms.Select(choices=Student.GENDER_CHOICES),
            "current_class": forms.Select(),
            "admission_year": forms.NumberInput(
                attrs={"min": 2000, "max": 2035, "placeholder": "Admission year"}
            ),
            "parent_name": forms.TextInput(attrs={"placeholder": "Parent / guardian name"}),
            "parent_phone": forms.TextInput(attrs={"placeholder": "Parent phone number"}),
            "parent_alternative_phone": forms.TextInput(
                attrs={"placeholder": "Alternative phone number"}
            ),
            "parent_email": forms.EmailInput(attrs={"placeholder": "Parent email"}),
            "physical_address": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Physical address"}
            ),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["admission_year"].initial = timezone.now().year

        self.fields["current_class"].queryset = Class.objects.all().order_by("name")
        self.fields["current_class"].empty_label = "--- Select a class ---"
        self.fields["current_class"].required = False
        self.fields["current_class"].label = "Select Class"
        self.fields["current_class"].help_text = "Choose an existing class from the dropdown"

        self.fields["admission_number"].help_text = "Unique admission number"
        self.fields["parent_phone"].help_text = "Primary contact for fee communication"
        self.fields["new_class"].help_text = "Type a new class name here if not in the dropdown above"
        self.fields["gender"].help_text = "Select student's gender"
        self.fields["gender"].required = False
        self.fields["gender"].initial = 'N'

        self.order_fields(
            [
                "admission_number",
                "upi_number",
                "first_name",
                "last_name",
                "middle_name",
                "gender",
                "current_class",
                "new_class",
                "admission_year",
                "parent_name",
                "parent_phone",
                "parent_alternative_phone",
                "parent_email",
                "physical_address",
                "is_active",
            ]
        )

        apply_dark_widget_classes(self)

    def clean_admission_year(self):
        admission_year = self.cleaned_data.get("admission_year")
        current_year = timezone.now().year

        if admission_year and not (2000 <= admission_year <= current_year + 5):
            raise ValidationError(
                f"Admission year must be between 2000 and {current_year + 5}."
            )

        return admission_year

    def clean(self):
        cleaned_data = super().clean()
        current_class = cleaned_data.get("current_class")
        new_class = (self.cleaned_data.get("new_class") or "").strip()

        if not current_class and not new_class:
            self.add_error("current_class", "Please select a class or enter a new class name.")
            self.add_error("new_class", "Enter a new class name if not in the dropdown.")

        return cleaned_data

    def save(self, commit=True):
        student = super().save(commit=False)
        new_class_name = (self.cleaned_data.get("new_class") or "").strip()

        if new_class_name:
            class_obj, created = Class.objects.get_or_create(
                name=new_class_name.title(),
            )
            student.current_class = class_obj

        if commit:
            student.save()
            self.save_m2m()

        return student


class StudentSearchForm(forms.Form):
    """Form for searching students"""
    
    query = forms.CharField(
        label="Search",
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search by name, admission number, or parent phone...",
                "autocomplete": "off",
            }
        ),
    )
    class_filter = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Class",
        widget=forms.Select(),
    )
    gender_filter = forms.ChoiceField(
        choices=[
            ("", "All Genders"),
            ("M", "Male"),
            ("F", "Female"),
            ("O", "Other"),
            ("N", "Not Specified"),
        ],
        required=False,
        widget=forms.Select(),
    )
    status_filter = forms.ChoiceField(
        choices=[
            ("", "All Students"),
            ("active", "Active Only"),
            ("inactive", "Inactive Only"),
        ],
        required=False,
        widget=forms.Select(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_filter"].queryset = Class.objects.all().order_by("name")
        self.fields["class_filter"].empty_label = "All Classes"
        apply_dark_widget_classes(self)


# ========== REMOVED THE DUPLICATE FeeStructureForm HERE ==========
# The duplicate problematic form has been removed.
# Only the working FeeStructureForm above remains.


class FeeComponentForm(forms.ModelForm):
    """Form for dynamic fee components"""
    
    class Meta:
        model = FeeComponent
        fields = ['name', 'amount', 'is_optional', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g., Tuition Fee, Sports Fee'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'placeholder': '0.00'}),
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional description'}),
            'is_optional': forms.CheckboxInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)


class FeePaymentForm(forms.ModelForm):
    """Form for recording fee payments"""
    
    class Meta:
        model = FeePayment
        fields = [
            "student",
            "amount",
            "payment_method",
            "transaction_id",
            "term",
            "academic_year",
            "notes",
        ]
        widgets = {
            "student": forms.HiddenInput(),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0", "placeholder": "Enter amount"}),
            "payment_method": forms.Select(),
            "transaction_id": forms.TextInput(attrs={"placeholder": "MPESA/Bank Reference Number"}),
            "term": forms.Select(),
            "academic_year": forms.Select(),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional notes"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        current_year = timezone.now().year
        current_month = timezone.now().month

        if current_month <= 4:
            default_term = 1
        elif current_month <= 8:
            default_term = 2
        else:
            default_term = 3

        year_choices = [
            ("", "Select Year"),
            (current_year - 1, str(current_year - 1)),
            (current_year, str(current_year)),
            (current_year + 1, str(current_year + 1)),
        ]
        self.fields["academic_year"].widget = forms.Select(choices=year_choices)

        term_choices = [
            ("", "Select Term"),
            (1, "Term 1"),
            (2, "Term 2"),
            (3, "Term 3"),
        ]
        self.fields["term"].widget = forms.Select(choices=term_choices)

        if not self.instance.pk:
            self.fields["academic_year"].initial = current_year
            self.fields["term"].initial = default_term

        self.fields["payment_method"].help_text = "Select how the payment was made"
        self.fields["transaction_id"].help_text = "MPESA confirmation code or bank reference number"
        self.fields["amount"].help_text = "Enter the payment amount in KES"
        self.fields["student"].required = False

        apply_dark_widget_classes(self)

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount and amount <= 0:
            raise ValidationError("Amount must be greater than zero.")
        if amount and amount > 10000000:
            raise ValidationError("Amount cannot exceed 10,000,000 KES.")
        return amount

    def clean_transaction_id(self):
        transaction_id = self.cleaned_data.get("transaction_id")
        
        if transaction_id:
            existing = FeePayment.objects.filter(transaction_id=transaction_id)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError("This transaction ID has already been used.")
        
        return transaction_id

    def clean_student(self):
        student = self.cleaned_data.get('student')
        if not student:
            raise ValidationError("Please select a student from the search results")
        return student

    def save(self, commit=True):
        payment = super().save(commit=False)
        
        if not payment.receipt_number:
            payment.receipt_number = self.generate_receipt_number()
        
        if commit:
            payment.save()
        
        return payment

    def generate_receipt_number(self):
        prefix = "RCP"
        date_str = datetime.now().strftime("%Y%m%d")
        random_num = str(random.randint(1000, 9999))
        
        receipt_number = f"{prefix}{date_str}{random_num}"
        
        while FeePayment.objects.filter(receipt_number=receipt_number).exists():
            random_num = str(random.randint(1000, 9999))
            receipt_number = f"{prefix}{date_str}{random_num}"
        
        return receipt_number


class FeeBalanceFilterForm(forms.Form):
    """Form for filtering fee balances"""

    academic_year = forms.ChoiceField(
        required=False,
        widget=forms.Select(),
    )
    term = forms.ChoiceField(
        choices=[("", "All Terms"), (1, "Term 1"), (2, "Term 2"), (3, "Term 3")],
        required=False,
        widget=forms.Select(),
    )
    status = forms.ChoiceField(
        choices=[
            ("", "All Status"),
            ("PAID", "Fully Paid"),
            ("PARTIAL", "Partially Paid"),
            ("DEFAULTING", "Defaulting"),
            ("OVERPAID", "Overpaid"),
        ],
        required=False,
        widget=forms.Select(),
    )
    student_class = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label="Class",
        widget=forms.Select(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["student_class"].queryset = Class.objects.all().order_by("name")
        self.fields["student_class"].empty_label = "All Classes"

        current_year = timezone.now().year
        year_choices = [
            ("", "All Years"),
            (current_year - 1, current_year - 1),
            (current_year, current_year),
            (current_year + 1, current_year + 1),
        ]
        self.fields["academic_year"].widget = forms.Select(choices=year_choices)

        apply_dark_widget_classes(self)


class FeedbackForm(forms.ModelForm):
    """Form for user feedback"""
    
    class Meta:
        model = Feedback
        fields = ['feedback_type', 'priority', 'subject', 'message', 'rating', 'screenshot']
        widgets = {
            'feedback_type': forms.Select(),
            'priority': forms.Select(),
            'subject': forms.TextInput(attrs={'placeholder': 'Brief summary of your feedback'}),
            'message': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Please provide detailed feedback...'}),
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5, 'step': 1}),
            'screenshot': forms.ClearableFileInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rating'].help_text = "Rate your experience (1-5)"
        self.fields['screenshot'].help_text = "Optional: Upload a screenshot"
        apply_dark_widget_classes(self)


class GradeForm(forms.ModelForm):
    """Form for creating and editing grade boundaries"""
    
    class Meta:
        model = Grade
        fields = ['grade', 'min_score', 'max_score', 'points', 'description']
        widgets = {
            'min_score': forms.NumberInput(attrs={'step': '0.01'}),
            'max_score': forms.NumberInput(attrs={'step': '0.01'}),
            'points': forms.NumberInput(attrs={'step': '0.1'}),
            'description': forms.TextInput(attrs={'placeholder': 'Optional description'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)
    
    def clean(self):
        cleaned_data = super().clean()
        min_score = cleaned_data.get('min_score')
        max_score = cleaned_data.get('max_score')
        
        if min_score and max_score and min_score > max_score:
            raise ValidationError("Minimum score cannot be greater than maximum score.")
        
        return cleaned_data


class ExamForm(forms.ModelForm):
    """Form for creating and editing exams with class association"""
    
    class Meta:
        model = Exam
        fields = ['name', 'exam_type', 'term', 'academic_year', 'student_class', 'max_score', 'exam_date', 'description']
        widgets = {
            'exam_date': forms.DateInput(attrs={'type': 'date'}),
            'name': forms.TextInput(attrs={'placeholder': 'e.g., MOCK EXAM - FORM 4'}),
            'max_score': forms.NumberInput(attrs={'step': '0.01'}),
            'academic_year': forms.TextInput(attrs={'placeholder': '2026'}),
            'description': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional description'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['student_class'].queryset = Class.objects.all().order_by('name')
        self.fields['student_class'].required = False
        self.fields['student_class'].empty_label = "--- All Classes (School-wide Exam) ---"
        self.fields['student_class'].label = "Class"
        self.fields['student_class'].help_text = "Select a specific class for this exam"
        
        current_year = timezone.now().year
        if not self.instance.pk:
            self.fields['academic_year'].initial = str(current_year)
        
        apply_dark_widget_classes(self)


class StudentResultForm(forms.ModelForm):
    """Form for entering individual student results"""
    
    class Meta:
        model = StudentResult
        fields = ['student', 'exam', 'subject', 'score', 'remarks']
        widgets = {
            'score': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'remarks': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional remarks'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.filter(is_active=True).order_by('first_name', 'last_name')
        self.fields['student'].empty_label = "--- Select Student ---"
        self.fields['exam'].queryset = Exam.objects.filter(is_active=True).order_by('-academic_year', '-term')
        self.fields['exam'].empty_label = "--- Select Exam ---"
        self.fields['subject'].queryset = Subject.objects.filter(is_active=True).order_by('name')
        self.fields['subject'].empty_label = "--- Select Subject ---"
        self.fields['subject'].required = True
        apply_dark_widget_classes(self)
    
    def clean_score(self):
        score = self.cleaned_data.get('score')
        exam = self.cleaned_data.get('exam')
        
        if score and exam and score > exam.max_score:
            raise ValidationError(f"Score cannot exceed the exam's maximum score of {exam.max_score}.")
        
        return score


class BulkResultForm(forms.Form):
    """Form for bulk entering results for a class"""
    
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.filter(is_active=True), 
        empty_label="Select Exam",
        widget=forms.Select()
    )
    student_class = forms.ModelChoiceField(
        queryset=Class.objects.all(), 
        empty_label="Select Class (Optional)", 
        required=False,
        widget=forms.Select()
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)
    
    def clean(self):
        cleaned_data = super().clean()
        exam = cleaned_data.get('exam')
        student_class = cleaned_data.get('student_class')
        
        if exam and exam.student_class and student_class and exam.student_class != student_class:
            raise ValidationError(f"This exam is only for {exam.student_class.name}.")
        
        return cleaned_data


class ExcelResultsUploadForm(forms.Form):
    """Form for uploading Excel file with results"""
    
    excel_file = forms.FileField(
        label="Excel File",
        help_text="Upload Excel file (.xlsx, .xls) with student results",
        widget=forms.FileInput(attrs={
            'accept': '.xlsx,.xls',
            'class': 'w-full'
        })
    )
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.filter(is_active=True),
        label="Select Exam",
        help_text="Select the exam for these results",
        widget=forms.Select()
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(is_active=True),
        label="Select Subject",
        help_text="Select the subject for these results",
        widget=forms.Select()
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_dark_widget_classes(self)
    
    def clean_excel_file(self):
        excel_file = self.cleaned_data.get('excel_file')
        if excel_file:
            if not excel_file.name.endswith(('.xlsx', '.xls')):
                raise ValidationError("Please upload a valid Excel file (.xlsx or .xls).")
# Add to digitallibrary/forms.py

class PaperResourceForm(forms.ModelForm):
    """Form for uploading resources organized by PaperSet"""
    
    class Meta:
        model = PaperResource
        fields = ['paper_set', 'kind', 'file', 'title']
        widgets = {
            'paper_set': forms.Select(attrs={'class': TEXT_INPUT_CLASSES}),
            'kind': forms.Select(attrs={'class': TEXT_INPUT_CLASSES}),
            'file': forms.ClearableFileInput(attrs={'class': FILE_INPUT_CLASSES}),
            'title': forms.TextInput(attrs={'class': TEXT_INPUT_CLASSES, 'placeholder': 'Optional custom title'}),
        }


class PaperSetFilterForm(forms.Form):
    """Filter form for PaperSets"""
    grade = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': SELECT_CLASSES}))
    subject = forms.ModelChoiceField(queryset=Subject.objects.filter(is_active=True), required=False, empty_label="All Subjects")
    year = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': SELECT_CLASSES}))
    paper_type = forms.ChoiceField(choices=[('', 'All Types')] + list(PaperSet.PAPER_TYPES), required=False)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate grade choices from existing PaperSets
        grades = PaperSet.objects.values_list('grade', flat=True).distinct().order_by('grade')
        self.fields['grade'].choices = [('', 'All Grades')] + [(g, g) for g in grades]
        
        years = PaperSet.objects.values_list('year', flat=True).distinct().order_by('-year')
        self.fields['year'].choices = [('', 'All Years')] + [(y, y) for y in years]
        apply_dark_widget_classes(self)
        return excel_file
class BulkStudentUploadForm(forms.Form):
    excel_file = forms.FileField(
        label='Excel/CSV File',
        help_text='Upload an Excel (.xlsx, .xls) or CSV file with student data',
        widget=forms.FileInput(attrs={
            'accept': '.xlsx,.xls,.csv',
            'class': 'w-full bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-2 text-slate-200 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500'
        })
    )
    
    def clean_excel_file(self):
        file = self.cleaned_data['excel_file']
        
        # Check file extension
        ext = file.name.split('.')[-1].lower()
        if ext not in ['xlsx', 'xls', 'csv']:
            raise forms.ValidationError('Please upload an Excel (.xlsx, .xls) or CSV file')
        
        # Check file size (max 5MB)
        if file.size > 5 * 1024 * 1024:
            raise forms.ValidationError('File size must be less than 5MB')
        
        return file