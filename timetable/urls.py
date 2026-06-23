from django.urls import path
from . import views

app_name = "timetable"

urlpatterns = [
    path("", views.timetable_dashboard, name="dashboard"),
    path("class/", views.class_timetable_view, name="class_timetable"),
    path("teacher/", views.teacher_timetable_view, name="teacher_timetable"),
    path("tv/current-lessons/", views.timetable_tv_current_lessons, name="tv_current_lessons"),
]
