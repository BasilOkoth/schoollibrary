from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from django.contrib.auth import get_user_model

User = get_user_model()
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
    Common timetable context used by dashboard,
    class view, teacher view and manage view.
    """

    template = TimetableTemplate.objects.filter(
        is_active=True
    ).first()

    entries = TimetableEntry.objects.none()
    days = TimetableDay.objects.none()
    periods = TimetablePeriod.objects.none()

    teachers = User.objects.none()
    classes = []

    selected_day = request.GET.get("day", "")
    selected_teacher = request.GET.get("teacher", "")
    selected_class = request.GET.get("class", "")

    current_lesson = None
    next_lesson = None

    now = timezone.localtime()
    current_day = now.strftime("%A").upper()
    current_time = now.time()

    if template:

        days = TimetableDay.objects.filter(
            template=template,
            is_active=True,
        ).order_by(
            "sort_order"
        )

        periods = TimetablePeriod.objects.filter(
            template=template,
            is_active=True,
        ).order_by(
            "sort_order",
            "start_time",
        )

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

        # Filters

        if selected_day:
            entries = entries.filter(
                day_id=selected_day
            )

        if selected_teacher:
            entries = entries.filter(
                teacher_id=selected_teacher
            )

        if selected_class:
            entries = entries.filter(
                class_group_id=selected_class
            )

        entries = entries.order_by(
            "day__sort_order",
            "period__sort_order",
            "class_group__name",
        )

        # Current lesson

        current_lesson = TimetableEntry.objects.filter(
            template=template,
            day__day=current_day,
            period__start_time__lte=current_time,
            period__end_time__gte=current_time,
            is_active=True,
        ).select_related(
            "day",
            "period",
            "class_group",
            "subject",
            "teacher",
            "room",
        ).first()

        # Next lesson

        next_lesson = TimetableEntry.objects.filter(
            template=template,
            day__day=current_day,
            period__start_time__gt=current_time,
            is_active=True,
        ).select_related(
            "day",
            "period",
            "class_group",
            "subject",
            "teacher",
            "room",
        ).order_by(
            "period__start_time"
        ).first()

        teachers = User.objects.filter(
            timetable_lessons__isnull=False
        ).distinct().order_by(
            "first_name",
            "last_name"
        )

        classes = (
            TimetableEntry.objects.filter(
                template=template,
                is_active=True,
            )
            .values(
                "class_group_id",
                "class_group__name",
            )
            .distinct()
            .order_by(
                "class_group__name"
            )
        )

    return {
        "tenant_schema": tenant_schema,
        "template": template,
        "days": days,
        "periods": periods,
        "entries": entries,

        "teachers": teachers,
        "classes": classes,

        "selected_day": selected_day,
        "selected_teacher": selected_teacher,
        "selected_class": selected_class,

        "current_lesson": current_lesson,
        "next_lesson": next_lesson,

        "current_day": current_day,
        "current_time": current_time,
        "now": now,

        "can_manage": can_manage_timetable(
            request.user
        ),
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

    Admin, Principal, Deputy Principal, Director of Studies:
    - Can manage timetable.

    Teachers, Class Teachers, and Students:
    - Can view timetable only.
    """

    try:
        user_role = request.user.profile.role
    except Exception:
        user_role = None

    allowed_roles = [
        "admin",
        "principal",
        "deputy_principal",
        "director_of_studies",
        "teacher",
        "class_teacher",
        "student",
    ]

    if user_role not in allowed_roles:
        return HttpResponseForbidden(
            "You do not have permission to view the timetable."
        )

    context = get_active_timetable_context(
        request=request,
        tenant_schema=tenant_schema,
    )

    context["view_title"] = "School Timetable"
    context["user_role"] = user_role

    # Useful in the timetable template to show/hide management buttons
    context["can_manage_timetable"] = user_role in [
        "admin",
        "principal",
        "deputy_principal",
        "director_of_studies",
    ]

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
    Teachers view their own lessons by default.
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

        if (
            role == "teacher"
            and not can_manage_timetable(request.user)
            and not request.GET.get("teacher")
        ):
            entries = entries.filter(
                teacher=request.user
            )

        context["entries"] = entries.order_by(
            "teacher__first_name",
            "teacher__last_name",
            "day__sort_order",
            "period__sort_order",
        )

    return render(
        request,
        "timetable/dashboard.html",
        context,
    )


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
# ============================================================
# TIMETABLE ENTRY EDIT/DELETE VIEWS - SAFE PATCH
# ============================================================
# Put this at the bottom of timetable/views.py
#
# This fixes:
# PathTenantSchemaMiddleware error:
# module 'timetable.views' has no attribute 'timetable_entry_edit'
#
# It provides BOTH names:
# - timetable_entry_edit
# - timetable_entry_delete
# - entry_edit alias
# - entry_delete alias
# ============================================================

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TimetableEntryForm
from .models import TimetableEntry


def _timetable_tenant_info(request, tenant_schema=None):
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    return schema_name, f"/tenant/{schema_name}/app"


@login_required
def timetable_entry_edit(request, tenant_schema=None, pk=None):
    """
    Edit timetable entry.

    URL:
    /tenant/<tenant_schema>/app/timetable/entry/<pk>/edit/
    """

    schema_name, tenant_base_url = _timetable_tenant_info(
        request,
        tenant_schema,
    )

    entry = get_object_or_404(
        TimetableEntry,
        pk=pk,
    )

    if request.method == "POST":
        form = TimetableEntryForm(
            request.POST,
            instance=entry,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Timetable entry updated successfully.",
            )

            return redirect(
                f"{tenant_base_url}/timetable/manage/"
            )

        messages.error(
            request,
            "Please correct the errors below.",
        )

    else:
        form = TimetableEntryForm(
            instance=entry,
        )

    context = {
        "form": form,
        "entry": entry,
        "title": "Edit Timetable Entry",
        "tenant_schema": schema_name,
        "current_tenant_schema": schema_name,
        "tenant_base_url": tenant_base_url,
        "cancel_url": f"{tenant_base_url}/timetable/manage/",
    }

    return render(
        request,
        "timetable/entry_form.html",
        context,
    )


@login_required
def timetable_entry_delete(request, tenant_schema=None, pk=None):
    """
    Delete timetable entry.

    GET shows confirmation page.
    POST deletes the entry.

    URL:
    /tenant/<tenant_schema>/app/timetable/entry/<pk>/delete/
    """

    schema_name, tenant_base_url = _timetable_tenant_info(
        request,
        tenant_schema,
    )

    entry = get_object_or_404(
        TimetableEntry,
        pk=pk,
    )

    if request.method == "POST":
        entry.delete()

        messages.success(
            request,
            "Timetable entry deleted successfully.",
        )

        return redirect(
            f"{tenant_base_url}/timetable/manage/"
        )

    context = {
        "entry": entry,
        "title": "Delete Timetable Entry",
        "tenant_schema": schema_name,
        "current_tenant_schema": schema_name,
        "tenant_base_url": tenant_base_url,
        "cancel_url": f"{tenant_base_url}/timetable/manage/",
    }

    return render(
        request,
        "timetable/entry_confirm_delete.html",
        context,
    )


# ------------------------------------------------------------
# Backward-compatible aliases.
# These prevent crashes if urls.py uses views.entry_edit
# instead of views.timetable_entry_edit.
# ------------------------------------------------------------
entry_edit = timetable_entry_edit
entry_delete = timetable_entry_delete
