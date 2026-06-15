from functools import wraps
import logging

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django_tenants.utils import schema_context

from tenants.models import Domain, School


logger = logging.getLogger(__name__)


# ============================================================
# SUPER ADMIN ACCESS DECORATOR
# ============================================================

def super_admin_required(view_func):
    """
    Restrict a view to the ShuleHub super administrator.

    Unauthenticated users are sent to the normal ShuleHub login.
    Authenticated users without permission remain logged in and
    receive an access-denied message.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(
                f"/smart-login/?next={request.get_full_path()}"
            )

        profile = getattr(
            request.user,
            "profile",
            None,
        )

        role = (
            getattr(profile, "role", "")
            or ""
        ).strip().lower()

        has_permission = (
            request.user.is_superuser
            or role in {
                "super_admin",
                "superadmin",
            }
        )

        if not has_permission:
            messages.error(
                request,
                (
                    "Access denied. Super administrator "
                    "privileges are required."
                ),
            )

            return redirect("/")

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapper


# ============================================================
# SUPER ADMIN DASHBOARD
# ============================================================

@super_admin_required
def dashboard(request):
    """
    Display the central ShuleHub super-administrator dashboard.
    """

    # --------------------------------------------------------
    # 1. Load tenants from the public schema
    # --------------------------------------------------------
    with schema_context("public"):
        schools_queryset = (
            School.objects.exclude(
                schema_name="public"
            )
            .order_by("-created_on")
        )

        schools = list(schools_queryset)

        total_schools = len(schools)

        active_schools = sum(
            1
            for school in schools
            if getattr(school, "is_active", False)
        )

        total_domains = Domain.objects.count()

        recent_tenants = schools[:5]

    # --------------------------------------------------------
    # 2. Aggregate feedback across tenant schemas
    # --------------------------------------------------------
    recent_feedback = []

    total_feedback = 0
    pending_feedback = 0
    resolved_feedback = 0

    for school in schools:
        schema_name = getattr(
            school,
            "schema_name",
            None,
        )

        if (
            not schema_name
            or schema_name == "public"
        ):
            continue

        try:
            with schema_context(schema_name):
                try:
                    from digitallibrary.models import Feedback

                except ImportError:
                    logger.warning(
                        "Feedback model was not found for %s",
                        school.name,
                    )
                    continue

                try:
                    total_feedback += (
                        Feedback.objects.count()
                    )

                    pending_feedback += (
                        Feedback.objects.filter(
                            status="pending"
                        ).count()
                    )

                    resolved_feedback += (
                        Feedback.objects.filter(
                            status="resolved"
                        ).count()
                    )

                    feedback_queryset = (
                        Feedback.objects.all()
                    )

                    feedback_field_names = {
                        field.name
                        for field in Feedback._meta.get_fields()
                    }

                    if (
                        "is_public"
                        in feedback_field_names
                    ):
                        feedback_queryset = (
                            feedback_queryset.filter(
                                is_public=True
                            )
                        )

                    feedbacks = (
                        feedback_queryset.order_by(
                            "-created_at"
                        )[:5]
                    )

                    for feedback in feedbacks:
                        recent_feedback.append({
                            "id": feedback.id,
                            "user_name": (
                                getattr(
                                    feedback,
                                    "user_name",
                                    "",
                                )
                                or "Anonymous"
                            ),
                            "user_email": getattr(
                                feedback,
                                "user_email",
                                "",
                            ),
                            "school_name": getattr(
                                school,
                                "name",
                                schema_name,
                            ),
                            "school_schema": (
                                schema_name
                            ),
                            "rating": getattr(
                                feedback,
                                "rating",
                                None,
                            ),
                            "message": (
                                (
                                    getattr(
                                        feedback,
                                        "message",
                                        "",
                                    )
                                    or ""
                                )[:200]
                            ),
                            "status": getattr(
                                feedback,
                                "status",
                                "pending",
                            ),
                            "created_at": getattr(
                                feedback,
                                "created_at",
                                timezone.now(),
                            ),
                            "feedback_type": getattr(
                                feedback,
                                "feedback_type",
                                "general",
                            ),
                        })

                except Exception as error:
                    logger.exception(
                        (
                            "Error retrieving feedback "
                            "from tenant %s: %s"
                        ),
                        school.name,
                        error,
                    )

        except Exception as error:
            logger.exception(
                (
                    "Error accessing tenant schema "
                    "%s: %s"
                ),
                schema_name,
                error,
            )

    # --------------------------------------------------------
    # 3. Sort recent feedback
    # --------------------------------------------------------
    recent_feedback.sort(
        key=lambda item: item["created_at"],
        reverse=True,
    )

    recent_feedback = recent_feedback[:10]

    # --------------------------------------------------------
    # 4. Calculate average rating
    # --------------------------------------------------------
    rated_feedback = [
        feedback
        for feedback in recent_feedback
        if feedback.get("rating") is not None
    ]

    average_rating = 0

    if rated_feedback:
        valid_ratings = []

        for feedback in rated_feedback:
            try:
                valid_ratings.append(
                    float(feedback["rating"])
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

        if valid_ratings:
            average_rating = round(
                sum(valid_ratings)
                / len(valid_ratings),
                1,
            )

    feedback_stats = {
        "total": total_feedback,
        "pending": pending_feedback,
        "resolved": resolved_feedback,
        "average_rating": average_rating,
    }

    # --------------------------------------------------------
    # 5. Render dashboard
    # --------------------------------------------------------
    context = {
        "total_schools": total_schools,
        "active_schools": active_schools,
        "total_domains": total_domains,
        "recent_tenants": recent_tenants,
        "recent_feedback": recent_feedback,
        "total_feedback": total_feedback,
        "pending_feedback": pending_feedback,
        "resolved_feedback": resolved_feedback,
        "feedback_stats": feedback_stats,
        "current_time": timezone.now(),
    }

    return render(
        request,
        "superadmin/dashboard.html",
        context,
    )
