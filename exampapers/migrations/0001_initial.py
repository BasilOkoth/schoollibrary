import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('digitallibrary', '0031_classteacherassignment_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamSubjectPaper',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('paper_name', models.CharField(help_text='Example: Paper 1, Paper 2, Practical or Oral.', max_length=80)),
                ('max_marks', models.DecimalField(decimal_places=2, help_text='Maximum marks for this paper. Examples: 40, 50, 80, 90 or 100.', max_digits=7, validators=[django.core.validators.MinValueValidator(Decimal('0.01')), django.core.validators.MaxValueValidator(Decimal('1000.00'))])),
                ('order', models.PositiveSmallIntegerField(default=1, help_text='The order in which this paper appears.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='configured_exam_papers', to=settings.AUTH_USER_MODEL)),
                ('exam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='configured_subject_papers', to='digitallibrary.exam')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='configured_exam_papers', to='digitallibrary.subject')),
            ],
            options={
                'ordering': ['subject__name', 'order', 'paper_name'],
            },
        ),
        migrations.CreateModel(
            name='StudentPaperMark',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('raw_score', models.DecimalField(decimal_places=2, max_digits=7, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('entered_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='entered_exam_paper_marks', to=settings.AUTH_USER_MODEL)),
                ('paper', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='student_marks', to='exampapers.examsubjectpaper')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_paper_marks', to='digitallibrary.student')),
            ],
            options={
                'ordering': ['paper__order', 'paper__paper_name'],
            },
        ),
        migrations.AddIndex(
            model_name='examsubjectpaper',
            index=models.Index(fields=['exam', 'subject', 'order'], name='exam_subject_paper_lookup_idx'),
        ),
        migrations.AddConstraint(
            model_name='examsubjectpaper',
            constraint=models.UniqueConstraint(fields=('exam', 'subject', 'paper_name'), name='unique_exam_subject_paper_name'),
        ),
        migrations.AddConstraint(
            model_name='examsubjectpaper',
            constraint=models.CheckConstraint(condition=models.Q(('max_marks__gt', 0)), name='exam_subject_paper_max_marks_positive'),
        ),
        migrations.AddIndex(
            model_name='studentpapermark',
            index=models.Index(fields=['student', 'paper'], name='student_paper_mark_lookup_idx'),
        ),
        migrations.AddConstraint(
            model_name='studentpapermark',
            constraint=models.UniqueConstraint(fields=('student', 'paper'), name='unique_student_mark_per_exam_paper'),
        ),
        migrations.AddConstraint(
            model_name='studentpapermark',
            constraint=models.CheckConstraint(condition=models.Q(('raw_score__gte', 0)), name='student_paper_mark_nonnegative'),
        ),
    ]
