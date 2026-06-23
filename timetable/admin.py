from django.contrib import admin
from .models import (
    TimetableTemplate,
    TimetableDay,
    TimetablePeriod,
    TimetableRoom,
    TimetableEntry,
    TimetableTVSetting,
)


@admin.register(TimetableTemplate)
class TimetableTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "show_on_tv", "created_at")
    list_filter = ("is_active", "show_on_tv")
    search_fields = ("name",)


@admin.register(TimetableDay)
class TimetableDayAdmin(admin.ModelAdmin):
    list_display = ("template", "day", "sort_order", "is_active")
    list_filter = ("template", "day", "is_active")


@admin.register(TimetablePeriod)
class TimetablePeriodAdmin(admin.ModelAdmin):
    list_display = (
        "template",
        "name",
        "period_type",
        "start_time",
        "end_time",
        "sort_order",
        "is_teaching_period",
        "is_active",
    )
    list_filter = ("template", "period_type", "is_teaching_period", "is_active")
    search_fields = ("name",)


@admin.register(TimetableRoom)
class TimetableRoomAdmin(admin.ModelAdmin):
    list_display = ("name", "room_type", "capacity", "is_active")
    list_filter = ("room_type", "is_active")
    search_fields = ("name",)


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = (
        "template",
        "day",
        "period",
        "class_group",
        "lesson_title",
        "teacher",
        "room",
        "show_on_tv",
        "is_active",
    )
    list_filter = ("template", "day", "period", "class_group", "teacher", "room", "is_active")
    search_fields = (
        "class_group__name",
        "subject__name",
        "custom_activity",
        "teacher__username",
        "room__name",
    )


@admin.register(TimetableTVSetting)
class TimetableTVSettingAdmin(admin.ModelAdmin):
    list_display = (
        "template",
        "title",
        "show_current_lessons",
        "show_next_lessons",
        "show_free_classes",
        "refresh_interval_seconds",
    )
