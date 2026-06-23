from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

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


def get_current_and_upcoming_lessons(limit=12):
    """
    Get current and upcoming lessons for the active TV timetable.
    This is used by the timetable TV page and can also be reused by TV bulletins.
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
    TV page showing current and upcoming lessons.
    """
    data = get_current_and_upcoming_lessons(limit=12)

    context = {
        "tenant_schema": tenant_schema,
        "template": data["template"],
        "current_lessons": data["current_lessons"],
        "upcoming_lessons": data["upcoming_lessons"],
        "now": data["now"],
        "current_day": data["current_day"],
        "current_time": data["current_time"],
    }

    return render(request, "timetable/tv_current_lessons.html", context)

@login_required
def timetable_entry_update(request, tenant_schema=None, pk=None):
    """
    Edit timetable lesson/activity.
    """
    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to edit timetable lessons."
        )

    entry = get_object_or_404(TimetableEntry, pk=pk)

    if request.method == "POST":
        form = TimetableEntryForm(request.POST, instance=entry)

        if form.is_valid():
            entry = form.save(commit=False)

            try:
                entry.full_clean()
                entry.save()

                messages.success(request, "Timetable lesson updated successfully.")
                return redirect(f"/tenant/{tenant_schema}/app/timetable/manage/")

            except Exception as error:
                form.add_error(None, error)
    else:
        form = TimetableEntryForm(instance=entry)

    context = {
        "tenant_schema": tenant_schema,
        "form": form,
        "title": "Edit Lesson / Activity",
        "submit_label": "Update Lesson",
    }

    return render(request, "timetable/form.html", context)


@login_required
def timetable_entry_delete(request, tenant_schema=None, pk=None):
    """
    Delete timetable lesson/activity.
    """
    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to delete timetable lessons."
        )

    entry = get_object_or_404(TimetableEntry, pk=pk)

    if request.method == "POST":
        entry.delete()
        messages.success(request, "Timetable lesson deleted successfully.")
        return redirect(f"/tenant/{tenant_schema}/app/timetable/manage/")

    context = {
        "tenant_schema": tenant_schema,
        "entry": entry,
    }

    return render(request, "timetable/confirm_delete.html", context)


@login_required
def timetable_template_deactivate(request, tenant_schema=None, pk=None):
    """
    Safely deactivate timetable instead of deleting everything.
    """
    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to deactivate this timetable."
        )

    template = get_object_or_404(TimetableTemplate, pk=pk)

    if request.method == "POST":
        template.is_active = False
        template.show_on_tv = False
        template.save()

        messages.success(request, "Timetable deactivated successfully.")
        return redirect(f"/tenant/{tenant_schema}/app/timetable/manage/")

    context = {
        "tenant_schema": tenant_schema,
        "template": template,
    }

    return render(request, "timetable/confirm_deactivate_template.html", context)
@login_required
def timetable_export_excel(request, tenant_schema=None, export_type="all"):
    """
    Export timetable to Excel.

    Admin and principal can export all timetable records.
    Teachers can export their own timetable when using teacher export.
    Students can export the visible timetable.
    """
    if not can_view_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to export the timetable."
        )

    template = TimetableTemplate.objects.filter(is_active=True).first()
    entries = TimetableEntry.objects.none()

    if template:
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

        role = get_user_role(request.user)

        if export_type == "teacher":
            if role == "teacher" and not can_manage_timetable(request.user):
                entries = entries.filter(teacher=request.user)

            entries = entries.order_by(
                "teacher__first_name",
                "teacher__last_name",
                "day__sort_order",
                "period__sort_order",
            )

        elif export_type == "class":
            entries = entries.order_by(
                "class_group__name",
                "day__sort_order",
                "period__sort_order",
            )

        else:
            entries = entries.order_by(
                "day__sort_order",
                "period__sort_order",
                "class_group__name",
            )

    wb = Workbook()
    ws = wb.active

    if export_type == "teacher":
        ws.title = "Teacher Timetable"
        title = "Teacher Timetable"
        filename = "teacher_timetable.xlsx"
    elif export_type == "class":
        ws.title = "Class Timetable"
        title = "Class Timetable"
        filename = "class_timetable.xlsx"
    else:
        ws.title = "School Timetable"
        title = "School Timetable"
        filename = "school_timetable.xlsx"

    ws.merge_cells("A1:H1")
    ws["A1"] = title
    ws["A1"].font = Font(size=16, bold=True)
    ws["A1"].alignment = Alignment(horizontal="center")

    if template:
        ws.merge_cells("A2:H2")
        ws["A2"] = template.name
        ws["A2"].font = Font(size=12, italic=True)
        ws["A2"].alignment = Alignment(horizontal="center")

    headers = [
        "Day",
        "Period",
        "Start Time",
        "End Time",
        "Class",
        "Lesson / Activity",
        "Teacher",
        "Room",
    ]

    header_row = 4

    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(
            start_color="1F2937",
            end_color="1F2937",
            fill_type="solid",
        )
        cell.alignment = Alignment(horizontal="center")

    row = header_row + 1

    for entry in entries:
        teacher_name = ""
        if entry.teacher:
            teacher_name = (
                entry.teacher.get_full_name()
                or entry.teacher.username
            )

        room_name = entry.room.name if entry.room else ""

        ws.cell(row=row, column=1, value=entry.day.get_day_display())
        ws.cell(row=row, column=2, value=entry.period.name)
        ws.cell(row=row, column=3, value=entry.period.start_time.strftime("%H:%M"))
        ws.cell(row=row, column=4, value=entry.period.end_time.strftime("%H:%M"))
        ws.cell(row=row, column=5, value=str(entry.class_group))
        ws.cell(row=row, column=6, value=entry.lesson_title())
        ws.cell(row=row, column=7, value=teacher_name)
        ws.cell(row=row, column=8, value=room_name)

        row += 1

    column_widths = {
        "A": 15,
        "B": 18,
        "C": 12,
        "D": 12,
        "E": 20,
        "F": 28,
        "G": 28,
        "H": 20,
    }

    for column, width in column_widths.items():
        ws.column_dimensions[column].width = width

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    wb.save(response)

    return response
