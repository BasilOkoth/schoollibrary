from .utils import get_current_and_upcoming_lessons


def timetable_tv_bulletins(request):
    """
    Inject current and upcoming timetable lessons into the existing
    ShuleHub TV bulletin.

    This does not create a second TV page.
    It only makes timetable messages available to the main TV template.
    """
    path = request.path or ""

    # Only run on TV-related pages to avoid unnecessary database queries
    if "tv" not in path.lower():
        return {}

    data = get_current_and_upcoming_lessons(limit=8)

    return {
        # Full timetable objects, useful if the TV template wants cards/details
        "tv_timetable_template": data["template"],
        "tv_current_lessons": data["current_lessons"],
        "tv_upcoming_lessons": data["upcoming_lessons"],
        "tv_timetable_now": data["now"],

        # Ready-made short bulletin messages for the main TV ticker
        "tv_current_lesson_bulletins": data["current_bulletins"],
        "tv_upcoming_lesson_bulletins": data["upcoming_bulletins"],
        "tv_timetable_bulletins": data["tv_bulletins"],
    }
