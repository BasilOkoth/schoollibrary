from django.urls import path
from . import views

app_name = "timetable"

urlpatterns = [
    path("", views.timetable_dashboard, name="dashboard"),
    path("tv/current-lessons/", views.timetable_tv_current_lessons, name="tv_current_lessons"),
]
