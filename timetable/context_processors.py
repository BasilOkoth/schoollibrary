from .utils import get_current_and_upcoming_lessons


def timetable_tv_bulletins(request):
    """
    Makes current and upcoming timetable lessons available automatically
    to ShuleHub TV bulletin templates.

    It only runs on TV pages to avoid unnecessary queries on normal pages.
    """
    path = request.path or ""

    if "/tv/" not in path:
        return {}

    data = get_current_and_upcoming_lessons(limit=8)

    return {
        "tv_timetable_template": data["template"],
        "tv_current_lessons": data["current_lessons"],
        "tv_upcoming_lessons": data["upcoming_lessons"],
        "tv_timetable_now": data["now"],
    }
