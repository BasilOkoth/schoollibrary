import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('digitallibrary', '0030_add_teacher_return_file'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClassTeacherAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stream_name', models.CharField(blank=True, default='', help_text='Leave blank for whole-class assignment; use values like East, West, A, Blue for streams.', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['class_obj__name', 'stream_name'],
            },
        ),
        migrations.CreateModel(
            name='FeePaymentSettingChangeRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('proposed_business_name', models.CharField(blank=True, max_length=150)),
                ('proposed_paybill_number', models.CharField(blank=True, max_length=30)),
                ('proposed_account_reference_format', models.CharField(blank=True, default='Use the student admission number as the account number.', max_length=255)),
                ('proposed_parent_payment_notes', models.TextField(blank=True)),
                ('proposed_payment_prompt_enabled', models.BooleanField(default=True)),
                ('reason', models.TextField(blank=True, help_text='Reason for changing the school fee payment settings.')),
                ('status', models.CharField(choices=[('pending', 'Pending Approval'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('applied', 'Applied')], db_index=True, default='pending', max_length=20)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('principal_approved_at', models.DateTimeField(blank=True, null=True)),
                ('admin_approved_at', models.DateTimeField(blank=True, null=True)),
                ('rejected_at', models.DateTimeField(blank=True, null=True)),
                ('rejection_reason', models.TextField(blank=True)),
                ('applied_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-requested_at'],
            },
        ),
        migrations.CreateModel(
            name='SMSWallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='default', max_length=50, unique=True)),
                ('currency', models.CharField(default='KES', max_length=10)),
                ('balance', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('sms_unit_cost', models.DecimalField(decimal_places=2, default=Decimal('1.50'), help_text='Cost per SMS unit', max_digits=8)),
                ('low_balance_threshold', models.DecimalField(decimal_places=2, default=Decimal('100.00'), help_text='Show warning when balance is below this amount', max_digits=12)),
                ('credit_limit', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Optional negative allowance. Keep 0 for strict prepaid SMS.', max_digits=12)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'SMS Wallet',
                'verbose_name_plural': 'SMS Wallets',
            },
        ),
        migrations.CreateModel(
            name='SMSWalletTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(choices=[('credit', 'Credit / Top Up'), ('debit', 'Debit / SMS Used'), ('refund', 'Refund'), ('adjustment', 'Adjustment')], max_length=20)),
                ('source', models.CharField(choices=[('manual_topup', 'Manual Top Up'), ('parent_bulk', 'Bulk SMS to Parents'), ('staff_sms', 'SMS to Staff'), ('test_sms', 'Test SMS'), ('parent_otp', 'Parent Portal OTP'), ('system', 'System')], default='system', max_length=30)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('sms_units', models.PositiveIntegerField(default=0)),
                ('recipient_count', models.PositiveIntegerField(default=0)),
                ('balance_before', models.DecimalField(decimal_places=2, max_digits=12)),
                ('balance_after', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reference', models.CharField(blank=True, max_length=100, null=True)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='StudentEnrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('academic_year', models.CharField(db_index=True, help_text='Example: 2026 or 2026-2027', max_length=9)),
                ('pathway', models.CharField(blank=True, help_text='Used mainly for Grade 10, Grade 11 and Grade 12.', max_length=30, null=True)),
                ('is_current', models.BooleanField(db_index=True, default=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('promoted', 'Promoted'), ('repeated', 'Repeated'), ('completed', 'Completed'), ('transferred', 'Transferred'), ('inactive', 'Inactive')], db_index=True, default='active', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-academic_year', 'student_class__sort_order', 'student__last_name', 'student__first_name'],
            },
        ),
        migrations.CreateModel(
            name='StudentEnrollmentSubject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('academic_year', models.CharField(db_index=True, max_length=9)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['subject__result_code', 'subject__name'],
            },
        ),
        migrations.AlterModelOptions(
            name='classaccesscode',
            options={'ordering': ['school_class__name', 'stream__name', 'code']},
        ),
        migrations.AlterModelOptions(
            name='studentsubject',
            options={'ordering': ['student__current_class__name', 'student__first_name', 'student__last_name', 'subject__result_code', 'subject__name']},
        ),
        migrations.AlterModelOptions(
            name='subject',
            options={'ordering': ['result_code', 'category', 'order', 'name'], 'verbose_name': 'Subject', 'verbose_name_plural': 'Subjects'},
        ),
        migrations.RenameField(
            model_name='studentsubject',
            old_name='registered_at',
            new_name='created_at',
        ),
        migrations.AlterUniqueTogether(
            name='studentsubject',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='smslog',
            name='cost',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10),
        ),
        migrations.AddField(
            model_name='smslog',
            name='error_message',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='smslog',
            name='sms_units',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='smslog',
            name='source',
            field=models.CharField(choices=[('parent_bulk', 'Bulk SMS to Parents'), ('staff_sms', 'SMS to Staff'), ('test_sms', 'Test SMS'), ('parent_otp', 'Parent Portal OTP'), ('manual', 'Manual SMS')], default='manual', max_length=30),
        ),
        migrations.AddField(
            model_name='studentsubject',
            name='academic_year',
            field=models.CharField(blank=True, db_index=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='studentsubject',
            name='is_active',
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name='subject',
            name='result_code',
            field=models.PositiveIntegerField(blank=True, db_index=True, help_text='Numeric subject code used for results entry and report card ordering, e.g. 101, 102, 121.', null=True),
        ),
        migrations.AddField(
            model_name='tvcontent',
            name='external_video_url',
            field=models.URLField(blank=True, help_text='Optional external video link such as YouTube, Google Drive, Vimeo, or other hosted video.', null=True),
        ),
        migrations.AlterField(
            model_name='assignmentsubmission',
            name='submitted_file',
            field=models.FileField(help_text='File submitted by the student.', upload_to='assignment_submissions/%Y/%m/'),
        ),
        migrations.AlterField(
            model_name='assignmentsubmission',
            name='teacher',
            field=models.ForeignKey(blank=True, help_text='Teacher who marked or returned the assignment.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='received_assignment_submissions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='assignmentsubmission',
            name='teacher_comment',
            field=models.TextField(blank=True, help_text='Teacher feedback visible to the student.'),
        ),
        migrations.AlterField(
            model_name='classaccesscode',
            name='code',
            field=models.CharField(db_index=True, max_length=80, unique=True),
        ),
        migrations.AlterField(
            model_name='classaccesscode',
            name='stream',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='access_codes', to='digitallibrary.classstream'),
        ),
        migrations.AlterField(
            model_name='feepaymentsetting',
            name='account_reference_format',
            field=models.CharField(blank=True, default='Use the student admission number as the account number.', help_text='Instructions shown to parents for account/reference number.', max_length=255),
        ),
        migrations.AlterField(
            model_name='feepaymentsetting',
            name='auto_update_enabled',
            field=models.BooleanField(default=True, help_text='Automatically update fee balance after confirmed payment.'),
        ),
        migrations.AlterField(
            model_name='feepaymentsetting',
            name='business_name',
            field=models.CharField(blank=True, help_text='School/business name shown to parents.', max_length=150),
        ),
        migrations.AlterField(
            model_name='feepaymentsetting',
            name='parent_payment_notes',
            field=models.TextField(blank=True, help_text='Extra payment instructions shown to parents.'),
        ),
        migrations.AlterField(
            model_name='feepaymentsetting',
            name='paybill_number',
            field=models.CharField(blank=True, help_text='School PayBill number used for fee payments.', max_length=30),
        ),
        migrations.AlterField(
            model_name='feepaymentsetting',
            name='payment_prompt_enabled',
            field=models.BooleanField(default=True, help_text='Show PayBill prompt in parent portal fee pages.'),
        ),
        migrations.AlterField(
            model_name='resource',
            name='allow_submission',
            field=models.BooleanField(default=False, help_text='Allow students to submit completed work online.'),
        ),
        migrations.AlterField(
            model_name='resource',
            name='assigned_class',
            field=models.ForeignKey(blank=True, help_text='Class this assignment/CAT/exam is meant for.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_resources', to='digitallibrary.class'),
        ),
        migrations.AlterField(
            model_name='resource',
            name='assigned_stream',
            field=models.ForeignKey(blank=True, help_text='Optional stream. Leave blank if it applies to all streams.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_resources', to='digitallibrary.classstream'),
        ),
        migrations.AlterField(
            model_name='resource',
            name='due_date',
            field=models.DateTimeField(blank=True, help_text='Deadline for assignment/CAT/exam submission.', null=True),
        ),
        migrations.AlterField(
            model_name='resource',
            name='file_type',
            field=models.CharField(choices=[('PDF', 'PDF'), ('DOC', 'Word Document'), ('VIDEO', 'Video'), ('OTHER', 'Other')], default='PDF', help_text='The physical file format, e.g. PDF, Word, Video or Other.', max_length=20),
        ),
        migrations.AlterField(
            model_name='resource',
            name='paper_type',
            field=models.CharField(choices=[('Paper 1', 'Paper 1'), ('Paper 2', 'Paper 2'), ('Paper 3', 'Paper 3'), ('Practical', 'Practical'), ('Marking Scheme', 'Marking Scheme'), ('Revision', 'Revision'), ('Notes', 'Notes'), ('N/A', 'General Resource')], default='N/A', max_length=30),
        ),
        migrations.AlterField(
            model_name='resource',
            name='posted_by',
            field=models.ForeignKey(blank=True, help_text='Teacher/staff member who posted this assignment/CAT/exam.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='posted_resources', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='resource',
            name='resource_type',
            field=models.CharField(choices=[('notes', 'Notes'), ('revision', 'Revision Paper'), ('assignment', 'Assignment'), ('cat', 'CAT'), ('exam', 'Exam')], db_index=True, default='notes', help_text='Choose whether this is Notes, Revision, Assignment, CAT or Exam.', max_length=30),
        ),
        migrations.AlterField(
            model_name='resource',
            name='uploaded_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_resources', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='smslog',
            name='category',
            field=models.CharField(default='general', max_length=50),
        ),
        migrations.AlterField(
            model_name='smslog',
            name='recipient',
            field=models.CharField(max_length=30),
        ),
        migrations.AlterField(
            model_name='smslog',
            name='recipient_name',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='smslog',
            name='sent_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sent_sms_logs', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='smslog',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('mock', 'Mock Sent')], default='pending', max_length=20),
        ),
        migrations.AlterField(
            model_name='studentactionlog',
            name='action',
            field=models.CharField(choices=[('created', 'Created'), ('enrolled', 'Enrolled'), ('promoted', 'Promoted'), ('repeated', 'Repeated'), ('transferred', 'Transferred Out'), ('graduated', 'Graduated'), ('suspended', 'Suspended'), ('reactivated', 'Reactivated'), ('deactivated', 'Deactivated'), ('archived', 'Archived'), ('updated', 'Information Updated')], max_length=20),
        ),
        migrations.AlterField(
            model_name='studentsubject',
            name='subject',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_assignments', to='digitallibrary.subject'),
        ),
        migrations.AlterField(
            model_name='subject',
            name='code',
            field=models.CharField(blank=True, help_text='Subject short code (e.g., MATH, ENG)', max_length=20, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='tvcontent',
            name='content_type',
            field=models.CharField(choices=[('announcement', '📢 Announcement'), ('event', '📅 Upcoming Event'), ('exam', '📝 Exam Schedule'), ('achievement', '🏆 Achievement'), ('quote', '💡 Quote of the Day'), ('notice', '📋 Notice Board'), ('reminder', '⏰ Reminder'), ('emergency', '🚨 Emergency Alert'), ('slide', '🖼️ Image Slide'), ('video', '🎬 Video Clip')], default='announcement', max_length=20),
        ),
        migrations.AlterField(
            model_name='tvcontent',
            name='image',
            field=models.ImageField(blank=True, help_text='Upload image/photo: JPEG, PNG, GIF, WebP.', null=True, upload_to='tv_content/%Y/%m/%d/', verbose_name='Upload Photo/Image'),
        ),
        migrations.AlterField(
            model_name='tvcontent',
            name='image_url',
            field=models.URLField(blank=True, help_text='External image URL. Optional.', null=True),
        ),
        migrations.AlterField(
            model_name='tvcontent',
            name='message',
            field=models.TextField(blank=True, help_text='Content message. Optional for image slides and videos.', null=True),
        ),
        migrations.AlterField(
            model_name='tvcontent',
            name='video',
            field=models.FileField(blank=True, help_text='Upload video clip: MP4, WebM, MOV, or M4V. Recommended max 200MB.', null=True, upload_to='tv_videos/%Y/%m/%d/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['mp4', 'webm', 'mov', 'm4v'])], verbose_name='Upload Video'),
        ),
        migrations.AlterUniqueTogether(
            name='studentsubject',
            unique_together={('student', 'subject', 'academic_year')},
        ),
        migrations.AddIndex(
            model_name='resource',
            index=models.Index(fields=['resource_type'], name='digitallibr_resourc_b91fe1_idx'),
        ),
        migrations.AddIndex(
            model_name='resource',
            index=models.Index(fields=['assigned_class'], name='digitallibr_assigne_6be41e_idx'),
        ),
        migrations.AddIndex(
            model_name='resource',
            index=models.Index(fields=['assigned_stream'], name='digitallibr_assigne_853cca_idx'),
        ),
        migrations.AddIndex(
            model_name='studentsubject',
            index=models.Index(fields=['student', 'academic_year'], name='digitallibr_student_a395ec_idx'),
        ),
        migrations.AddIndex(
            model_name='studentsubject',
            index=models.Index(fields=['subject', 'academic_year'], name='digitallibr_subject_0fcad8_idx'),
        ),
        migrations.AddIndex(
            model_name='studentsubject',
            index=models.Index(fields=['is_active'], name='digitallibr_is_acti_452426_idx'),
        ),
        migrations.AddIndex(
            model_name='subject',
            index=models.Index(fields=['result_code'], name='digitallibr_result__f0e627_idx'),
        ),
        migrations.AddField(
            model_name='classteacherassignment',
            name='class_obj',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_assignments', to='digitallibrary.class'),
        ),
        migrations.AddField(
            model_name='classteacherassignment',
            name='class_teacher',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='class_stream_assignments', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='feepaymentsettingchangerequest',
            name='admin_approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='admin_fee_setting_approvals', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='feepaymentsettingchangerequest',
            name='applied_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='applied_fee_setting_changes', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='feepaymentsettingchangerequest',
            name='principal_approved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='principal_fee_setting_approvals', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='feepaymentsettingchangerequest',
            name='rejected_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rejected_fee_setting_changes', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='feepaymentsettingchangerequest',
            name='requested_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='fee_setting_change_requests', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='smslog',
            name='wallet',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sms_logs', to='digitallibrary.smswallet'),
        ),
        migrations.AddIndex(
            model_name='smslog',
            index=models.Index(fields=['status', 'created_at'], name='digitallibr_status_9cb530_idx'),
        ),
        migrations.AddIndex(
            model_name='smslog',
            index=models.Index(fields=['source', 'created_at'], name='digitallibr_source_0c32ab_idx'),
        ),
        migrations.AddIndex(
            model_name='smslog',
            index=models.Index(fields=['recipient'], name='digitallibr_recipie_49654d_idx'),
        ),
        migrations.AddField(
            model_name='smswallettransaction',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sms_wallet_transactions', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='smswallettransaction',
            name='wallet',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='digitallibrary.smswallet'),
        ),
        migrations.AddField(
            model_name='studentenrollment',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_student_enrollments', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='studentenrollment',
            name='promoted_from',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='promoted_to', to='digitallibrary.studentenrollment'),
        ),
        migrations.AddField(
            model_name='studentenrollment',
            name='stream',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_enrollments', to='digitallibrary.classstream'),
        ),
        migrations.AddField(
            model_name='studentenrollment',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='digitallibrary.student'),
        ),
        migrations.AddField(
            model_name='studentenrollment',
            name='student_class',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='student_enrollments', to='digitallibrary.class'),
        ),
        migrations.AddField(
            model_name='studentenrollmentsubject',
            name='enrollment',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollment_subjects', to='digitallibrary.studentenrollment'),
        ),
        migrations.AddField(
            model_name='studentenrollmentsubject',
            name='student',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollment_subjects', to='digitallibrary.student'),
        ),
        migrations.AddField(
            model_name='studentenrollmentsubject',
            name='subject',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='enrollment_students', to='digitallibrary.subject'),
        ),
        migrations.AlterUniqueTogether(
            name='classteacherassignment',
            unique_together={('class_obj', 'stream_name')},
        ),
        migrations.AddIndex(
            model_name='feepaymentsettingchangerequest',
            index=models.Index(fields=['status'], name='digitallibr_status_97472b_idx'),
        ),
        migrations.AddIndex(
            model_name='feepaymentsettingchangerequest',
            index=models.Index(fields=['requested_at'], name='digitallibr_request_4728ac_idx'),
        ),
        migrations.AddIndex(
            model_name='smswallettransaction',
            index=models.Index(fields=['transaction_type', 'created_at'], name='digitallibr_transac_00b4d2_idx'),
        ),
        migrations.AddIndex(
            model_name='smswallettransaction',
            index=models.Index(fields=['source', 'created_at'], name='digitallibr_source_98011e_idx'),
        ),
        migrations.AddIndex(
            model_name='studentenrollment',
            index=models.Index(fields=['student', 'academic_year'], name='digitallibr_student_694a0c_idx'),
        ),
        migrations.AddIndex(
            model_name='studentenrollment',
            index=models.Index(fields=['student_class', 'academic_year'], name='digitallibr_student_626bcd_idx'),
        ),
        migrations.AddIndex(
            model_name='studentenrollment',
            index=models.Index(fields=['is_current', 'status'], name='digitallibr_is_curr_60acdd_idx'),
        ),
        migrations.AddConstraint(
            model_name='studentenrollment',
            constraint=models.UniqueConstraint(fields=('student', 'academic_year'), name='unique_student_enrollment_per_academic_year'),
        ),
        migrations.AddIndex(
            model_name='studentenrollmentsubject',
            index=models.Index(fields=['student', 'academic_year'], name='digitallibr_student_c0cad5_idx'),
        ),
        migrations.AddIndex(
            model_name='studentenrollmentsubject',
            index=models.Index(fields=['enrollment', 'is_active'], name='digitallibr_enrollm_c610e7_idx'),
        ),
        migrations.AddConstraint(
            model_name='studentenrollmentsubject',
            constraint=models.UniqueConstraint(fields=('enrollment', 'subject'), name='unique_subject_per_student_enrollment'),
        ),
    ]
