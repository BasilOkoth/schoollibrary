from django.utils import timezone

from .models import TimetableTemplate, TimetableEntry


def get_current_and_upcoming_lessons(limit=8):
    """
    Returns current lessons and upcoming lessons for the active TV timetable.
    Used by timetable TV page and ShuleHub TV bulletins.
    """
    template = TimetableTemplate.objects.filter(
        is_active=True,
        show_on_tv=True,
    ).first()

    now = timezone.localtime()
    current_day = now.strftime("%A").upper()
    current_time = now.time()

    current_lessons = TimetableEntry.objects.none()
    upcoming_lessons = TimetableEntry.objects.none()

    if template:
        current_lessons = TimetableEntry.objects.filter(
            template=template,
            day__day=current_day,
            period__start_time__lte=current_time,
            period__end_time__gte=current_time,
            show_on_tv=True,
            is_active=True,
        ).select_related(
            "day",
            "period",
            "class_group",
            "subject",
            "teacher",
            "room",
        ).order_by(
            "class_group__name",
            "period__sort_order",
        )[:limit]

        upcoming_lessons = TimetableEntry.objects.filter(
            template=template,
            day__day=current_day,
            period__start_time__gt=current_time,
            show_on_tv=True,
            is_active=True,
        ).select_related(
            "day",
            "period",
            "class_group",
            "subject",
            "teacher",
            "room",
        ).order_by(
            "period__start_time",
            "class_group__name",
        )[:limit]

    return {
        "template": template,
        "now": now,
        "current_day": current_day,
        "current_time": current_time,
        "current_lessons": current_lessons,
        "upcoming_lessons": upcoming_lessons,
    }
