# File: timetable/urls.py

from django.urls import path

from . import generator_views, views


app_name = "timetable"


urlpatterns = [
    # Dashboard and timetable views
    path(
        "",
        views.timetable_dashboard,
        name="dashboard",
    ),
    path(
        "class/",
        views.class_timetable_view,
        name="class_timetable",
    ),
    path(
        "teacher/",
        views.teacher_timetable_view,
        name="teacher_timetable",
    ),

    # Timetable management
    path(
        "manage/",
        views.timetable_manage,
        name="manage",
    ),

    # Automatic timetable generator
    path(
        "generator/",
        generator_views.timetable_generator,
        name="generator",
    ),
    path(
        "generator/preview/",
        generator_views.timetable_generator_preview,
        name="generator_preview",
    ),
    path(
        "generator/apply/",
        generator_views.timetable_generator_apply,
        name="generator_apply",
    ),
    path(
        "generator/requirement/<int:pk>/edit/",
        generator_views.timetable_requirement_edit,
        name="generator_requirement_edit",
    ),
    path(
        "generator/requirement/<int:pk>/delete/",
        generator_views.timetable_requirement_delete,
        name="generator_requirement_delete",
    ),

    # Timetable templates
    path(
        "template/add/",
        views.timetable_template_create,
        name="template_add",
    ),
    path(
        "template/<int:pk>/deactivate/",
        views.timetable_template_deactivate,
        name="template_deactivate",
    ),

    # Timetable structure
    path(
        "day/add/",
        views.timetable_day_create,
        name="day_add",
    ),
    path(
        "period/add/",
        views.timetable_period_create,
        name="period_add",
    ),
    path(
        "room/add/",
        views.timetable_room_create,
        name="room_add",
    ),

    # Timetable entries
    path(
        "entry/add/",
        views.timetable_entry_create,
        name="entry_add",
    ),
    path(
        "entry/<int:pk>/edit/",
        views.timetable_entry_edit,
        name="entry_edit",
    ),
    path(
        "entry/<int:pk>/delete/",
        views.timetable_entry_delete,
        name="entry_delete",
    ),

    # Exports
    path(
        "export/",
        views.timetable_export_excel,
        name="export_excel",
    ),
    path(
        "export/class/",
        views.timetable_export_excel,
        {"export_type": "class"},
        name="export_class_excel",
    ),
    path(
        "export/teacher/",
        views.timetable_export_excel,
        {"export_type": "teacher"},
        name="export_teacher_excel",
    ),

    # TV timetable
    path(
        "tv/current-lessons/",
        views.timetable_tv_current_lessons,
        name="tv_current_lessons",
    ),
]
