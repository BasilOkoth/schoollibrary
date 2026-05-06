# digitallibrary/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.views.generic import TemplateView

app_name = 'digitallibrary'

urlpatterns = [
    # ========== HOME ==========
    path('', views.home, name='home'),
    
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
    
    # ========== AI SEARCH ==========
    path('ai-search/', views.ai_search_page, name='ai_search_page'),
    
    # ========== PRINTING PORTAL ==========
    path('printing/request/', views.printing_portal, name='printing_portal'),
    path('printing/mark-downloaded/<int:job_id>/', views.mark_as_downloaded, name='mark_downloaded'),
    path('printing/mark-completed/<int:job_id>/', views.mark_as_completed, name='mark_completed'),
    path('printing/job/<int:job_id>/', views.print_job_detail, name='print_job_detail'),
    path('printing/download/<int:job_id>/', views.download_print_file, name='download_print_file'),
    
    # ========== LIBRARY ADMIN ==========
    path('library-admin/', views.library_admin_dashboard, name='library_admin_dashboard'),
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
    path('api/test/', views.test_metrics, name='test-metrics'),
    path('api/public/metrics/', views.public_metrics, name='public-metrics'),
    path('api/central-stats/', views.central_stats, name='central_stats'),
    path('api/increment-view/<int:pk>/', views.increment_resource_view, name='increment_view'),
    
    # ========== CENTRAL DASHBOARD API ==========
    path('api/register-school/', views.register_school_api, name='register_school_api'),
    path('api/schools/list/', views.get_schools_list, name='get_schools_list'),
    path('api/schools/<int:school_id>/stats/', views.get_school_stats, name='get_school_stats'),
    
    # ========== FEES MANAGEMENT ==========
    path('fees/dashboard/', views.fees_dashboard, name='fees_dashboard'),
    path('fees/structure/', views.fee_structure_list, name='fee_structure_list'),
    path('students/bulk-upload/', views.student_bulk_upload, name='student_bulk_upload'),
    path('fees/structure/create/', views.fee_structure_create, name='fee_structure_create'),
    path('fees/structure/<int:pk>/edit/', views.fee_structure_edit, name='fee_structure_edit'),
    path('fees/students/', views.student_list, name='student_list'),
    path('fees/students/<int:pk>/', views.student_detail, name='student_detail'),
    path('fees/students/create/', views.student_create, name='student_create'),
    path('fees/students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('fees/structure/print/<int:fee_structure_id>/', views.print_fee_structure, name='print_fee_structure'),
    path('fees/payments/record/', views.payment_record, name='payment_record'),
    path('fees/payments/<int:pk>/receipt/', views.payment_receipt, name='payment_receipt'),
    path('fees/reports/defaulters/', views.defaulter_list, name='defaulter_list'),
    path('fees/reports/export-defaulters/', views.export_defaulters_csv, name='export_defaulters_csv'),
    path('fees/reports/collection/', views.collection_report, name='collection_report'),
    path('fees/ajax/search-students/', views.search_students_ajax, name='search_students_ajax'),
    path('fees/ajax/search-students-payment/', views.search_students_for_payment, name='search_students_payment'),
    
    # ========== PERFORMANCE MODULE ==========
    # Dashboard
    path('performance/', views.performance_dashboard, name='performance_dashboard'),
    path('system-dashboard/', views.system_dashboard, name='system_dashboard'),
    
    # Exam Management
    path('exams/', views.exam_list, name='exam_list'),
    path('exams/create/', views.exam_create, name='exam_create'),
    path('exams/<int:pk>/edit/', views.exam_edit, name='exam_edit'),
    
    # Results Entry
    path('enter-results/', views.enter_results_form, name='enter_results_form'),
    path('exam-performance/<int:exam_id>/', views.exam_performance_detail, name='exam_performance_detail'),
    path('export-exam-performance/<int:exam_id>/', views.export_exam_performance, name='export_exam_performance'),
    path('export-performance-report/', views.export_performance_report, name='export_performance_report'),
    
    # Subject Exam Performance
    path('subject-exam-performance/<int:subject_id>/<int:exam_id>/', views.subject_exam_performance_detail, name='subject_exam_performance_detail'),
    
    # Bulk Entry
    path('bulk-enter-results/', views.bulk_select, name='bulk_enter_results'),
    path('bulk-results-entry/<int:exam_id>/<int:subject_id>/', views.bulk_results_entry, name='bulk_results_entry'),
    path('bulk-excel-upload/', views.bulk_excel_upload, name='bulk_excel_upload'),
    path('download-template/', views.download_excel_template, name='download_excel_template'),
    
    # Performance Reports
    path('performance/reports/', views.performance_reports, name='performance_reports'),
    path('performance/class/<int:class_id>/', views.class_performance, name='class_performance'),
    path('performance/subject/<int:subject_id>/', views.subject_performance, name='subject_performance'),
    path('performance/report-card/<int:student_id>/', views.student_report_card, name='student_report_card'),
    path('performance/report-card/<int:student_id>/<int:exam_id>/', views.student_report_card, name='student_report_card_with_exam'),
    
    # Teacher Dashboards
    path('my-dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('class-dashboard/', views.class_teacher_dashboard, name='class_teacher_dashboard'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),  # Removed duplicate
    
    # Exam Compilation & Rankings
    path('compile-results/', views.compile_results_overview, name='compile_results'),
    path('exam-compilation/<int:exam_id>/', views.exam_compilation, name='exam_compilation'),
    path('exam-ranking/<int:exam_id>/', views.exam_ranking, name='exam_ranking'),
    path('class-ranking/<int:class_id>/', views.class_ranking, name='class_ranking'),
    path('export-ranking/<int:exam_id>/', views.export_ranking_csv, name='export_ranking'),
    
    # Student Performance Tracking
    path('student-performance/<int:student_id>/', views.student_performance_tracking, name='student_performance_tracking'),
    
    # ========== SMS DASHBOARD ==========
    path('sms/', views.sms_dashboard, name='sms_dashboard'),
    path('sms/send-bulk/', views.send_bulk_sms_view, name='send_bulk_sms'),
    path('sms/send-test/', views.send_test_sms, name='send_test_sms'),
    
    # ========== API ENDPOINTS ==========
    path('api/students/by-class/<int:class_id>/', views.get_students_by_class_api, name='api_students_by_class'),
    path('api/students/all/', views.get_all_students_api, name='get_all_students_api'),
    path('library/', views.library_list, name='library_list'),
    path('api/performance/submit-results/', views.submit_results_api, name='submit_results_api'),
    path('exam/<int:exam_id>/get-students/', views.get_subject_students, name='get_subject_students'),
    path('view-subject-results/<int:exam_id>/<int:subject_id>/', views.view_subject_results, 
name='view_subject_results'),
    path('subject/<int:subject_id>/exam/<int:exam_id>/', views.subject_exam_performance, name='subject_exam_performance'),
    
    # ========== FEEDBACK ==========
    path('feedback/', views.share_feedback, name='share_feedback'),
    path('feedback/success/', views.feedback_success, name='feedback_success'),
    path('feedback/list/', views.feedback_list, name='feedback_list'),
    
    # ========== PAPER LIBRARY ==========
    path('papers/', views.paper_library, name='paper_library'),
    path('papers/<int:pk>/', views.paper_detail, name='paper_detail'),
    path('papers/create/', views.create_paper_set, name='create_paper_set'),
    path('papers/upload/', views.upload_paper_resource, name='upload_paper_resource'),
    path('papers/download/<int:resource_id>/', views.download_paper_resource, name='download_paper_resource'),
    
    # ========== PWA / OFFLINE SUPPORT ==========
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json'), name='manifest'),
  # In digitallibrary/urls.py
    path('fees/update/', views.fee_update_page, name='fee_update_page'),
    path('fees/update/students/', views.update_student_fees, name='update_student_fees'),
# Add this to urlpatterns
   path('bulk-download-students/', views.bulk_download_student_packages, name='bulk_download_students'),  
]