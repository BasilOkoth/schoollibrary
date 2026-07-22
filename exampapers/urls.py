from django.urls import path

from . import component_views
from . import views


app_name = "exampapers"


urlpatterns = [
    path(
        "exam-papers/configure/"
        "<int:exam_id>/"
        "<int:subject_id>/",
        component_views.configure_components,
        name="configure_papers",
    ),

    path(
        "exam-papers/results/"
        "<int:exam_id>/"
        "<int:subject_id>/",
        views.enter_paper_marks,
        name="enter_paper_marks",
    ),
]
