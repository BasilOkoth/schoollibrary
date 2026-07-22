from django.contrib import admin

from .models import (
    ExamSubjectComponent,
    ExamSubjectPaper,
    StudentPaperMark,
)


class ExamSubjectPaperInline(
    admin.TabularInline
):
    model = ExamSubjectPaper
    extra = 0

    fields = [
        "paper_name",
        "max_marks",
        "order",
        "created_by",
    ]


@admin.register(
    ExamSubjectComponent
)
class ExamSubjectComponentAdmin(
    admin.ModelAdmin
):
    list_display = [
        "exam",
        "subject",
        "name",
        "weight_percentage",
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
        "name",
    ]

    ordering = [
        "-exam__academic_year",
        "subject__name",
        "order",
    ]

    inlines = [
        ExamSubjectPaperInline,
    ]


@admin.register(
    ExamSubjectPaper
)
class ExamSubjectPaperAdmin(
    admin.ModelAdmin
):
    list_display = [
        "component",
        "exam_name",
        "subject_name",
        "paper_name",
        "max_marks",
        "order",
    ]

    list_filter = [
        (
            "component__exam__"
            "academic_year"
        ),
        "component__exam__term",
        "component__subject",
    ]

    search_fields = [
        "component__exam__name",
        "component__subject__name",
        "component__name",
        "paper_name",
    ]

    @admin.display(
        description="Exam"
    )
    def exam_name(
        self,
        obj,
    ):
        return obj.component.exam

    @admin.display(
        description="Subject"
    )
    def subject_name(
        self,
        obj,
    ):
        return obj.component.subject


@admin.register(
    StudentPaperMark
)
class StudentPaperMarkAdmin(
    admin.ModelAdmin
):
    list_display = [
        "student",
        "paper",
        "raw_score",
        "entered_by",
        "updated_at",
    ]

    list_filter = [
        (
            "paper__component__exam__"
            "academic_year"
        ),
        (
            "paper__component__"
            "exam__term"
        ),
        "paper__component__subject",
    ]

    search_fields = [
        "student__admission_number",
        "student__first_name",
        "student__last_name",
        "paper__paper_name",
        "paper__component__name",
        (
            "paper__component__"
            "subject__name"
        ),
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
