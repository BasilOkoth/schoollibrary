# File: timetable/apps.py

from django.apps import AppConfig


class TimetableConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "timetable"

    def ready(self):
        from . import generator_models  # noqa: F401
