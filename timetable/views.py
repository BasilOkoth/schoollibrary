from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.utils import timezone

from .models import TimetableTemplate, TimetableEntry, TimetableDay, TimetablePeriod


def get_user_role(user):
    profile = getattr(user, "profile", None)

    if profile and hasattr(profile, "role"):
        return profile.role

    return ""


def can_manage_timetable(user):
    role = get_user_role(user)
    return user.is_superuser or role in ["admin", "principal"]


def can_view_timetable(user):
    role = get_user_role(user)
    return user.is_superuser or role in ["admin", "principal", "teacher", "student"]


@login_required
def timetable_dashboard(request, tenant_schema=None):
    """
    Main timetable page.

    Admin and Principal:
    - Can manage timetable.

    Teachers and Students:
    - Can view timetable only.
    """
    if not can_view_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to view the timetable."
        )

    template = TimetableTemplate.objects.filter(is_active=True).first()
    entries = TimetableEntry.objects.none()
    days = TimetableDay.objects.none()
    periods = TimetablePeriod.objects.none()

    if template:
        days = TimetableDay.objects.filter(
            template=template,
            is_active=True,
        ).order_by("sort_order")

        periods = TimetablePeriod.objects.filter(
            template=template,
            is_active=True,
        ).order_by("sort_order", "start_time")

        entries = TimetableEntry.objects.filter(
            template=template,
            is_active=True,
        ).select_related(
            "day",
            "period",
            "class_group",
            "subject",
            "teacher",
            "room",
        )

    context = {
        "tenant_schema": tenant_schema,
        "template": template,
        "days": days,
        "periods": periods,
        "entries": entries,
        "can_manage": can_manage_timetable(request.user),
    }

    return render(request, "timetable/dashboard.html", context)


@login_required
def timetable_tv_current_lessons(request, tenant_schema=None):
    """
    TV page showing current lessons going on.
    """
    template = TimetableTemplate.objects.filter(
        is_active=True,
        show_on_tv=True,
    ).first()

    now = timezone.localtime()
    current_day = now.strftime("%A").upper()
    current_time = now.time()

    current_lessons = TimetableEntry.objects.none()

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
        )

    context = {
        "tenant_schema": tenant_schema,
        "template": template,
        "current_lessons": current_lessons,
        "now": now,
        "current_day": current_day,
        "current_time": current_time,
    }

    return render(request, "timetable/tv_current_lessons.html", context)
