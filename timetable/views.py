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


def get_active_timetable_context(request, tenant_schema=None):
    """
    Common timetable context used by dashboard, class view and teacher view.
    """
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

    return {
        "tenant_schema": tenant_schema,
        "template": template,
        "days": days,
        "periods": periods,
        "entries": entries,
        "can_manage": can_manage_timetable(request.user),
    }


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

    context = get_active_timetable_context(
        request=request,
        tenant_schema=tenant_schema,
    )
    context["view_title"] = "School Timetable"

    return render(request, "timetable/dashboard.html", context)


@login_required
def class_timetable_view(request, tenant_schema=None):
    """
    Class timetable page.

    Admin, principal, teachers and students can view this.
    """
    if not can_view_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to view the class timetable."
        )

    context = get_active_timetable_context(
        request=request,
        tenant_schema=tenant_schema,
    )

    context["view_title"] = "Class Timetable"

    if context["template"]:
        context["entries"] = context["entries"].order_by(
            "class_group__name",
            "day__sort_order",
            "period__sort_order",
        )

    return render(request, "timetable/dashboard.html", context)


@login_required
def teacher_timetable_view(request, tenant_schema=None):
    """
    Teacher timetable page.

    Admin and principal can view all teacher lessons.
    Teachers view their own lessons.
    Students can view the general teacher timetable only if allowed by role.
    """
    if not can_view_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to view the teacher timetable."
        )

    context = get_active_timetable_context(
        request=request,
        tenant_schema=tenant_schema,
    )

    context["view_title"] = "Teacher Timetable"

    if context["template"]:
        entries = context["entries"]

        role = get_user_role(request.user)

        if role == "teacher" and not can_manage_timetable(request.user):
            entries = entries.filter(teacher=request.user)

        context["entries"] = entries.order_by(
            "teacher__first_name",
            "teacher__last_name",
            "day__sort_order",
            "period__sort_order",
        )

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
