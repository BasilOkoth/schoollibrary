# File: timetable/tests.py

from django.test import SimpleTestCase

from .generator import _scope_conflicts


class TimetableGeneratorScopeRuleTests(SimpleTestCase):

    def test_different_elective_groups_can_share_same_stream_slot(self):
        existing = [
            {
                "stream_id": 10,
                "lesson_group": "business option",
            }
        ]

        self.assertFalse(
            _scope_conflicts(
                existing,
                stream_id=10,
                lesson_group="Agriculture option",
            )
        )

    def test_same_elective_group_cannot_share_same_stream_slot(self):
        existing = [
            {
                "stream_id": 10,
                "lesson_group": "business option",
            }
        ]

        self.assertTrue(
            _scope_conflicts(
                existing,
                stream_id=10,
                lesson_group="Business option",
            )
        )

    def test_default_stream_lesson_conflicts_with_elective_in_same_stream(self):
        existing = [
            {
                "stream_id": 10,
                "lesson_group": "business option",
            }
        ]

        self.assertTrue(
            _scope_conflicts(
                existing,
                stream_id=10,
                lesson_group="",
            )
        )

    def test_whole_class_default_blocks_stream_lesson(self):
        existing = [
            {
                "stream_id": None,
                "lesson_group": "",
            }
        ]

        self.assertTrue(
            _scope_conflicts(
                existing,
                stream_id=10,
                lesson_group="",
            )
        )

    def test_other_stream_does_not_block_stream_specific_lesson(self):
        existing = [
            {
                "stream_id": 11,
                "lesson_group": "",
            }
        ]

        self.assertFalse(
            _scope_conflicts(
                existing,
                stream_id=10,
                lesson_group="",
            )
        )
