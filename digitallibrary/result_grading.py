from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.db.models import Q

from digitallibrary.models import StudentResult


@dataclass(frozen=True)
class GradeResolution:
    label: str
    points: Decimal
    remark: str
    system_code: str
    grade_object: object | None = None


def model_has_field(model_class, field_name):
    try:
        model_class._meta.get_field(field_name)
        return True
    except Exception:
        return False


def get_model_field(model_class, field_name):
    try:
        return model_class._meta.get_field(field_name)
    except Exception:
        return None


def decimal_value(value, default="0"):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def normalized_text(value):
    return str(value or "").strip().lower()


def is_old_curriculum_class(school_class):
    """
    Return True for legacy 8-4-4 classes such as Form 3 and Form 4.
    """

    if not school_class:
        return False

    if getattr(school_class, "is_legacy", False):
        return True

    if getattr(school_class, "curriculum", "") == "LEGACY_844":
        return True

    if getattr(school_class, "level", "") == "LEGACY_SECONDARY":
        return True

    class_name = normalized_text(
        getattr(school_class, "name", "")
        or str(school_class)
    )

    old_curriculum_keywords = [
        "form 3",
        "form three",
        "form iii",
        "form 4",
        "form four",
        "form iv",
    ]

    return any(
        keyword in class_name
        for keyword in old_curriculum_keywords
    )


def traditional_grade_for_percentage(percentage_score):
    percentage_score = decimal_value(percentage_score)

    boundaries = [
        (Decimal("80"), "A", 12, "Excellent"),
        (Decimal("75"), "A-", 11, "Very Good"),
        (Decimal("70"), "B+", 10, "Good"),
        (Decimal("65"), "B", 9, "Good"),
        (Decimal("60"), "B-", 8, "Above Average"),
        (Decimal("55"), "C+", 7, "Average"),
        (Decimal("50"), "C", 6, "Average"),
        (Decimal("45"), "C-", 5, "Below Average"),
        (Decimal("40"), "D+", 4, "Weak"),
        (Decimal("35"), "D", 3, "Weak"),
        (Decimal("30"), "D-", 2, "Very Weak"),
    ]

    for minimum, label, points, description in boundaries:
        if percentage_score >= minimum:
            return GradeResolution(
                label=label,
                points=Decimal(str(points)),
                remark=f"{label} - {description}",
                system_code="traditional",
            )

    return GradeResolution(
        label="E",
        points=Decimal("1"),
        remark="E - Fail",
        system_code="traditional",
    )


def fallback_cbe_grade_for_percentage(percentage_score):
    percentage_score = decimal_value(percentage_score)

    boundaries = [
        (Decimal("90"), "EE1", 8, "Exceptional"),
        (Decimal("75"), "EE2", 7, "Excellent"),
        (Decimal("58"), "ME1", 6, "Meets Expectation"),
        (Decimal("41"), "ME2", 5, "Meets Expectation"),
        (Decimal("31"), "AE1", 4, "Approaching Expectation"),
        (Decimal("21"), "AE2", 3, "Approaching Expectation"),
        (Decimal("11"), "BE1", 2, "Below Expectation"),
    ]

    for minimum, label, points, description in boundaries:
        if percentage_score >= minimum:
            return GradeResolution(
                label=label,
                points=Decimal(str(points)),
                remark=f"{label} - {description}",
                system_code="cbe",
            )

    return GradeResolution(
        label="BE2",
        points=Decimal("1"),
        remark="BE2 - Below Expectation",
        system_code="cbe",
    )


def get_optional_model(model_name):
    try:
        return apps.get_model(
            "digitallibrary",
            model_name,
        )
    except LookupError:
        return None


def choose_school_grading_system(exam=None, subject=None):
    GradingSystem = get_optional_model("GradingSystem")

    if GradingSystem is None:
        return None

    queryset = GradingSystem.objects.all()

    if model_has_field(GradingSystem, "is_active"):
        queryset = queryset.filter(is_active=True)

    if model_has_field(GradingSystem, "is_archived"):
        queryset = queryset.filter(is_archived=False)

    # Prefer systems that are specifically linked to this exam or subject,
    # while still allowing school-wide default systems.
    filters = Q()

    if exam is not None and model_has_field(GradingSystem, "exam"):
        filters |= Q(exam=exam)

    if subject is not None and model_has_field(GradingSystem, "subject"):
        filters |= Q(subject=subject)

    if subject is not None and model_has_field(
        GradingSystem,
        "applicable_subjects",
    ):
        filters |= Q(applicable_subjects=subject)

    if model_has_field(GradingSystem, "is_default"):
        filters |= Q(is_default=True)

    if filters:
        preferred = queryset.filter(filters).distinct()

        ordering = []

        if model_has_field(GradingSystem, "is_default"):
            ordering.append("-is_default")

        ordering.append("name")

        preferred = preferred.order_by(*ordering)

        if preferred.exists():
            return preferred.first()

    if model_has_field(GradingSystem, "is_default"):
        default_system = queryset.filter(
            is_default=True,
        ).first()

        if default_system:
            return default_system

    return queryset.order_by("name").first()


def school_grade_from_scale(
    percentage_score,
    exam=None,
    subject=None,
):
    GradeScale = get_optional_model("GradeScale")
    grading_system = choose_school_grading_system(
        exam=exam,
        subject=subject,
    )

    if (
        GradeScale is None
        or grading_system is None
    ):
        return None

    scale = (
        GradeScale.objects
        .filter(
            grading_system=grading_system,
            min_score__lte=percentage_score,
            max_score__gte=percentage_score,
        )
        .order_by("-min_score")
        .first()
    )

    if scale is None:
        return None

    label = str(
        getattr(scale, "grade", "")
        or getattr(scale, "level", "")
        or getattr(scale, "code", "")
        or getattr(scale, "name", "")
    ).strip()

    if not label:
        return None

    points = decimal_value(
        getattr(scale, "points", 0)
    )

    description = str(
        getattr(scale, "remark", "")
        or getattr(scale, "description", "")
    ).strip()

    remark = (
        f"{label} - {description}"
        if description
        else label
    )

    return GradeResolution(
        label=label,
        points=points,
        remark=remark,
        system_code="traditional",
        grade_object=scale,
    )


def cbe_grade_from_table(percentage_score):
    KNECCBEGrade = get_optional_model("KNECCBEGrade")

    if KNECCBEGrade is None:
        return None

    queryset = KNECCBEGrade.objects.filter(
        min_score__lte=percentage_score,
        max_score__gte=percentage_score,
    )

    if model_has_field(KNECCBEGrade, "is_active"):
        queryset = queryset.filter(is_active=True)

    grade_object = queryset.order_by(
        "-min_score",
    ).first()

    if grade_object is None:
        return None

    label = str(
        getattr(grade_object, "level", "")
        or getattr(grade_object, "grade", "")
        or getattr(grade_object, "code", "")
        or getattr(grade_object, "name", "")
    ).strip()

    if not label:
        return None

    points = decimal_value(
        getattr(grade_object, "points", 0)
    )

    description = str(
        getattr(grade_object, "level_name", "")
        or getattr(grade_object, "remark", "")
        or getattr(grade_object, "description", "")
    ).strip()

    remark = (
        f"{label} - {description}"
        if description
        else label
    )

    return GradeResolution(
        label=label,
        points=points,
        remark=remark,
        system_code="cbe",
        grade_object=grade_object,
    )


def resolve_grade(
    *,
    percentage_score,
    school_class,
    exam=None,
    subject=None,
):
    percentage_score = decimal_value(
        percentage_score
    )

    if is_old_curriculum_class(school_class):
        configured_grade = school_grade_from_scale(
            percentage_score=percentage_score,
            exam=exam,
            subject=subject,
        )

        if configured_grade:
            return configured_grade

        return traditional_grade_for_percentage(
            percentage_score
        )

    configured_grade = cbe_grade_from_table(
        percentage_score
    )

    if configured_grade:
        return configured_grade

    return fallback_cbe_grade_for_percentage(
        percentage_score
    )


def find_grade_object_for_field(
    grade_field,
    resolution,
):
    remote_field = getattr(
        grade_field,
        "remote_field",
        None,
    )

    remote_model = (
        getattr(
            remote_field,
            "model",
            None,
        )
        if remote_field
        else None
    )

    if remote_model is None:
        return None

    candidate = resolution.grade_object

    if (
        candidate is not None
        and isinstance(candidate, remote_model)
    ):
        return candidate

    for lookup_field in [
        "level",
        "grade",
        "code",
        "name",
    ]:
        if model_has_field(
            remote_model,
            lookup_field,
        ):
            grade_object = remote_model.objects.filter(
                **{
                    lookup_field: resolution.label,
                }
            ).first()

            if grade_object:
                return grade_object

    return None


def build_student_result_defaults(
    *,
    score,
    percentage_score,
    school_class,
    exam,
    subject,
    user,
    extra_remarks="",
):
    """
    Build StudentResult defaults safely across ShuleHub model versions.

    The grade field may be a CharField/TextField or a ForeignKey. The label is
    also stored in competency_level/grade_remark where those fields exist, so
    the result remains displayable even when no matching grade FK row exists.
    """

    resolution = resolve_grade(
        percentage_score=percentage_score,
        school_class=school_class,
        exam=exam,
        subject=subject,
    )

    defaults = {
        "score": score,
        "entered_by": user,
    }

    grade_field = get_model_field(
        StudentResult,
        "grade",
    )

    if grade_field:
        remote_field = getattr(
            grade_field,
            "remote_field",
            None,
        )

        if remote_field:
            grade_object = find_grade_object_for_field(
                grade_field,
                resolution,
            )

            if grade_object:
                defaults["grade"] = grade_object
        else:
            defaults["grade"] = resolution.label

    if model_has_field(
        StudentResult,
        "points",
    ):
        defaults["points"] = resolution.points

    combined_remarks = resolution.remark

    if extra_remarks:
        combined_remarks = (
            f"{resolution.remark}; "
            f"{str(extra_remarks).strip()}"
        )

    if model_has_field(
        StudentResult,
        "remarks",
    ):
        defaults["remarks"] = combined_remarks

    if model_has_field(
        StudentResult,
        "grade_remark",
    ):
        defaults["grade_remark"] = resolution.remark

    if model_has_field(
        StudentResult,
        "competency_level",
    ):
        defaults["competency_level"] = resolution.label

    grading_field = get_model_field(
        StudentResult,
        "grading_system_used",
    )

    if (
        grading_field
        and getattr(
            grading_field,
            "get_internal_type",
            lambda: "",
        )() == "CharField"
    ):
        defaults[
            "grading_system_used"
        ] = resolution.system_code

    return defaults


def grade_label_from_object(value):
    if value in (
        None,
        "",
    ):
        return ""

    if isinstance(value, str):
        return value.strip()

    for attribute in [
        "level",
        "grade",
        "code",
        "name",
    ]:
        label = getattr(
            value,
            attribute,
            None,
        )

        if label:
            return str(label).strip()

    return str(value).strip()


def get_result_grade_display(result):
    if result is None:
        return ""

    if model_has_field(
        StudentResult,
        "grade",
    ):
        try:
            label = grade_label_from_object(
                getattr(
                    result,
                    "grade",
                    None,
                )
            )
        except Exception:
            label = ""

        if label:
            return label

    if model_has_field(
        StudentResult,
        "competency_level",
    ):
        label = str(
            getattr(
                result,
                "competency_level",
                "",
            )
            or ""
        ).strip()

        if label:
            return label

    for field_name in [
        "grade_remark",
        "remarks",
    ]:
        if not model_has_field(
            StudentResult,
            field_name,
        ):
            continue

        text = str(
            getattr(
                result,
                field_name,
                "",
            )
            or ""
        ).strip()

        if not text:
            continue

        # Grade remarks are stored as "EE2 - Excellent" or
        # "B+ - Good". Return only the grade label for the table.
        label = (
            text.split(";", 1)[0]
            .split(" - ", 1)[0]
            .strip()
        )

        if label and not label.lower().startswith(
            "raw result:"
        ):
            return label

    return ""
