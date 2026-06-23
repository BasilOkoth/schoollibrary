from django import forms

from .models import (
    TimetableTemplate,
    TimetableDay,
    TimetablePeriod,
    TimetableRoom,
    TimetableEntry,
)


class TimetableTemplateForm(forms.ModelForm):
    class Meta:
        model = TimetableTemplate
        fields = [
            "name",
            "description",
            "is_active",
            "show_on_tv",
        ]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
                "placeholder": "Main Timetable",
            }),
            "description": forms.Textarea(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
                "rows": 3,
                "placeholder": "Optional description",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "rounded border-gray-600 bg-gray-900",
            }),
            "show_on_tv": forms.CheckboxInput(attrs={
                "class": "rounded border-gray-600 bg-gray-900",
            }),
        }


class TimetableDayForm(forms.ModelForm):
    class Meta:
        model = TimetableDay
        fields = [
            "template",
            "day",
            "sort_order",
            "is_active",
        ]

        widgets = {
            "template": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "day": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "sort_order": forms.NumberInput(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "rounded border-gray-600 bg-gray-900",
            }),
        }


class TimetablePeriodForm(forms.ModelForm):
    class Meta:
        model = TimetablePeriod
        fields = [
            "template",
            "name",
            "period_type",
            "start_time",
            "end_time",
            "sort_order",
            "is_teaching_period",
            "is_active",
        ]

        widgets = {
            "template": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "name": forms.TextInput(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
                "placeholder": "Period 1",
            }),
            "period_type": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "start_time": forms.TimeInput(attrs={
                "type": "time",
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "end_time": forms.TimeInput(attrs={
                "type": "time",
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "sort_order": forms.NumberInput(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "is_teaching_period": forms.CheckboxInput(attrs={
                "class": "rounded border-gray-600 bg-gray-900",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "rounded border-gray-600 bg-gray-900",
            }),
        }


class TimetableRoomForm(forms.ModelForm):
    class Meta:
        model = TimetableRoom
        fields = [
            "name",
            "room_type",
            "capacity",
            "is_active",
        ]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
                "placeholder": "Room 1, Lab, Hall",
            }),
            "room_type": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "capacity": forms.NumberInput(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
                "placeholder": "Optional",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "rounded border-gray-600 bg-gray-900",
            }),
        }


class TimetableEntryForm(forms.ModelForm):
    class Meta:
        model = TimetableEntry
        fields = [
            "template",
            "day",
            "period",
            "class_group",
            "subject",
            "teacher",
            "room",
            "custom_activity",
            "notes",
            "is_active",
            "show_on_tv",
        ]

        widgets = {
            "template": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "day": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "period": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "class_group": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "subject": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "teacher": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "room": forms.Select(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
            }),
            "custom_activity": forms.TextInput(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
                "placeholder": "Assembly, Games, Club, Remedial, Prep",
            }),
            "notes": forms.Textarea(attrs={
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white",
                "rows": 3,
                "placeholder": "Optional notes",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "rounded border-gray-600 bg-gray-900",
            }),
            "show_on_tv": forms.CheckboxInput(attrs={
                "class": "rounded border-gray-600 bg-gray-900",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        active_template = TimetableTemplate.objects.filter(is_active=True).first()

        if active_template:
            self.fields["template"].initial = active_template
            self.fields["day"].queryset = TimetableDay.objects.filter(
                template=active_template,
                is_active=True,
            ).order_by("sort_order")
            self.fields["period"].queryset = TimetablePeriod.objects.filter(
                template=active_template,
                is_active=True,
            ).order_by("sort_order", "start_time")
        else:
            self.fields["day"].queryset = TimetableDay.objects.none()
            self.fields["period"].queryset = TimetablePeriod.objects.none()

        self.fields["subject"].required = False
        self.fields["teacher"].required = False
        self.fields["room"].required = False
        self.fields["custom_activity"].required = False
        self.fields["notes"].required = False
