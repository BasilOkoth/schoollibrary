from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from digitallibrary.models import Class, ClassStream, Subject

from .models import TeachingAssignment


TEXT_INPUT_CLASSES = (
    "w-full rounded-xl border border-slate-700 bg-slate-950 "
    "px-3 py-2.5 text-sm font-semibold text-slate-100 "
    "outline-none focus:border-emerald-500"
)

SELECT_CLASSES = (
    "w-full rounded-xl border border-slate-700 bg-slate-950 "
    "px-3 py-2.5 text-sm font-semibold text-slate-100 "
    "outline-none focus:border-emerald-500"
)


class TeachingAssignmentForm(forms.ModelForm):
    class Meta:
        model = TeachingAssignment
        fields = [
            "teacher",
            "subject",
            "school_class",
            "stream",
            "academic_year",
            "is_active",
        ]

        widgets = {
            "teacher": forms.Select(attrs={"class": SELECT_CLASSES}),
            "subject": forms.Select(attrs={"class": SELECT_CLASSES}),
            "school_class": forms.Select(attrs={"class": SELECT_CLASSES}),
            "stream": forms.Select(attrs={"class": SELECT_CLASSES}),
            "academic_year": forms.TextInput(
                attrs={
                    "class": TEXT_INPUT_CLASSES,
                    "placeholder": "2026",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": (
                        "h-4 w-4 rounded border-slate-600 "
                        "bg-slate-900 text-emerald-500"
                    )
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        User = get_user_model()

        self.fields["teacher"].queryset = (
            User.objects.filter(
                is_active=True,
                profile__role__in=["teacher", "class_teacher"],
            )
            .distinct()
            .order_by("first_name", "last_name", "username")
        )

        self.fields["subject"].queryset = Subject.objects.filter(
            is_active=True
        ).order_by("result_code", "name")

        self.fields["school_class"].queryset = Class.objects.all().order_by(
            "sort_order", "name"
        )

        # Display every active stream. ClassStream.__str__ already includes
        # the class name, and model validation prevents a mismatched class.
        self.fields["stream"].queryset = ClassStream.objects.filter(
            is_active=True
        ).order_by("school_class__sort_order", "school_class__name", "name")
        self.fields["stream"].required = False
        self.fields["stream"].empty_label = "--- All streams in this class ---"

        if not self.is_bound and not self.instance.pk:
            self.fields["academic_year"].initial = str(timezone.now().year)

    def clean(self):
        cleaned_data = super().clean()
        school_class = cleaned_data.get("school_class")
        stream = cleaned_data.get("stream")

        if (
            school_class
            and stream
            and stream.school_class_id != school_class.id
        ):
            self.add_error(
                "stream",
                "The selected stream does not belong to the selected class.",
            )

        return cleaned_data
