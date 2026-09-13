# File: timetable/generator_forms.py

from django import forms
from django.contrib.auth import get_user_model

from digitallibrary.models import ClassStream, Subject

from .generator_models import TimetableRequirement
from .models import TimetableRoom


User = get_user_model()


INPUT_CLASS = (
    "w-full bg-gray-900 border border-gray-700 rounded-lg "
    "px-3 py-2 text-white"
)


class TimetableRequirementForm(forms.ModelForm):
    """Configure one weekly teaching requirement."""

    class Meta:
        model = TimetableRequirement
        fields = [
            "class_group",
            "stream",
            "apply_to_all_streams",
            "subject",
            "teacher",
            "room",
            "lessons_per_week",
            "consecutive_periods",
            "lesson_group",
            "parallel_block",
            "notes",
            "is_active",
        ]
        widgets = {
            "class_group": forms.Select(
                attrs={
                    "class": INPUT_CLASS,
                    "id": "id_requirement_class_group",
                }
            ),
            "stream": forms.Select(
                attrs={
                    "class": INPUT_CLASS,
                    "id": "id_requirement_stream",
                }
            ),
            "apply_to_all_streams": forms.CheckboxInput(
                attrs={"class": "rounded border-gray-600 bg-gray-900"}
            ),
            "subject": forms.Select(attrs={"class": INPUT_CLASS}),
            "teacher": forms.Select(attrs={"class": INPUT_CLASS}),
            "room": forms.Select(attrs={"class": INPUT_CLASS}),
            "lessons_per_week": forms.NumberInput(
                attrs={
                    "class": INPUT_CLASS,
                    "min": 1,
                    "max": 20,
                }
            ),
            "consecutive_periods": forms.Select(attrs={"class": INPUT_CLASS}),
            "lesson_group": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "Business option",
                }
            ),
            "parallel_block": forms.TextInput(
                attrs={
                    "class": INPUT_CLASS,
                    "placeholder": "FORM3_OPTIONS",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": INPUT_CLASS,
                    "rows": 2,
                    "placeholder": "Optional scheduling notes",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={"class": "rounded border-gray-600 bg-gray-900"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["stream"].required = False
        self.fields["stream"].empty_label = "Whole Class / No specific stream"
        self.fields["teacher"].required = False
        self.fields["teacher"].empty_label = "Not assigned"
        self.fields["room"].required = False
        self.fields["room"].empty_label = "No fixed room"

        self.fields["subject"].queryset = Subject.objects.filter(
            is_active=True
        ).order_by(
            "result_code",
            "name",
        )
        self.fields["teacher"].queryset = User.objects.filter(
            is_active=True
        ).order_by(
            "first_name",
            "last_name",
            "username",
        )
        self.fields["room"].queryset = TimetableRoom.objects.filter(
            is_active=True
        ).order_by("name")

        selected_class_id = None

        if self.data.get("class_group"):
            selected_class_id = self.data.get("class_group")
        elif self.instance and self.instance.pk:
            selected_class_id = self.instance.class_group_id
        elif self.initial.get("class_group"):
            selected_class_id = self.initial.get("class_group")

        if selected_class_id:
            self.fields["stream"].queryset = ClassStream.objects.filter(
                school_class_id=selected_class_id,
                is_active=True,
            ).select_related(
                "school_class"
            ).order_by(
                "name"
            )
        else:
            self.fields["stream"].queryset = ClassStream.objects.filter(
                is_active=True
            ).select_related(
                "school_class"
            ).order_by(
                "school_class__sort_order",
                "school_class__name",
                "name",
            )

        self.fields["apply_to_all_streams"].label = "Apply to all streams"
        self.fields["lesson_group"].label = "Lesson / Elective Group"
        self.fields["parallel_block"].label = "Parallel Block"

        self.fields["apply_to_all_streams"].help_text = (
            "Use this when the same subject load should be generated separately "
            "for every active stream in the selected class."
        )
        self.fields["lesson_group"].help_text = (
            "Leave blank for a normal lesson. For selective subjects use a "
            "different group name for each option, e.g. Business option."
        )
        self.fields["parallel_block"].help_text = (
            "Subjects with the same block name are generated at exactly the "
            "same time. Example: Business, Agriculture and Computer can all use "
            "FORM3_OPTIONS."
        )

    def clean(self):
        cleaned_data = super().clean()

        class_group = cleaned_data.get("class_group")
        stream = cleaned_data.get("stream")
        apply_to_all_streams = cleaned_data.get("apply_to_all_streams")
        subject = cleaned_data.get("subject")
        lesson_group = (cleaned_data.get("lesson_group") or "").strip()
        parallel_block = (cleaned_data.get("parallel_block") or "").strip()
        lessons_per_week = cleaned_data.get("lessons_per_week")
        consecutive_periods = cleaned_data.get("consecutive_periods")

        if (
            stream
            and class_group
            and stream.school_class_id != class_group.id
        ):
            self.add_error(
                "stream",
                "The selected stream does not belong to the selected class.",
            )

        if apply_to_all_streams and stream:
            self.add_error(
                "stream",
                "Leave Stream blank when Apply to all streams is selected.",
            )

        if parallel_block and not lesson_group and subject:
            cleaned_data["lesson_group"] = f"{subject.name} option"

        if (
            consecutive_periods == 2
            and lessons_per_week
            and lessons_per_week % 2
        ):
            self.add_error(
                "lessons_per_week",
                "Double periods require an even number of weekly periods.",
            )

        cleaned_data["parallel_block"] = parallel_block

        return cleaned_data
