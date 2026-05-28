# digitallibrary/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.db import connection
from digitallibrary.views import landing_page
from . import views
from . import views_backup
from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


def health_check(request):
    return HttpResponse("OK")


def debug_tenant(request):
    """Debug view to check tenant detection and authentication"""
    from django.db import connection
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tenant Debug Info</title>
        <style>
            body {{ font-family: monospace; padding: 20px; background: #1a1a2e; color: #eee; }}
            h1 {{ color: #10b981; }}
            .info {{ background: #16213e; padding: 15px; border-radius: 10px; margin: 10px 0; }}
            .success {{ color: #10b981; }}
            .error {{ color: #ef4444; }}
            table {{ width: 100%; border-collapse: collapse; }}
            td {{ padding: 8px; border-bottom: 1px solid #333; }}
            td:first-child {{ font-weight: bold; width: 200px; }}
        </style>
    </head>
    <body>
        <h1>🔍 Tenant Debug Information</h1>
        
        <div class="info">
            <h2>📊 Database Schema</h2>
            <table>
                <tr><td>Current Schema:</td><td class="{'success' if connection.schema_name == 'demo' else 'error'}">{connection.schema_name}</td></tr>
                <tr><td>Expected Schema:</td><td>demo</td></tr>
            </table>
        </div>
        
        <div class="info">
            <h2>👤 Authentication Status</h2>
            <table>
                <tr><td>Is Authenticated:</td><td class="{'success' if request.user.is_authenticated else 'error'}">{request.user.is_authenticated}</td></tr>
                <tr><td>Username:</td><td>{request.user.username if request.user.is_authenticated else 'Anonymous'}</td></tr>
                <tr><td>User ID:</td><td>{request.user.id if request.user.is_authenticated else 'N/A'}</td></tr>
                <tr><td>Is Staff:</td><td>{request.user.is_staff if request.user.is_authenticated else 'N/A'}</td></tr>
                <tr><td>Is Superuser:</td><td>{request.user.is_superuser if request.user.is_authenticated else 'N/A'}</td></tr>
            </table>
        </div>
        
        <div class="info">
            <h2>🏢 Tenant Information</h2>
            <table>
                <tr><td>Has Tenant Attribute:</td><td>{hasattr(request, 'tenant')}</td></tr>
                <tr><td>Tenant Schema:</td><td>{request.tenant.schema_name if hasattr(request, 'tenant') and request.tenant else 'None'}</td></tr>
                <tr><td>Tenant Name:</td><td>{request.tenant.name if hasattr(request, 'tenant') and request.tenant else 'None'}</td></tr>
            </table>
        </div>
        
        <div class="info">
            <h2>🌐 Request Information</h2>
            <table>
                <tr><td>Path:</td><td>{request.path}</td></tr>
                <tr><td>Method:</td><td>{request.method}</td></tr>
                <tr><td>Host:</td><td>{request.get_host()}</td></tr>
                <tr><td>Session Key:</td><td>{request.session.session_key}</td></tr>
            </table>
        </div>
        
        <div class="info">
            <h2>🔗 Useful Links</h2>
            <ul>
                <li><a href="/tenant/demo/app/login/" style="color: #10b981;">Login Page</a></li>
                <li><a href="/tenant/demo/app/dashboard/" style="color: #10b981;">Dashboard</a></li>
                <li><a href="/tenant/demo/admin/" style="color: #10b981;">Django Admin</a></li>
                <li><a href="/tenant/demo/app/logout/" style="color: #ef4444;">Logout</a></li>
            </ul>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html)


def simple_test(request):
    """Simple test view that doesn't require login"""
    from django.db import connection
    return HttpResponse(f"""
    <!DOCTYPE html>
    <html>
    <head><title>Simple Test</title></head>
    <body>
        <h1>✅ Simple Test Works!</h1>
        <p>Current Schema: <strong>{connection.schema_name}</strong></p>
        <p>Path: {request.path}</p>
        <p>This proves the URL routing is working!</p>
        <hr>
        <p>Now try: <a href="/tenant/demo/app/debug/">Debug Page</a></p>
    </body>
    </html>
    """)


app_name = 'digitallibrary'

urlpatterns = [
    # ========== DEBUG & TEST - MUST BE FIRST ==========
    path('simple-test/', simple_test, name='simple_test'),
    path('debug/', debug_tenant, name='debug_tenant'),
    
    # ========== HOME - FIXED ==========
    # The root path for tenant should go to dashboard or app_home, NOT landing_page!
    path('', login_required(views.admin_dashboard), name='tenant_root'),
    path('dashboard/', login_required(views.admin_dashboard), name='dashboard'),
    path('app/', login_required(views.admin_dashboard), name='app_home'),
    
    # Public landing page - only accessible at /landing/ or root domain
    path('landing-page/', landing_page, name='landing_page'),
    
    # ========== AUTHENTICATION ==========
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # ========== LIBRARY RESOURCES ==========
    path('library/', views.library_list, name='library_list'),
    path('resource/<int:pk>/', views.resource_detail, name='resource_detail'),
    
    # ========== TEACHER UPLOADS ==========
    path('upload/', views.upload_resource, name='upload_resource'),
    path('my-uploads/', views.my_uploads, name='my_uploads'),
    path('edit-resource/<int:pk>/', views.edit_my_resource, name='edit_my_resource'),
    path('delete-resource/<int:pk>/', views.delete_my_resource, name='delete_my_resource'),
    path('healthz/', health_check, name='health_check'),
    
    # ========== AI SEARCH ==========
    path('ai-search/', views.ai_search_page, name='ai_search_page'),
    
    # ========== PRINTING PORTAL ==========
    path('print/', views.printing_portal, name='printing_portal'),
    path('printing/request/', views.printing_portal, name='printing_portal_alias'),
    path('printing/mark-downloaded/<int:job_id>/', views.mark_as_downloaded, name='mark_downloaded'),
    path('printing/mark-completed/<int:job_id>/', views.mark_as_completed, name='mark_completed'),
    path('printing/job/<int:job_id>/', views.print_job_detail, name='print_job_detail'),
    path('printing/download/<int:job_id>/', views.download_print_file, name='download_print_file'),
    
    # ========== LIBRARY ADMIN ==========
    path('admin-library/dashboard/', views.library_admin_dashboard, name='library_admin_dashboard'),
    path('library-admin/', views.library_admin_dashboard, name='library_admin_dashboard_alias'),
    path('library-admin/resources/', views.library_admin_resources, name='library_admin_resources'),
    path('library-admin/resources/add/', views.library_admin_resource_edit, name='library_admin_resource_add'),
    path('library-admin/resources/<int:pk>/edit/', views.library_admin_resource_edit, name='library_admin_resource_edit'),
    path('library-admin/resources/<int:pk>/delete/', views.library_admin_resource_delete, name='library_admin_resource_delete'),
    path('library-admin/announcements/', views.library_admin_announcements, name='library_admin_announcements'),
    path('library-admin/announcements/add/', views.library_admin_announcement_add, name='library_admin_announcement_add'),
    path('library-admin/announcements/<int:pk>/edit/', views.library_admin_announcement_edit, name='library_admin_announcement_edit'),
    path('library-admin/announcements/<int:pk>/delete/', views.library_admin_announcement_delete, name='library_admin_announcement_delete'),
    
    # ========== USER PROFILE & ACTIVITY ==========
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/approve/<int:user_id>/', views.approve_teacher, name='approve_teacher'),
    path('activity-log/', views.activity_log, name='activity_log'),
    path('api/calculate-grade/', views.api_calculate_grade, name='api_calculate_grade'),
    path('set-grading-preference/<int:exam_id>/', views.set_grading_preference, name='set_grading_preference'),
    
    # ========== ANNOUNCEMENTS ==========
    path('announcements/', views.announcement_list, name='announcement_list'),
    path('announcements/create/', views.create_announcement, name='create_announcement'),
    path('announcements/<int:pk>/', views.announcement_detail, name='announcement_detail'),
    path('announcements/<int:pk>/edit/', views.edit_announcement, name='edit_announcement'),
    path('announcements/<int:pk>/delete/', views.delete_announcement, name='delete_announcement'),
    path('announcements/<int:pk>/stats/', views.announcement_read_stats, name='announcement_stats'),
    
    # ========== ADMIN DASHBOARD ==========
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/statistics/', views.dashboard_statistics, name='dashboard_statistics'),
    path('dashboard/users/', views.manage_users, name='manage_users'),
    path('dashboard/users/<int:user_id>/role/', views.change_user_role, name='change_user_role'),
    
    # ========== USER MANAGEMENT ==========
    path('users/', views.user_management, name='user_management'),
    path('users/add/', views.add_user, name='add_user'),
    path('users/edit/<int:user_id>/', views.edit_user, name='edit_user'),
    path('users/reset-password/<int:user_id>/', views.reset_user_password, name='reset_user_password'),
    path('users/toggle-status/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('users/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('users/get/<int:user_id>/', views.get_user_json, name='get_user_json'),
    
    # ========== NOTIFICATIONS ==========
    path('notifications/', views.notification_list, name='notifications'),
    path('api/notifications/', views.api_notifications, name='api_notifications'),
    path('api/notifications/<int:pk>/read/', views.api_mark_notification_read, name='api_mark_read'),
    path('api/notifications/mark-all-read/', views.api_mark_all_read, name='api_mark_all_read'),
    path('api/notifications/<int:pk>/archive/', views.api_archive_notification, name='api_archive'),
    
    # ========== API ENDPOINTS ==========
    path('api/subjects/', views.get_subjects, name='get_subjects'),
    path('api/subjects/add/', views.add_subject, name='api_add_subject'),
    path('api/subjects/delete/<int:pk>/', views.delete_subject, name='delete_subject'),
    path('add-subject/', views.add_subject, name='add_subject'),
    path('api/categories/', views.get_categories, name='get_categories'),
    path('api/central-stats/', views.central_stats, name='central_stats'),
    path('api/increment-view/<int:pk>/', views.increment_resource_view, name='increment_view'),
    
    # ========== CENTRAL DASHBOARD API ==========
    path('api/register-school/', views.register_school_api, name='register_school_api'),
    path('api/schools/list/', views.get_schools_list, name='get_schools_list'),
    path('api/schools/<int:school_id>/stats/', views.get_school_stats, name='get_school_stats'),
    
    # ========== FEES MANAGEMENT ==========
    path('fees/dashboard/', views.fees_dashboard, name='fees_dashboard'),
    path('fees/structure/', views.fee_structure_list, name='fee_structure_list'),
    path('fees/structures/', views.fee_structure_list, name='fee_structure_list_alias'),
    path('fees/defaulters/', views.defaulter_list, name='defaulter_list'),
    path('fees/reports/', views.collection_report, name='collection_report'),
    path('fees/reports/defaulters/', views.defaulter_list, name='defaulter_list_alias'),
    path('fees/reports/export-defaulters/', views.export_defaulters_csv, name='export_defaulters_csv'),
    path('fees/reports/collection/', views.collection_report, name='collection_report_alias'),
    
    # ========== STUDENT MANAGEMENT ==========
    path('students/', views.student_list, name='student_list'),
    path('students/bulk-upload/', views.student_bulk_upload, name='student_bulk_upload'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/<int:pk>/', views.student_detail, name='student_detail'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:student_id>/delete/', views.soft_delete_student, name='soft_delete_student'),
    path('students/<int:student_id>/reactivate/', views.reactivate_student, name='reactivate_student'),
    
    # ========== FEES STUDENT ALIASES ==========
    path('fees/students/', views.student_list, name='fees_student_list'),
    path('fees/students/<int:pk>/', views.student_detail, name='fees_student_detail'),
    path('fees/students/create/', views.student_create, name='fees_student_create'),
    path('fees/students/<int:pk>/edit/', views.student_edit, name='fees_student_edit'),
    
    # ========== BULK RESULTS UPLOAD (Excel/CSV) ==========
    path('bulk-enter-results/', views.bulk_enter_results, name='bulk_enter_results'),
    path('bulk-excel-process/', views.bulk_excel_process, name='bulk_excel_process'),
    
    # ========== FEE STRUCTURE ==========
    path('fees/structure/print/<int:fee_structure_id>/', views.print_fee_structure, name='print_fee_structure'),
    path('fees/structure/create/', views.fee_structure_create, name='fee_structure_create'),
    path('fees/structure/<int:pk>/edit/', views.fee_structure_edit, name='fee_structure_edit'),
    path('fees/structure/<int:pk>/delete/', views.fee_structure_delete, name='fee_structure_delete'),
    path('fees/structure/delete-component/<int:pk>/', views.fee_structure_delete_component, name='fee_structure_delete_component'),
    
    # ========== FEE PAYMENTS ==========
    path('fees/payments/record/', views.payment_record, name='payment_record'),
    path('fees/payments/<int:pk>/receipt/', views.payment_receipt, name='payment_receipt'),
    path('fees/ajax/search-students/', views.search_students_ajax, name='search_students_ajax'),
    path('fees/ajax/search-students-payment/', views.search_students_for_payment, name='search_students_payment'),
    path('fees/update/', views.fee_update_page, name='fee_update_page'),
    path('fees/update/students/', views.update_student_fees, name='update_student_fees'),
    
    # ========== STUDENT FEE DETAIL ==========
    path('student/<int:student_id>/fee-detail/', views.student_fee_detail, name='student_fee_detail'),
    
    # ========== HISTORICAL ARREARS ==========
    path('fees/historical-arrears/', views.add_historical_arrears, name='add_historical_arrears'),
    
    # ========== SMS DASHBOARD ==========
    path('sms/', views.sms_dashboard, name='sms_dashboard'),
    path('sms/dashboard/', views.sms_dashboard, name='sms_dashboard_alias'),
    path('sms/send-bulk/', views.send_bulk_sms_view, name='send_bulk_sms'),
    path('sms/send-test/', views.send_test_sms, name='send_test_sms'),
    path('sms/to-staff/', views.sms_to_staff, name='sms_to_staff'),
    
    # ========== TV DISPLAY ==========
    path('tv/', views.tv_display, name='tv_display'),
    path('tv/dashboard/', views.tv_dashboard, name='tv_dashboard'),
    path('tv/content/add/', views.tv_content_add, name='tv_content_add'),
    path('tv/content/<int:pk>/edit/', views.tv_content_edit, name='tv_content_edit'),
    path('tv/content/<int:pk>/delete/', views.tv_content_delete, name='tv_content_delete'),
    path('tv/settings/', views.tv_settings, name='tv_settings'),
    
    # ========== PERFORMANCE / EXAM MODULE ==========
    path('performance/', views.performance_dashboard, name='performance_dashboard'),
    path('performance/exam/<int:exam_id>/', views.exam_performance_detail, name='exam_performance_detail'),
    path('exams/', views.exam_list, name='exam_list'),
    path('exams/create/', views.exam_create, name='exam_create'),
    path('exams/<int:pk>/edit/', views.exam_edit, name='exam_edit'),
    
    # ========== RESULTS ENTRY ==========
    path('enter-results/', views.enter_results_form, name='enter_results'),
    path('enter-results-form/', views.enter_results_form, name='enter_results_form'),
    path('enter-results/grid/', views.enter_results_grid, name='enter_results_grid'),
    
    # ========== EXCEL BULK UPLOAD ==========
    path('bulk-excel-upload/', views.bulk_excel_upload, name='bulk_excel_upload'),
    
    # ========== EXAM RESULTS ENTRY ==========
    path('exam-results-entry/<int:exam_id>/', views.exam_results_entry, name='exam_results_entry'),
    
    # ========== PERFORMANCE REPORTS ==========
    path('performance/reports/', views.performance_reports, name='performance_reports'),
    path('performance/report-card/<int:student_id>/', views.student_report_card, name='student_report_card'),
    path('performance/student-analytics/<int:student_id>/', views.student_analytics, name='student_analytics'),
    path('performance/class-analytics/<int:class_id>/', views.class_performance_analytics, name='class_performance_analytics'),
    path('performance/export-report/', views.export_performance_report, name='export_performance_report'),
    path('performance/export-exam/<int:exam_id>/', views.export_exam_performance, name='export_exam_performance'),
    path('performance/export-ranking/<int:exam_id>/', views.export_ranking_csv, name='export_ranking_csv'),
    
    # ========== SUBJECT AND CLASS PERFORMANCE ==========
    path('performance/subject/<int:subject_id>/', views.subject_performance, name='subject_performance'),
    path('performance/class/<int:class_id>/', views.class_performance, name='class_performance'),
    path('performance/subject-exam/<int:subject_id>/<int:exam_id>/', views.subject_exam_performance_detail, name='subject_exam_performance_detail'),
    
    # ========== TEACHER DASHBOARD ==========
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/class/', views.class_teacher_dashboard, name='class_teacher_dashboard'),
    path('teacher/assign-class/', views.assign_class_teachers, name='assign_class_teachers'),
    
    # ========== GRADING SYSTEM ==========
    path('grading/systems/', views.grading_system_list, name='grading_system_list'),
    path('grading/systems/create/', views.grading_system_create, name='grading_system_create'),
    path('grading/systems/<int:pk>/edit/', views.grading_system_edit, name='grading_system_edit'),
    path('grading/systems/<int:pk>/delete/', views.grading_system_delete, name='grading_system_delete'),
    path('grading/teacher-preference/', views.teacher_grading_preference, name='teacher_grading_preference'),
    path('grading/exam/<int:exam_id>/', views.exam_grading_preference, name='exam_grading_preference'),
    path('grading/subject/<int:subject_id>/', views.subject_grading_list, name='subject_grading_list'),
    path('grading/subject/<int:subject_id>/create/', views.subject_grading_create, name='subject_grading_create'),
    path('grading/subject/<int:subject_id>/config/', views.subject_grading_config, name='subject_grading_config'),
    path('grading/config/<int:config_id>/edit/', views.subject_grading_edit, name='subject_grading_edit'),
    path('grading/knec-cbe/', views.knec_cbe_grading, name='knec_cbe_grading'),
    
    # ========== PAPER LIBRARY ==========
    path('papers/', views.paper_library, name='paper_library'),
    path('papers/<int:pk>/', views.paper_detail, name='paper_detail'),
    path('papers/upload/', views.upload_paper_resource, name='upload_paper_resource'),
    path('papers/create-set/', views.create_paper_set, name='create_paper_set'),
    path('papers/download/<int:resource_id>/', views.download_paper_resource, name='download_paper_resource'),
    
    # ========== SCHOOL SETTINGS ==========
    path('school-settings/', views.school_settings, name='school_settings'),
    path('settings/', views.school_settings, name='settings'),
    
    # ========== PARENT PORTAL ==========
    path('parent/login/', views.parent_login, name='parent_login'),
    path('parent/verify-otp/', views.verify_parent_otp, name='verify_parent_otp'),
    path('parent/resend-otp/', views.parent_resend_otp, name='parent_resend_otp'),
    path('parent/logout/', views.parent_logout, name='parent_logout'),
    path('parent/', views.parent_dashboard, name='parent_dashboard'),
    path('parent/dashboard/', views.parent_dashboard, name='parent_dashboard_alias'),
    path('parent/student/<int:student_id>/', views.parent_student_detail, name='parent_student_detail'),
    path('parent/student/<int:student_id>/fee/', views.parent_fee_detail, name='parent_fee_detail'),
    path('parent/student/<int:student_id>/fee-statement/', views.parent_fee_statement, name='parent_fee_statement'),
    path('parent/student/<int:student_id>/results/', views.parent_results, name='parent_results'),
    path('parent/student/<int:student_id>/pay/', views.parent_pay_fees, name='parent_pay_fees'),
    path('parent/child/<int:student_id>/', views.parent_student_detail, name='parent_child_detail'),
    path('parent/grades/', views.parent_view_grades, name='parent_view_grades'),
    path('parent/attendance/', views.parent_view_attendance, name='parent_view_attendance'),
    path('parent/fee/', views.parent_fee_balance, name='parent_fee_balance'),
    
    # ========== FEEDBACK ==========
    path('feedback/', views.share_feedback, name='share_feedback'),
    path('feedback/success/', views.feedback_success, name='feedback_success'),
    path('feedback/list/', views.feedback_list, name='feedback_list'),
    path('api/submit-feedback/', views.submit_feedback, name='submit_feedback'),
    
    # ========== BULK DOWNLOAD ==========
    path('bulk-download/', views.bulk_download_student_packages, name='bulk_download_student_packages'),
    
    # ========== TENANT SELECTOR ==========
    path('tenant-selector/', views.tenant_selector, name='tenant_selector'),
    
    # ========== DEBUG ==========
    path('debug/models/', views.check_result_model, name='check_result_model'),
    
    # ========== BACKUP SYSTEM ==========
    path('backup/', views_backup.backup_management, name='backup_management'),
    path('backup/create/', views_backup.create_backup, name='create_backup'),
    path('backup/restore/', views_backup.restore_backup, name='restore_backup'),
    path('backup/download/', views_backup.download_backup, name='download_backup'),
    path('backup/download/<str:backup_type>/<path:filename>/', views_backup.download_backup_by_name, name='download_backup_by_name'),
    path('backup/delete/', views_backup.delete_backup, name='delete_backup'),
    path('backup/schedule/', views_backup.save_schedule, name='backup_schedule'),
    path('backup/schedule-settings/', views_backup.schedule_settings, name='schedule_settings'),
    
    # Feedback URLs
    path('feedback/', views.feedback_list, name='feedback_list'),
    path('feedback/admin/', views.feedback_admin, name='feedback_admin'),
    path('feedback/submit/', views.submit_feedback, name='submit_feedback'),
    path('feedback/<int:feedback_id>/resolve/', views.resolve_feedback, name='resolve_feedback'),
    path('feedback/<int:feedback_id>/delete/', views.delete_feedback, name='delete_feedback'),
]

# Health check
urlpatterns += [
    path('health/', health_check, name='health'),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
