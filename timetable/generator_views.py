# File: timetable/generator_views.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .generator import generate_timetable_preview
from .generator_forms import TimetableRequirementForm
from .generator_models import TimetableGenerationDraft, TimetableRequirement
from .models import TimetableEntry, TimetableTemplate
from .views import can_manage_timetable


SESSION_KEY = "timetable_generator_draft_id"


def _schema_name(request, tenant_schema=None):
    return (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
    )


def _timetable_url(request, tenant_schema, suffix):
    schema = _schema_name(request, tenant_schema)
    return f"/tenant/{schema}/app/timetable/{suffix}"


def _active_template():
    return TimetableTemplate.objects.filter(
        is_active=True
    ).first()


def _clear_cached_draft(request):
    request.session.pop(SESSION_KEY, None)


@login_required
def timetable_generator(request, tenant_schema=None):
    """Configure weekly requirements used by the generator."""

    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to generate timetables."
        )

    template = _active_template()

    if request.method == "POST":
        if not template:
            messages.error(
                request,
                "Create and activate a timetable template first.",
            )
            return redirect(
                _timetable_url(
                    request,
                    tenant_schema,
                    "generator/",
                )
            )

        form = TimetableRequirementForm(request.POST)

        if form.is_valid():
            requirement = form.save(commit=False)
            requirement.template = template
            requirement.created_by = request.user
            requirement.save()

            _clear_cached_draft(request)

            messages.success(
                request,
                "Weekly teaching requirement added.",
            )
            return redirect(
                _timetable_url(
                    request,
                    tenant_schema,
                    "generator/",
                )
            )
    else:
        form = TimetableRequirementForm()

    requirements = TimetableRequirement.objects.none()

    if template:
        requirements = TimetableRequirement.objects.filter(
            template=template
        ).select_related(
            "class_group",
            "stream",
            "subject",
            "teacher",
            "room",
        )

    context = {
        "tenant_schema": _schema_name(request, tenant_schema),
        "template": template,
        "form": form,
        "requirements": requirements,
    }

    return render(
        request,
        "timetable/generator.html",
        context,
    )


@login_required
def timetable_requirement_edit(
    request,
    tenant_schema=None,
    pk=None,
):
    """Edit one weekly teaching requirement."""

    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to edit timetable requirements."
        )

    requirement = get_object_or_404(
        TimetableRequirement,
        pk=pk,
    )

    if request.method == "POST":
        form = TimetableRequirementForm(
            request.POST,
            instance=requirement,
        )

        if form.is_valid():
            requirement = form.save(commit=False)
            requirement.save()

            _clear_cached_draft(request)

            messages.success(
                request,
                "Weekly teaching requirement updated.",
            )
            return redirect(
                _timetable_url(
                    request,
                    tenant_schema,
                    "generator/",
                )
            )
    else:
        form = TimetableRequirementForm(
            instance=requirement
        )

    context = {
        "tenant_schema": _schema_name(request, tenant_schema),
        "form": form,
        "title": "Edit Weekly Teaching Requirement",
        "submit_label": "Update Requirement",
    }

    return render(
        request,
        "timetable/form.html",
        context,
    )


@login_required
@require_POST
def timetable_requirement_delete(
    request,
    tenant_schema=None,
    pk=None,
):
    """Delete one weekly teaching requirement."""

    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to delete timetable requirements."
        )

    requirement = get_object_or_404(
        TimetableRequirement,
        pk=pk,
    )
    requirement.delete()

    _clear_cached_draft(request)

    messages.success(
        request,
        "Weekly teaching requirement deleted.",
    )

    return redirect(
        _timetable_url(
            request,
            tenant_schema,
            "generator/",
        )
    )


@login_required
def timetable_generator_preview(
    request,
    tenant_schema=None,
):
    """Generate or redisplay a timetable preview."""

    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to generate timetables."
        )

    template = _active_template()

    if not template:
        messages.error(
            request,
            "Create and activate a timetable template first.",
        )
        return redirect(
            _timetable_url(
                request,
                tenant_schema,
                "generator/",
            )
        )

    if request.method == "POST":
        result = generate_timetable_preview(template)

        TimetableGenerationDraft.objects.filter(
            template=template,
            created_by=request.user,
            is_applied=False,
        ).delete()

        draft = TimetableGenerationDraft.objects.create(
            template=template,
            created_by=request.user,
            proposals=result["proposals"],
            errors=result["errors"],
            warnings=result["warnings"],
        )
        request.session[SESSION_KEY] = draft.id
    else:
        draft_id = request.session.get(SESSION_KEY)

        if not draft_id:
            return redirect(
                _timetable_url(
                    request,
                    tenant_schema,
                    "generator/",
                )
            )

        draft = get_object_or_404(
            TimetableGenerationDraft,
            pk=draft_id,
            template=template,
            created_by=request.user,
            is_applied=False,
        )

    context = {
        "tenant_schema": _schema_name(request, tenant_schema),
        "template": template,
        "proposals": draft.proposals,
        "errors": draft.errors,
        "warnings": draft.warnings,
        "draft": draft,
    }

    return render(
        request,
        "timetable/generator_preview.html",
        context,
    )


@login_required
@require_POST
def timetable_generator_apply(
    request,
    tenant_schema=None,
):
    """Validate and save the currently previewed generated lessons."""

    if not can_manage_timetable(request.user):
        return HttpResponseForbidden(
            "You do not have permission to apply generated timetables."
        )

    draft_id = request.session.get(SESSION_KEY)

    if not draft_id:
        messages.error(
            request,
            "The timetable preview has expired. Generate it again.",
        )
        return redirect(
            _timetable_url(
                request,
                tenant_schema,
                "generator/",
            )
        )

    draft = get_object_or_404(
        TimetableGenerationDraft,
        pk=draft_id,
        created_by=request.user,
        is_applied=False,
    )

    if draft.errors:
        messages.error(
            request,
            "Resolve the generator errors before applying the timetable.",
        )
        return redirect(
            _timetable_url(
                request,
                tenant_schema,
                "generator/preview/",
            )
        )

    template = get_object_or_404(
        TimetableTemplate,
        pk=draft.template_id,
        is_active=True,
    )
    proposals = draft.proposals

    if not proposals:
        messages.info(
            request,
            "There are no new lessons to add.",
        )
        return redirect(
            _timetable_url(
                request,
                tenant_schema,
                "generator/",
            )
        )

    created_count = 0
    skipped_count = 0

    try:
        with transaction.atomic():
            for proposal in proposals:
                exact_exists = TimetableEntry.objects.filter(
                    template=template,
                    day_id=proposal["day_id"],
                    period_id=proposal["period_id"],
                    class_group_id=proposal["class_group_id"],
                    stream_id=proposal["stream_id"],
                    subject_id=proposal["subject_id"],
                    lesson_group=proposal["lesson_group"],
                    is_active=True,
                ).exists()

                if exact_exists:
                    skipped_count += 1
                    continue

                entry = TimetableEntry(
                    template=template,
                    day_id=proposal["day_id"],
                    period_id=proposal["period_id"],
                    class_group_id=proposal["class_group_id"],
                    stream_id=proposal["stream_id"],
                    lesson_group=proposal["lesson_group"],
                    subject_id=proposal["subject_id"],
                    teacher_id=proposal["teacher_id"],
                    room_id=proposal["room_id"],
                    notes="Auto-generated from weekly teaching requirements.",
                    is_active=True,
                    show_on_tv=True,
                    created_by=request.user,
                )
                entry.full_clean()
                entry.save()
                created_count += 1

            draft.is_applied = True
            draft.save(update_fields=["is_applied"])

    except Exception as error:
        messages.error(
            request,
            (
                "Nothing was saved because the timetable changed or a conflict "
                f"was detected: {error}"
            ),
        )
        return redirect(
            _timetable_url(
                request,
                tenant_schema,
                "generator/preview/",
            )
        )

    _clear_cached_draft(request)

    message = (
        f"Automatic timetable applied successfully: "
        f"{created_count} lesson entries created."
    )
    if skipped_count:
        message += f" {skipped_count} existing entries were skipped."

    messages.success(request, message)

    return redirect(
        _timetable_url(
            request,
            tenant_schema,
            "manage/",
        )
    )
