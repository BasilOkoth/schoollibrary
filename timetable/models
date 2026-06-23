from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TimetableTemplate(models.Model):
    name = models.CharField(max_length=100, default="Main Timetable")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    show_on_tv = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_timetable_templates",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "name"]

    def __str__(self):
        return self.name


class TimetableDay(models.Model):
    DAY_CHOICES = [
        ("MONDAY", "Monday"),
        ("TUESDAY", "Tuesday"),
        ("WEDNESDAY", "Wednesday"),
        ("THURSDAY", "Thursday"),
        ("FRIDAY", "Friday"),
        ("SATURDAY", "Saturday"),
        ("SUNDAY", "Sunday"),
    ]

    template = models.ForeignKey(
        TimetableTemplate,
        on_delete=models.CASCADE,
        related_name="days",
    )
    day = models.CharField(max_length=20, choices=DAY_CHOICES)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order"]
        unique_together = ("template", "day")

    def __str__(self):
        return f"{self.template.name} - {self.get_day_display()}"


class TimetablePeriod(models.Model):
    PERIOD_TYPE_CHOICES = [
        ("LESSON", "Lesson"),
        ("BREAK", "Break"),
        ("LUNCH", "Lunch"),
        ("ASSEMBLY", "Assembly"),
        ("GAMES", "Games"),
        ("CLUB", "Club"),
        ("PREP", "Prep"),
        ("EXAM", "Exam"),
        ("REMEDIAL", "Remedial"),
        ("OTHER", "Other"),
    ]

    template = models.ForeignKey(
        TimetableTemplate,
        on_delete=models.CASCADE,
        related_name="periods",
    )
    name = models.CharField(max_length=50)
    period_type = models.CharField(
        max_length=20,
        choices=PERIOD_TYPE_CHOICES,
        default="LESSON",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    sort_order = models.PositiveIntegerField(default=0)
    is_teaching_period = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "start_time"]

    def __str__(self):
        return f"{self.name} ({self.start_time} - {self.end_time})"

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError("End time must be later than start time.")


class TimetableRoom(models.Model):
    ROOM_TYPE_CHOICES = [
        ("CLASSROOM", "Classroom"),
        ("LAB", "Laboratory"),
        ("LIBRARY", "Library"),
        ("HALL", "Hall"),
        ("FIELD", "Field / Sports Ground"),
        ("ICT", "ICT Room"),
        ("WORKSHOP", "Workshop"),
        ("OTHER", "Other"),
    ]

    name = models.CharField(max_length=100)
    room_type = models.CharField(
        max_length=20,
        choices=ROOM_TYPE_CHOICES,
        default="CLASSROOM",
    )
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TimetableEntry(models.Model):
    template = models.ForeignKey(
        TimetableTemplate,
        on_delete=models.CASCADE,
        related_name="entries",
    )

    day = models.ForeignKey(
        TimetableDay,
        on_delete=models.CASCADE,
        related_name="entries",
    )

    period = models.ForeignKey(
        TimetablePeriod,
        on_delete=models.CASCADE,
        related_name="entries",
    )

    class_group = models.ForeignKey(
        "digitallibrary.Class",
        on_delete=models.CASCADE,
        related_name="timetable_entries",
    )

    subject = models.ForeignKey(
        "digitallibrary.Subject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_entries",
    )

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_lessons",
    )

    room = models.ForeignKey(
        TimetableRoom,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_entries",
    )

    custom_activity = models.CharField(
        max_length=100,
        blank=True,
        help_text="Use this for Assembly, Games, Clubs, Remedial, Prep, etc.",
    )

    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    show_on_tv = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_timetable_entries",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "day__sort_order",
            "period__sort_order",
            "class_group__name",
        ]
        unique_together = ("template", "day", "period", "class_group")

    def __str__(self):
        return f"{self.class_group} - {self.lesson_title()} - {self.day.day} {self.period.name}"

    def lesson_title(self):
        if self.subject:
            return self.subject.name
        return self.custom_activity or self.period.name

    def clean(self):
        if self.period and self.period.is_teaching_period and not self.subject and not self.custom_activity:
            raise ValidationError("Please select a subject or enter a custom activity.")

        if self.day and self.period and self.day.template_id != self.period.template_id:
            raise ValidationError("The selected day and period must belong to the same timetable template.")

        if self.template and self.day and self.template_id != self.day.template_id:
            raise ValidationError("The selected day must belong to the selected timetable template.")

        if self.template and self.period and self.template_id != self.period.template_id:
            raise ValidationError("The selected period must belong to the selected timetable template.")

        if self.teacher:
            teacher_conflict = TimetableEntry.objects.filter(
                template=self.template,
                day=self.day,
                period=self.period,
                teacher=self.teacher,
                is_active=True,
            ).exclude(pk=self.pk)

            if teacher_conflict.exists():
                raise ValidationError("This teacher already has another lesson at this time.")

        if self.room:
            room_conflict = TimetableEntry.objects.filter(
                template=self.template,
                day=self.day,
                period=self.period,
                room=self.room,
                is_active=True,
            ).exclude(pk=self.pk)

            if room_conflict.exists():
                raise ValidationError("This room is already booked at this time.")


class TimetableTVSetting(models.Model):
    template = models.OneToOneField(
        TimetableTemplate,
        on_delete=models.CASCADE,
        related_name="tv_setting",
    )

    show_current_lessons = models.BooleanField(default=True)
    show_next_lessons = models.BooleanField(default=True)
    show_free_classes = models.BooleanField(default=True)
    show_teacher_names = models.BooleanField(default=True)
    show_rooms = models.BooleanField(default=True)

    refresh_interval_seconds = models.PositiveIntegerField(default=30)

    title = models.CharField(
        max_length=100,
        default="Current Lessons Going On",
    )

    def __str__(self):
        return f"TV Settings - {self.template.name}"
