from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.utils import timezone

from .models import TimetableTemplate, TimetableEntry, TimetableDay, TimetablePeriod
from .forms import (
    TimetableTemplateForm,
    TimetableDayForm,
    TimetablePeriodForm,
    TimetableRoomForm,
    TimetableEntryForm,
)


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
    Common timetable context used by dashboard, class view, teacher view and manage view.
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
        ).order_by(
            "day__sort_order",
            "period__sort_order",
            "class_group__name",
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
def timetable_manage(request, tenant_schema=None):
    """
    Admin/principal timetable management page.
    """
    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to manage the timetable."
        )

    context = get_active_timetable_context(
        request=request,
        tenant_schema=tenant_schema,
    )
    context["view_title"] = "Manage Timetable"

    return render(request, "timetable/manage.html", context)


@login_required
def timetable_template_create(request, tenant_schema=None):
    """
    Create timetable template.
    """
    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to create a timetable."
        )

    if request.method == "POST":
        form = TimetableTemplateForm(request.POST)

        if form.is_valid():
            timetable_template = form.save(commit=False)
            timetable_template.created_by = request.user
            timetable_template.save()

            messages.success(request, "Timetable template created successfully.")
            return redirect(f"/tenant/{tenant_schema}/app/timetable/manage/")
    else:
        form = TimetableTemplateForm()

    context = {
        "tenant_schema": tenant_schema,
        "form": form,
        "title": "Create Timetable Template",
        "submit_label": "Save Template",
    }

    return render(request, "timetable/form.html", context)


@login_required
def timetable_day_create(request, tenant_schema=None):
    """
    Add timetable day.
    """
    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to add timetable days."
        )

    if request.method == "POST":
        form = TimetableDayForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Timetable day added successfully.")
            return redirect(f"/tenant/{tenant_schema}/app/timetable/manage/")
    else:
        form = TimetableDayForm()

    context = {
        "tenant_schema": tenant_schema,
        "form": form,
        "title": "Add Timetable Day",
        "submit_label": "Save Day",
    }

    return render(request, "timetable/form.html", context)


@login_required
def timetable_period_create(request, tenant_schema=None):
    """
    Add timetable period.
    """
    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to add timetable periods."
        )

    if request.method == "POST":
        form = TimetablePeriodForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Timetable period added successfully.")
            return redirect(f"/tenant/{tenant_schema}/app/timetable/manage/")
    else:
        form = TimetablePeriodForm()

    context = {
        "tenant_schema": tenant_schema,
        "form": form,
        "title": "Add Timetable Period",
        "submit_label": "Save Period",
    }

    return render(request, "timetable/form.html", context)


@login_required
def timetable_room_create(request, tenant_schema=None):
    """
    Add timetable room.
    """
    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to add timetable rooms."
        )

    if request.method == "POST":
        form = TimetableRoomForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Timetable room added successfully.")
            return redirect(f"/tenant/{tenant_schema}/app/timetable/manage/")
    else:
        form = TimetableRoomForm()

    context = {
        "tenant_schema": tenant_schema,
        "form": form,
        "title": "Add Room",
        "submit_label": "Save Room",
    }

    return render(request, "timetable/form.html", context)


@login_required
def timetable_entry_create(request, tenant_schema=None):
    """
    Add timetable lesson/activity.
    """
    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to add timetable lessons."
        )

    if request.method == "POST":
        form = TimetableEntryForm(request.POST)

        if form.is_valid():
            entry = form.save(commit=False)
            entry.created_by = request.user
            entry.save()

            messages.success(request, "Timetable lesson added successfully.")
            return redirect(f"/tenant/{tenant_schema}/app/timetable/manage/")
    else:
        form = TimetableEntryForm()

    context = {
        "tenant_schema": tenant_schema,
        "form": form,
        "title": "Add Lesson / Activity",
        "submit_label": "Save Lesson",
    }

    return render(request, "timetable/form.html", context)


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
        ).order_by(
            "class_group__name",
            "period__sort_order",
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
