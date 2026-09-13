# File: timetable/generator.py

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
import random

from django.db.models import Count

from digitallibrary.models import ClassStream

from .generator_models import TimetableRequirement
from .models import TimetableDay, TimetableEntry, TimetablePeriod


@dataclass(frozen=True)
class ScopedRequirement:
    requirement_id: int
    class_group_id: int
    class_group_name: str
    stream_id: int | None
    stream_name: str
    subject_id: int
    subject_name: str
    teacher_id: int | None
    teacher_name: str
    room_id: int | None
    room_name: str
    lessons_per_week: int
    consecutive_periods: int
    lesson_group: str
    parallel_block: str
    remaining_periods: int
    existing_day_counts: dict[int, int]


@dataclass(frozen=True)
class SchedulingUnit:
    key: str
    members: tuple[ScopedRequirement, ...]
    sessions_needed: int
    consecutive_periods: int


def _teacher_name(user):
    if not user:
        return ""

    full_name = user.get_full_name().strip()
    return full_name or user.username


def _expand_requirement(requirement):
    if requirement.apply_to_all_streams:
        streams = list(
            ClassStream.objects.filter(
                school_class=requirement.class_group,
                is_active=True,
            ).order_by("name")
        )
        if streams:
            return streams

    return [requirement.stream]


def _existing_entries_for_scope(template, requirement, stream):
    queryset = TimetableEntry.objects.filter(
        template=template,
        class_group=requirement.class_group,
        subject=requirement.subject,
        is_active=True,
        lesson_group=requirement.lesson_group,
    )

    if stream:
        queryset = queryset.filter(stream=stream)
    else:
        queryset = queryset.filter(stream__isnull=True)

    return queryset


def _build_scoped_requirements(template):
    requirements = list(
        TimetableRequirement.objects.filter(
            template=template,
            is_active=True,
        ).select_related(
            "class_group",
            "stream",
            "subject",
            "teacher",
            "room",
        )
    )

    scoped = []
    errors = []
    warnings = []

    for requirement in requirements:
        for stream in _expand_requirement(requirement):
            existing_queryset = _existing_entries_for_scope(
                template,
                requirement,
                stream,
            )
            existing_count = existing_queryset.count()
            existing_day_counts = {
                row["day_id"]: row["total"]
                for row in existing_queryset.values("day_id").annotate(
                    total=Count("id")
                )
            }

            remaining_periods = max(
                0,
                requirement.lessons_per_week - existing_count,
            )

            scope_name = requirement.class_group.name
            if stream:
                scope_name = f"{scope_name} {stream.name}"

            if existing_count > requirement.lessons_per_week:
                warnings.append(
                    (
                        f"{scope_name} - {requirement.subject.name} already has "
                        f"{existing_count} periods, above the configured "
                        f"{requirement.lessons_per_week}."
                    )
                )

            if (
                requirement.consecutive_periods == 2
                and remaining_periods % 2
            ):
                errors.append(
                    (
                        f"{scope_name} - {requirement.subject.name} has "
                        f"{remaining_periods} period(s) still required, which "
                        "cannot be completed using only double periods."
                    )
                )

            scoped.append(
                ScopedRequirement(
                    requirement_id=requirement.id,
                    class_group_id=requirement.class_group_id,
                    class_group_name=requirement.class_group.name,
                    stream_id=stream.id if stream else None,
                    stream_name=stream.name if stream else "",
                    subject_id=requirement.subject_id,
                    subject_name=requirement.subject.name,
                    teacher_id=requirement.teacher_id,
                    teacher_name=_teacher_name(requirement.teacher),
                    room_id=requirement.room_id,
                    room_name=requirement.room.name if requirement.room else "",
                    lessons_per_week=requirement.lessons_per_week,
                    consecutive_periods=requirement.consecutive_periods,
                    lesson_group=requirement.lesson_group,
                    parallel_block=requirement.parallel_block,
                    remaining_periods=remaining_periods,
                    existing_day_counts=existing_day_counts,
                )
            )

    return scoped, errors, warnings


def _build_units(scoped_requirements):
    grouped = defaultdict(list)
    errors = []

    for requirement in scoped_requirements:
        if requirement.parallel_block:
            key = (
                f"parallel:{requirement.class_group_id}:"
                f"{requirement.stream_id}:"
                f"{requirement.parallel_block.casefold()}"
            )
        else:
            key = (
                f"single:{requirement.requirement_id}:"
                f"{requirement.stream_id}"
            )

        grouped[key].append(requirement)

    units = []

    for key, members in grouped.items():
        members = tuple(members)

        if key.startswith("parallel:"):
            remaining_values = {
                member.remaining_periods
                for member in members
            }
            consecutive_values = {
                member.consecutive_periods
                for member in members
            }
            lesson_groups = [
                member.lesson_group.casefold()
                for member in members
                if member.lesson_group
            ]

            block_label = members[0].parallel_block
            scope_label = members[0].class_group_name
            if members[0].stream_name:
                scope_label = (
                    f"{scope_label} {members[0].stream_name}"
                )

            if len(members) < 2:
                errors.append(
                    (
                        f"Parallel block {block_label} for {scope_label} "
                        "contains only one subject. Add the other parallel "
                        "subjects or clear the block name."
                    )
                )
                continue

            if len(remaining_values) != 1:
                errors.append(
                    (
                        f"Parallel block {block_label} for {scope_label} has "
                        "different remaining weekly period counts. The subjects "
                        "inside one parallel block must have matching weekly "
                        "loads."
                    )
                )
                continue

            if len(consecutive_values) != 1:
                errors.append(
                    (
                        f"Parallel block {block_label} for {scope_label} mixes "
                        "single and double periods. Use the same period length "
                        "for every subject in the block."
                    )
                )
                continue

            if len(lesson_groups) != len(set(lesson_groups)):
                errors.append(
                    (
                        f"Parallel block {block_label} for {scope_label} "
                        "contains duplicate Lesson / Elective Group names."
                    )
                )
                continue

            teacher_ids = [
                member.teacher_id
                for member in members
                if member.teacher_id
            ]
            if len(teacher_ids) != len(set(teacher_ids)):
                errors.append(
                    (
                        f"Parallel block {block_label} for {scope_label} assigns "
                        "the same teacher to more than one simultaneous subject."
                    )
                )
                continue

            room_ids = [
                member.room_id
                for member in members
                if member.room_id
            ]
            if len(room_ids) != len(set(room_ids)):
                errors.append(
                    (
                        f"Parallel block {block_label} for {scope_label} assigns "
                        "the same room to more than one simultaneous subject."
                    )
                )
                continue

        remaining_periods = members[0].remaining_periods
        consecutive_periods = members[0].consecutive_periods

        if remaining_periods == 0:
            continue

        sessions_needed = remaining_periods // consecutive_periods

        units.append(
            SchedulingUnit(
                key=key,
                members=members,
                sessions_needed=sessions_needed,
                consecutive_periods=consecutive_periods,
            )
        )

    return units, errors


def _build_windows(template, consecutive_periods):
    days = list(
        TimetableDay.objects.filter(
            template=template,
            is_active=True,
        ).order_by("sort_order")
    )
    periods = list(
        TimetablePeriod.objects.filter(
            template=template,
            is_active=True,
        ).order_by("sort_order", "start_time")
    )

    windows = []

    for day in days:
        if consecutive_periods == 1:
            for period in periods:
                if period.is_teaching_period:
                    windows.append(
                        {
                            "day_id": day.id,
                            "day_name": day.get_day_display(),
                            "day_sort": day.sort_order,
                            "period_ids": (period.id,),
                            "period_names": (period.name,),
                            "period_sorts": (period.sort_order,),
                            "times": (
                                (
                                    period.start_time.strftime("%H:%M"),
                                    period.end_time.strftime("%H:%M"),
                                ),
                            ),
                        }
                    )
            continue

        for index in range(len(periods) - consecutive_periods + 1):
            selected = periods[index:index + consecutive_periods]

            if not all(period.is_teaching_period for period in selected):
                continue

            windows.append(
                {
                    "day_id": day.id,
                    "day_name": day.get_day_display(),
                    "day_sort": day.sort_order,
                    "period_ids": tuple(
                        period.id for period in selected
                    ),
                    "period_names": tuple(
                        period.name for period in selected
                    ),
                    "period_sorts": tuple(
                        period.sort_order for period in selected
                    ),
                    "times": tuple(
                        (
                            period.start_time.strftime("%H:%M"),
                            period.end_time.strftime("%H:%M"),
                        )
                        for period in selected
                    ),
                }
            )

    return windows


def _base_occupancy(template):
    class_entries = defaultdict(list)
    teacher_busy = set()
    room_busy = set()
    class_day_load = Counter()
    teacher_day_load = Counter()
    subject_day_count = Counter()

    entries = TimetableEntry.objects.filter(
        template=template,
        is_active=True,
    ).select_related(
        "day",
        "period",
        "class_group",
        "stream",
        "subject",
        "teacher",
        "room",
    )

    for entry in entries:
        slot_key = (
            entry.day_id,
            entry.period_id,
            entry.class_group_id,
        )
        class_entries[slot_key].append(
            {
                "stream_id": entry.stream_id,
                "lesson_group": (entry.lesson_group or "").casefold(),
            }
        )

        if entry.teacher_id:
            teacher_busy.add(
                (
                    entry.teacher_id,
                    entry.day_id,
                    entry.period_id,
                )
            )
            teacher_day_load[
                (entry.teacher_id, entry.day_id)
            ] += 1

        if entry.room_id:
            room_busy.add(
                (
                    entry.room_id,
                    entry.day_id,
                    entry.period_id,
                )
            )

        class_day_load[
            (
                entry.class_group_id,
                entry.stream_id,
                entry.day_id,
            )
        ] += 1

        if entry.subject_id:
            subject_day_count[
                (
                    entry.class_group_id,
                    entry.stream_id,
                    entry.subject_id,
                    entry.day_id,
                )
            ] += 1

    return {
        "class_entries": class_entries,
        "teacher_busy": teacher_busy,
        "room_busy": room_busy,
        "class_day_load": class_day_load,
        "teacher_day_load": teacher_day_load,
        "subject_day_count": subject_day_count,
    }


def _scope_conflicts(
    slot_entries,
    stream_id,
    lesson_group,
):
    candidate_group = (lesson_group or "").casefold()

    for existing in slot_entries:
        existing_stream = existing["stream_id"]
        existing_group = existing["lesson_group"]

        if not candidate_group:
            if stream_id is None:
                return True

            if existing_stream is None and not existing_group:
                return True

            if existing_stream == stream_id:
                return True

            continue

        if stream_id is None:
            if existing_stream is None and (
                not existing_group
                or existing_group == candidate_group
            ):
                return True

            if existing_stream is not None and not existing_group:
                return True

            continue

        if existing_stream is None and not existing_group:
            return True

        if existing_stream == stream_id and (
            not existing_group
            or existing_group == candidate_group
        ):
            return True

    return False


def _window_is_available(unit, window, occupancy):
    class_entries = occupancy["class_entries"]
    teacher_busy = occupancy["teacher_busy"]
    room_busy = occupancy["room_busy"]

    for period_id in window["period_ids"]:
        for member in unit.members:
            slot_key = (
                window["day_id"],
                period_id,
                member.class_group_id,
            )

            if _scope_conflicts(
                class_entries[slot_key],
                member.stream_id,
                member.lesson_group,
            ):
                return False

            if member.teacher_id and (
                member.teacher_id,
                window["day_id"],
                period_id,
            ) in teacher_busy:
                return False

            if member.room_id and (
                member.room_id,
                window["day_id"],
                period_id,
            ) in room_busy:
                return False

    return True


def _window_score(unit, window, occupancy):
    score = 0

    for member in unit.members:
        subject_key = (
            member.class_group_id,
            member.stream_id,
            member.subject_id,
            window["day_id"],
        )
        class_key = (
            member.class_group_id,
            member.stream_id,
            window["day_id"],
        )

        score += (
            occupancy["subject_day_count"][subject_key] * 100
        )
        score += occupancy["class_day_load"][class_key] * 3

        if member.teacher_id:
            score += (
                occupancy["teacher_day_load"][
                    (member.teacher_id, window["day_id"])
                ]
                * 2
            )

        score += (
            member.existing_day_counts.get(
                window["day_id"],
                0,
            )
            * 100
        )

    score += window["day_sort"]
    score += min(window["period_sorts"]) / 100

    return score


def _place_unit(unit, window, occupancy, proposals):
    for period_index, period_id in enumerate(window["period_ids"]):
        for member in unit.members:
            slot_key = (
                window["day_id"],
                period_id,
                member.class_group_id,
            )
            occupancy["class_entries"][slot_key].append(
                {
                    "stream_id": member.stream_id,
                    "lesson_group": (
                        member.lesson_group or ""
                    ).casefold(),
                }
            )

            if member.teacher_id:
                occupancy["teacher_busy"].add(
                    (
                        member.teacher_id,
                        window["day_id"],
                        period_id,
                    )
                )
                occupancy["teacher_day_load"][
                    (member.teacher_id, window["day_id"])
                ] += 1

            if member.room_id:
                occupancy["room_busy"].add(
                    (
                        member.room_id,
                        window["day_id"],
                        period_id,
                    )
                )

            occupancy["class_day_load"][
                (
                    member.class_group_id,
                    member.stream_id,
                    window["day_id"],
                )
            ] += 1
            occupancy["subject_day_count"][
                (
                    member.class_group_id,
                    member.stream_id,
                    member.subject_id,
                    window["day_id"],
                )
            ] += 1

            start_time, end_time = window["times"][period_index]

            proposals.append(
                {
                    "requirement_id": member.requirement_id,
                    "day_id": window["day_id"],
                    "day_name": window["day_name"],
                    "day_sort": window["day_sort"],
                    "period_id": period_id,
                    "period_name": window["period_names"][period_index],
                    "period_sort": window["period_sorts"][period_index],
                    "start_time": start_time,
                    "end_time": end_time,
                    "class_group_id": member.class_group_id,
                    "class_group_name": member.class_group_name,
                    "stream_id": member.stream_id,
                    "stream_name": member.stream_name,
                    "subject_id": member.subject_id,
                    "subject_name": member.subject_name,
                    "teacher_id": member.teacher_id,
                    "teacher_name": member.teacher_name,
                    "room_id": member.room_id,
                    "room_name": member.room_name,
                    "lesson_group": member.lesson_group,
                    "parallel_block": member.parallel_block,
                }
            )


def _task_difficulty(unit):
    score = len(unit.members) * 100
    score += unit.consecutive_periods * 20

    for member in unit.members:
        if member.teacher_id:
            score += 5
        if member.room_id:
            score += 5

    return score


def _run_attempt(template, units, base_occupancy, attempt):
    occupancy = deepcopy(base_occupancy)
    proposals = []

    rng = random.Random(
        (template.pk * 1009)
        + (attempt * 9176)
        + len(units)
    )

    tasks = []
    for unit in units:
        for session_number in range(unit.sessions_needed):
            tasks.append(
                (
                    unit,
                    session_number,
                    rng.random(),
                )
            )

    tasks.sort(
        key=lambda item: (
            -_task_difficulty(item[0]),
            item[2],
        )
    )

    window_cache = {}

    for unit, _session_number, _random_tie in tasks:
        span = unit.consecutive_periods
        if span not in window_cache:
            window_cache[span] = _build_windows(
                template,
                span,
            )

        candidates = [
            window
            for window in window_cache[span]
            if _window_is_available(
                unit,
                window,
                occupancy,
            )
        ]

        if not candidates:
            return proposals, False, unit

        candidates.sort(
            key=lambda window: _window_score(
                unit,
                window,
                occupancy,
            )
        )

        top_count = min(4, len(candidates))
        chosen = rng.choice(candidates[:top_count])

        _place_unit(
            unit,
            chosen,
            occupancy,
            proposals,
        )

    return proposals, True, None


def generate_timetable_preview(template):
    """Build a safe preview without writing timetable entries."""

    scoped, errors, warnings = _build_scoped_requirements(
        template
    )

    if not scoped:
        errors.append(
            "No active weekly teaching requirements have been configured."
        )
        return {
            "proposals": [],
            "errors": errors,
            "warnings": warnings,
        }

    units, unit_errors = _build_units(scoped)
    errors.extend(unit_errors)

    if errors:
        return {
            "proposals": [],
            "errors": errors,
            "warnings": warnings,
        }

    if not units:
        warnings.append(
            "The current timetable already satisfies every active requirement."
        )
        return {
            "proposals": [],
            "errors": [],
            "warnings": warnings,
        }

    base_occupancy = _base_occupancy(template)

    best_proposals = []
    failed_unit = None

    for attempt in range(80):
        proposals, complete, current_failed_unit = _run_attempt(
            template,
            units,
            base_occupancy,
            attempt,
        )

        if complete:
            proposals.sort(
                key=lambda item: (
                    item["day_sort"],
                    item["period_sort"],
                    item["class_group_name"],
                    item["stream_name"],
                    item["lesson_group"],
                    item["subject_name"],
                )
            )
            return {
                "proposals": proposals,
                "errors": [],
                "warnings": warnings,
            }

        if len(proposals) > len(best_proposals):
            best_proposals = proposals
            failed_unit = current_failed_unit

    if failed_unit:
        member = failed_unit.members[0]
        scope_name = member.class_group_name
        if member.stream_name:
            scope_name = f"{scope_name} {member.stream_name}"

        block_name = member.parallel_block
        if block_name:
            target = f"parallel block {block_name}"
        else:
            target = member.subject_name

        errors.append(
            (
                f"Could not find enough conflict-free periods for {scope_name} "
                f"- {target}. Add more teaching periods, reduce weekly loads, "
                "or review teacher/room conflicts."
            )
        )
    else:
        errors.append(
            "The generator could not complete the timetable with the current rules."
        )

    return {
        "proposals": best_proposals,
        "errors": errors,
        "warnings": warnings,
    }
