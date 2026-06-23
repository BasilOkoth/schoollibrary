from django.utils import timezone

from .models import TimetableTemplate, TimetableEntry


def format_lesson_for_tv(lesson, label="NOW"):
    """
    Convert a timetable lesson into a short TV bulletin text.
    Example:
    NOW: Grade 8 - Mathematics with Mr Otieno • Room 4 • 08:20-09:00
    """
    teacher_name = ""
    room_name = ""

    if lesson.teacher:
        teacher_name = (
            lesson.teacher.get_full_name()
            or lesson.teacher.username
        )

    if lesson.room:
        room_name = lesson.room.name

    lesson_title = lesson.lesson_title()
    class_name = str(lesson.class_group) if lesson.class_group else ""

    start_time = lesson.period.start_time.strftime("%H:%M")
    end_time = lesson.period.end_time.strftime("%H:%M")

    parts = [
        f"{label}:",
        class_name,
        "-",
        lesson_title,
    ]

    if teacher_name:
        parts.append(f"with {teacher_name}")

    if room_name:
        parts.append(f"• {room_name}")

    parts.append(f"• {start_time}-{end_time}")

    return " ".join(parts)


def get_current_and_upcoming_lessons(limit=8):
    """
    Returns current lessons, upcoming lessons, and short bulletin messages
    for the main ShuleHub TV.

    This should feed the existing ShuleHub TV bulletin/ticker.
    It should not be treated as a second TV screen.
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

    current_bulletins = []
    upcoming_bulletins = []
    tv_bulletins = []

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

        for lesson in current_lessons:
            current_bulletins.append(
                format_lesson_for_tv(
                    lesson=lesson,
                    label="NOW",
                )
            )

        for lesson in upcoming_lessons:
            upcoming_bulletins.append(
                format_lesson_for_tv(
                    lesson=lesson,
                    label="NEXT",
                )
            )

        tv_bulletins = current_bulletins + upcoming_bulletins

    return {
        "template": template,
        "now": now,
        "current_day": current_day,
        "current_time": current_time,
        "current_lessons": current_lessons,
        "upcoming_lessons": upcoming_lessons,
        "current_bulletins": current_bulletins,
        "upcoming_bulletins": upcoming_bulletins,
        "tv_bulletins": tv_bulletins,
    }
