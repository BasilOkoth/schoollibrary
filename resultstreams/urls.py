from django.urls import path

from . import views

app_name = "resultstreams"

urlpatterns = [
    path(
        "result-streams/assignments/",
        views.teaching_assignments,
        name="teaching_assignments",
    ),
    path(
        "result-streams/assignments/<int:assignment_id>/delete/",
        views.delete_teaching_assignment,
        name="delete_teaching_assignment",
    ),
    path(
        "result-streams/entry/<int:exam_id>/<int:subject_id>/<int:class_id>/",
        views.result_stream_entry,
        name="result_stream_entry",
    ),
    path(
        "exam-papers/results/<int:exam_id>/<int:subject_id>/",
        views.paper_result_bridge,
        name="paper_result_bridge",
    ),
]
