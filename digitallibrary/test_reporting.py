# digitallibrary/test_reporting.py
"""Focused regression tests for report generation and result grading."""

from decimal import Decimal

from django.test import SimpleTestCase

from .models import StudentResult
from .reporting import (
    ReportResultRow,
    percentage_for_score,
    progress_for_resolution,
    subject_comment,
)
from .result_grading import (
    GradeResolution,
    fallback_cbe_grade_for_percentage,
    traditional_grade_for_percentage,
)


class ReportPercentageTests(SimpleTestCase):
    def test_score_is_normalized_against_exam_maximum(self):
        self.assertEqual(
            percentage_for_score(30, 50),
            Decimal("60.0"),
        )

    def test_missing_score_is_not_treated_as_zero(self):
        self.assertIsNone(percentage_for_score(None, 100))

    def test_invalid_maximum_does_not_divide_by_zero(self):
        self.assertIsNone(percentage_for_score(30, 0))


    def test_zero_score_is_a_valid_percentage(self):
        self.assertEqual(
            percentage_for_score(0, 100),
            Decimal("0.0"),
        )

class CurriculumGradingTests(SimpleTestCase):
    def test_legacy_thirty_percent_is_d_minus(self):
        resolution = traditional_grade_for_percentage(30)
        self.assertEqual(resolution.label, "D-")
        self.assertEqual(resolution.points, Decimal("2"))

    def test_cbe_thirty_percent_is_approaching_expectations(self):
        resolution = fallback_cbe_grade_for_percentage(30)
        self.assertEqual(resolution.label, "AE2")

    def test_progress_comes_from_resolved_grade(self):
        resolution = GradeResolution(
            label="D-",
            points=Decimal("2"),
            remark="D- - Very Weak",
            system_code="traditional",
        )
        progress, band = progress_for_resolution(resolution)
        self.assertEqual(progress, "Needs Support")
        self.assertEqual(band, "support")


class ReportCommentTests(SimpleTestCase):
    def test_critical_comment_does_not_use_positive_fallback(self):
        comment = subject_comment("Chemistry", "Critical")
        self.assertIn("critically below", comment.lower())
        self.assertNotIn("good effort", comment.lower())


class StudentResultStructureTests(SimpleTestCase):
    def test_unified_result_metadata_fields_exist(self):
        field_names = {
            field.name
            for field in StudentResult._meta.get_fields()
        }
        self.assertTrue(
            {
                "grade_label",
                "grading_system_used",
                "teacher_comment",
            }.issubset(field_names)
        )

class RegisteredSubjectReportTests(SimpleTestCase):
    def test_pending_registered_subject_is_not_treated_as_zero(self):
        row = ReportResultRow(
            result_id=None,
            subject=object(),
            score=None,
            max_score=Decimal("100"),
            percentage=None,
            grade="—",
            points=None,
            progress="Pending",
            performance_band="pending",
            subject_position=None,
            subject_size=0,
            teacher_comment="Result not entered.",
            status="Pending",
            is_entered=False,
        )

        self.assertFalse(row.is_entered)
        self.assertIsNone(row.score)
        self.assertIsNone(row.percentage)
        self.assertEqual(row.status, "Pending")

