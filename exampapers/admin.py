from django.contrib import admin

from .models import (
    ExamSubjectPaper,
    StudentPaperMark,
)


@admin.register(ExamSubjectPaper)
class ExamSubjectPaperAdmin(admin.ModelAdmin):
    list_display = [
        "exam",
        "subject",
        "paper_name",
        "max_marks",
        "order",
        "updated_at",
    ]

    list_filter = [
        "exam__academic_year",
        "exam__term",
        "subject",
    ]

    search_fields = [
        "exam__name",
        "subject__name",
        "paper_name",
    ]

    ordering = [
        "-exam__academic_year",
        "subject__name",
        "order",
    ]


@admin.register(StudentPaperMark)
class StudentPaperMarkAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "paper",
        "raw_score",
        "entered_by",
        "updated_at",
    ]

    list_filter = [
        "paper__exam__academic_year",
        "paper__exam__term",
        "paper__subject",
    ]

    search_fields = [
        "student__admission_number",
        "student__first_name",
        "student__last_name",
        "paper__paper_name",
        "paper__subject__name",
    ]

    readonly_fields = [
        "student",
        "paper",
        "raw_score",
        "entered_by",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False
