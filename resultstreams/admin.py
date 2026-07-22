from django.contrib import admin

from .models import TeachingAssignment


@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "subject",
        "school_class",
        "stream",
        "academic_year",
        "is_active",
    )
    list_filter = (
        "academic_year",
        "school_class",
        "stream",
        "subject",
        "is_active",
    )
    search_fields = (
        "teacher__username",
        "teacher__first_name",
        "teacher__last_name",
        "subject__name",
        "school_class__name",
        "stream__name",
    )
    autocomplete_fields = (
        "teacher",
        "subject",
        "school_class",
        "stream",
    )
