from django.contrib import admin
from .models import (
    Category, Resource, UserProfile, SchoolSetting, PrintJob, Subject, 
    Announcement, ActivityLog, Feedback, Student, FeeStructure, FeePayment,
    FeeBalance, Class, Exam, StudentResult, PerformanceSummary, Grade, SMSLog,
    TeacherSubject  # ADDED THIS IMPORT
)


# digitallibrary/admin.py - Update SchoolSetting section

@admin.register(SchoolSetting)
class SchoolSettingAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "principal_name")
    search_fields = ("name", "email", "phone")
    
    fieldsets = (
        ("School Basic Information", {
            "fields": ("name", "motto", "logo")
        }),
        ("Contact Information", {
            "fields": ("address", "phone", "email", "website")
        }),
        ("School Leadership", {
            "fields": ("principal_name",)
        }),
    )
    
    def has_module_permission(self, request):
        """Always show in tenant schemas"""
        return True
    
    def has_add_permission(self, request):
        """Allow adding school settings"""
        return True
    
    def has_change_permission(self, request, obj=None):
        """Allow changing school settings"""
        return True

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "is_approved")
    list_filter = ("role", "is_approved")
    search_fields = ("user__username", "user__email")
    list_editable = ("is_approved",)
    list_per_page = 25


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ("teacher", "copies", "color", "status", "downloaded", "created_at")
    list_filter = ("status", "color", "downloaded")
    list_editable = ("status",)
    search_fields = ("teacher__username", "file")
    readonly_fields = ("created_at", "completed_at")
    date_hierarchy = "created_at"
    list_per_page = 25


@admin.register(TeacherSubject)
class TeacherSubjectAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'subject', 'class_assigned', 'academic_year']
    list_filter = ['academic_year', 'subject']
    search_fields = ['teacher__username', 'subject__name']
    list_per_page = 25


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "grade", "paper_type", "subject", "category", "resource_type", "uploaded_by", "created_at")
    list_filter = ("grade", "paper_type", "subject", "category", "resource_type", "created_at")
    search_fields = ("title", "description", "author")
    readonly_fields = ("views", "created_at", "updated_at")
    list_per_page = 25
    fieldsets = (
        ("Basic Information", {
            "fields": ("title", "description", "author", "grade", "year")
        }),
        ("Classification", {
            "fields": ("subject", "category", "paper_type", "resource_type")
        }),
        ("Files", {
            "fields": ("file", "cover_image")
        }),
        ("Metadata", {
            "fields": ("uploaded_by", "views", "created_at", "updated_at")
        }),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 25


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "code", "description")
    fieldsets = (
        ("Subject Information", {
            "fields": ("name", "code", "description", "is_active")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 25


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "target_audience", "is_featured", "created_at", "expires_at")
    list_filter = ("is_featured", "target_audience", "created_at")
    search_fields = ("title", "content", "author__username")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    list_per_page = 25
    fieldsets = (
        ("Announcement Details", {
            "fields": ("title", "content", "author", "target_audience", "is_featured")
        }),
        ("Attachment & Expiry", {
            "fields": ("attachment", "expires_at"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['subject', 'school_name', 'user', 'feedback_type', 'rating', 'is_resolved', 'created_at']
    list_filter = ['feedback_type', 'is_resolved', 'school_name', 'priority']
    search_fields = ['subject', 'message', 'user__username', 'user__email', 'school_name']
    readonly_fields = ['created_at', 'page_url']
    list_per_page = 25
    
    fieldsets = (
        ('Feedback Information', {
            'fields': ('subject', 'message', 'feedback_type', 'priority', 'rating')
        }),
        ('User Information', {
            'fields': ('user', 'page_url')
        }),
        ('School Information', {
            'fields': ('school_name', 'school_location', 'school_id')
        }),
        ('Status', {
            'fields': ('is_resolved', 'admin_response')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_resolved', 'mark_as_pending']
    
    def mark_as_resolved(self, request, queryset):
        queryset.update(is_resolved=True)
    mark_as_resolved.short_description = "Mark selected feedback as resolved"
    
    def mark_as_pending(self, request, queryset):
        queryset.update(is_resolved=False)
    mark_as_pending.short_description = "Mark selected feedback as pending"


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "description", "timestamp")
    list_filter = ("action", "timestamp")
    search_fields = ("user__username", "action", "description")
    readonly_fields = ("user", "action", "description", "timestamp")
    date_hierarchy = "timestamp"
    list_per_page = 50
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# ============================================================
# FEES MANAGEMENT ADMIN
# ============================================================

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('admission_number', 'first_name', 'last_name', 'current_class', 'gender', 'is_active')
    list_filter = ('is_active', 'current_class', 'gender')
    search_fields = ('admission_number', 'first_name', 'last_name', 'parent_phone', 'upi_number')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('student_class', 'academic_year', 'term', 'total_fees', 'deadline', 'status')
    list_filter = ('academic_year', 'term', 'student_class', 'status')
    search_fields = ('student_class__name', 'name')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'student', 'amount', 'payment_method', 'payment_date', 'term', 'academic_year')
    list_filter = ('payment_method', 'term', 'academic_year', 'payment_date')
    search_fields = ('receipt_number', 'student__first_name', 'student__last_name', 'transaction_id')
    readonly_fields = ('created_at',)
    list_per_page = 25


@admin.register(FeeBalance)
class FeeBalanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'academic_year', 'term', 'total_expected', 'total_paid', 'balance', 'status')
    list_filter = ('status', 'academic_year', 'term')
    search_fields = ('student__first_name', 'student__last_name')
    readonly_fields = ('last_updated',)
    list_per_page = 25


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'stream', 'capacity', 'class_teacher')
    list_filter = ('capacity',)
    search_fields = ('name', 'code', 'stream')
    list_per_page = 25


# ============================================================
# PERFORMANCE ANALYSIS ADMIN
# ============================================================

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam_type', 'term', 'academic_year', 'student_class', 'max_score', 'exam_date')
    list_filter = ('exam_type', 'term', 'academic_year', 'student_class', 'is_active')
    search_fields = ('name',)
    list_per_page = 25


@admin.register(StudentResult)
class StudentResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'subject', 'score', 'grade', 'created_at')
    list_filter = ('exam', 'subject', 'grade')
    search_fields = ('student__first_name', 'student__last_name', 'exam__name')
    list_per_page = 25


@admin.register(PerformanceSummary)
class PerformanceSummaryAdmin(admin.ModelAdmin):
    list_display = ('student', 'academic_year', 'term', 'average_score', 'overall_grade', 'rank_in_class')
    list_filter = ('academic_year', 'term', 'overall_grade')
    search_fields = ('student__first_name', 'student__last_name')
    list_per_page = 25


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('grade', 'min_score', 'max_score', 'points')
    list_filter = ('grade',)
    ordering = ('-min_score',)
    list_per_page = 25


# ============================================================
# SMS LOG ADMIN
# ============================================================

@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'student', 'category', 'status', 'sent_at', 'created_at')
    list_filter = ('category', 'status')
    search_fields = ('recipient', 'recipient_name', 'student__first_name')
    readonly_fields = ('created_at',)
    list_per_page = 25
