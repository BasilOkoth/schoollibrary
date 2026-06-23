from django.urls import path
from . import views

app_name = "timetable"

urlpatterns = [
    path("", views.timetable_dashboard, name="dashboard"),
    path("class/", views.class_timetable_view, name="class_timetable"),
    path("teacher/", views.teacher_timetable_view, name="teacher_timetable"),

    path("manage/", views.timetable_manage, name="manage"),
    path("template/add/", views.timetable_template_create, name="template_add"),
    path("day/add/", views.timetable_day_create, name="day_add"),
    path("period/add/", views.timetable_period_create, name="period_add"),
    path("room/add/", views.timetable_room_create, name="room_add"),
    path("entry/add/", views.timetable_entry_create, name="entry_add"),

    path("export/", views.timetable_export_excel, name="export_excel"),
    path("export/class/", views.timetable_export_excel, {"export_type": "class"}, name="export_class_excel"),
    path("export/teacher/", views.timetable_export_excel, {"export_type": "teacher"}, name="export_teacher_excel"),

    path("tv/current-lessons/", views.timetable_tv_current_lessons, name="tv_current_lessons"),
]
