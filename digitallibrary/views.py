# ==============================
# file: digitallibrary/views.py
# ==============================
from __future__ import annotations
from digitallibrary.decorators import role_required
from tenants.models import School
from django.db import models
from django.conf import settings
from .decorators import tenant_app_view
from collections import defaultdict
from statistics import mean, pstdev
from django.db import connection
from digitallibrary.decorators import fees_access
from digitallibrary.decorators import sms_access
from django.db.models import Sum
from .sms_utils import send_sms, send_bulk_sms, send_to_teachers, send_to_students, send_to_all_users
from .sms_utils import format_phone_number
from django.views.decorators.http import require_http_methods
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import json
import os
import openpyxl
import mimetypes
import random
from digitallibrary.models import UserProfile
import csv
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
import pandas as pd
from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.core.validators import ValidationError
from .forms import BulkStudentUploadForm
from .models import Student, Class
from datetime import datetime, timedelta
from django.core.cache import cache
from django.db.models import Count, Sum, Q, Avg, Max, Min
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
# ReportLab imports for PDF generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# Tenant imports for central dashboard
from tenants.models import School
from django_tenants.utils import tenant_context
from digitallibrary.decorators import role_required
from .forms import ResourceForm, AnnouncementForm, AnnouncementFilterForm, FeedbackForm
from .models import (
    Resource,
    Category,
    Subject,
    PrintJob,
    SchoolSetting,
    UserProfile,
    Announcement,
    AnnouncementRead,
    ActivityLog,
    Notification,
    FeeStructure,
    Student,
    FeePayment,
    FeeBalance,
    Feedback,
    Class,
    Class,
    FeeComponent,
    Class as ClassModel,
    Exam,
    StudentResult,
    PerformanceSummary,
    Grade,
    PaperSet,
    PaperResource,
)
from .forms import (
    FeeStructureForm, 
    StudentForm, 
    FeePaymentForm, 
    StudentSearchForm,
    ExamForm,
    StudentResultForm,
    BulkResultForm,
    PaperResourceForm,
    PaperSetFilterForm,
)


# ========== HELPER FUNCTIONS ==========

MOCK_SMS_MODE = getattr(settings, 'MOCK_SMS_MODE', True)


def generate_receipt_number():
    """Generate a unique receipt number"""
    prefix = "RCP"
    date_str = datetime.now().strftime("%Y%m%d")
    random_num = str(random.randint(1000, 9999))
    
    receipt_number = f"{prefix}{date_str}{random_num}"
    
    while FeePayment.objects.filter(receipt_number=receipt_number).exists():
        random_num = str(random.randint(1000, 9999))
        receipt_number = f"{prefix}{date_str}{random_num}"
    
    return receipt_number


def update_fee_balance_after_payment(payment):
    """Update fee balance after a payment is recorded"""
    from django.db.models import Sum
    from digitallibrary.models import FeeBalance, FeePayment
    
    # Get or create fee balance
    balance, created = FeeBalance.objects.get_or_create(
        student=payment.student,
        term=payment.term,
        academic_year=payment.academic_year,
        defaults={
            'total_expected': 0,
            'total_paid': 0,
            'balance': 0
        }
    )
    
    # Calculate total paid
    total_paid = FeePayment.objects.filter(
        student=payment.student,
        term=payment.term,
        academic_year=payment.academic_year
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Just update total paid - don't query fee structure
    balance.total_paid = total_paid
    balance.save()


def get_year_choices():
    """Generate year choices from 2000 to next year"""
    current_year = timezone.now().year
    years = [str(year) for year in range(current_year + 1, 1999, -1)]
    years.append('N/A')
    return years


def get_grade_from_score(score):
    """Helper function to get grade from score"""
    grade_obj = Grade.objects.filter(min_score__lte=score, max_score__gte=score).first()
    return grade_obj.grade if grade_obj else 'N/A'


def update_performance_summary(student, academic_year, term):
    """Update or create performance summary for a student"""
    results = StudentResult.objects.filter(
        student=student,
        exam__academic_year=academic_year,
        exam__term=term
    ).select_related('exam')
    
    if not results:
        return
    
    total_score = sum(float(r.score) for r in results)
    average_score = total_score / len(results)
    
    total_points = 0
    subjects_passed = 0
    subjects_failed = 0
    
    for result in results:
        grade_obj = Grade.objects.filter(min_score__lte=result.score, max_score__gte=result.score).first()
        if grade_obj:
            total_points += float(grade_obj.points)
            if grade_obj.grade in ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-']:
                subjects_passed += 1
            else:
                subjects_failed += 1
    
    average_points = total_points / len(results) if results else 0
    
    overall_grade_obj = Grade.objects.filter(min_score__lte=average_score, max_score__gte=average_score).first()
    overall_grade = overall_grade_obj.grade if overall_grade_obj else None
    
    class_summaries = PerformanceSummary.objects.filter(
        student__current_class=student.current_class,
        academic_year=academic_year,
        term=term
    ).order_by('-average_score')
    
    rank = 1
    for i, summary in enumerate(class_summaries, 1):
        if summary.student_id == student.id:
            rank = i
            break
    
    PerformanceSummary.objects.update_or_create(
        student=student,
        academic_year=academic_year,
        term=term,
        defaults={
            'total_score': total_score,
            'average_score': average_score,
            'total_points': total_points,
            'average_points': average_points,
            'overall_grade': overall_grade,
            'rank_in_class': rank,
            'subjects_passed': subjects_passed,
            'subjects_failed': subjects_failed,
        }
    )

@staff_member_required
def search_students_ajax(request):
    """AJAX endpoint for searching students"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'results': []})
    
    students = Student.objects.filter(is_active=True).filter(
        Q(admission_number__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(parent_phone__icontains=query) |
        Q(upi_number__icontains=query)
    )[:20]
    
    results = []
    for student in students:
        results.append({
            'id': student.id,
            'admission_number': student.admission_number,
            'name': student.get_full_name(),
            'class': student.current_class.name if student.current_class else 'N/A',
            'parent_phone': student.parent_phone,
        })
    
    return JsonResponse({'results': results})
# ========== AJAX SEARCH FUNCTIONS ==========

@staff_member_required
def search_students_ajax(request):
    """AJAX endpoint for searching students"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'results': []})
    
    students = Student.objects.filter(is_active=True).filter(
        Q(admission_number__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(parent_phone__icontains=query) |
        Q(upi_number__icontains=query)
    )[:20]
    
    results = []
    for student in students:
        results.append({
            'id': student.id,
            'admission_number': student.admission_number,
            'name': student.get_full_name(),
            'class': student.current_class.name if student.current_class else 'N/A',
            'parent_phone': student.parent_phone,
        })
    
    return JsonResponse({'results': results})


@login_required
def search_students_for_payment(request):
    """AJAX endpoint to search students for payment selection"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'results': []})
    
    students = Student.objects.filter(is_active=True).filter(
        Q(admission_number__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(parent_phone__icontains=query) |
        Q(upi_number__icontains=query)
    )[:20]
    
    results = []
    for student in students:
        results.append({
            'id': student.id,
            'text': f"{student.admission_number} - {student.first_name} {student.last_name} ({student.current_class.name if student.current_class else 'No Class'})",
            'admission': student.admission_number,
            'name': f"{student.first_name} {student.last_name}",
            'class': student.current_class.name if student.current_class else 'N/A',
            'parent_phone': student.parent_phone,
        })
    
    return JsonResponse({'results': results})


@login_required
def get_students_by_class(request, class_id):
    """API to get students for a specific class"""
    students = Student.objects.filter(
        current_class_id=class_id,
        is_active=True
    ).values('id', 'admission_number', 'first_name', 'last_name')
    
    return JsonResponse({
        'success': True,
        'students': list(students)
    })


@login_required
def get_all_students(request):
    """API to get all active students"""
    students = Student.objects.filter(
        is_active=True
    ).values('id', 'admission_number', 'first_name', 'last_name')
    
    return JsonResponse({
        'success': True,
        'students': list(students)
    })


@login_required
def user_management(request):
    """Manage all users in the system"""
    if request.user.profile.role not in ['admin', 'principal']:
        messages.error(request, "Access Denied. Only administrators can manage users.")
        return redirect('digitallibrary:home')
    
    # Get all users with their profiles - ADDED order_by to fix pagination warning
    users = User.objects.all().select_related('profile').order_by('-date_joined')
    
    # Filter by role if specified
    role_filter = request.GET.get('role', '')
    if role_filter:
        users = users.filter(profile__role=role_filter)
    
    # Search
    search = request.GET.get('search', '')
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page', 1)
    users_page = paginator.get_page(page_number)
    
    # Calculate statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = User.objects.filter(is_active=False).count()
    
    # Role counts
    role_counts = {}
    for role_code, role_name in UserProfile.ROLE_CHOICES:
        count = UserProfile.objects.filter(role=role_code).count()
        role_counts[role_code] = count
    
    context = {
        'users': users_page,
        'role_filter': role_filter,
        'search': search,
        'roles': UserProfile.ROLE_CHOICES,
        'school': SchoolSetting.objects.first(),
        # Statistics
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'role_counts': role_counts,
    }
    return render(request, 'digitallibrary/user_management.html', context)
@login_required
@role_required(['admin', 'principal'])
def assign_class_teachers(request):
    """Assign class teachers (homeroom teachers) - Admin and Principal only"""
    
    classes = Class.objects.all().order_by('name')
    
    # Teachers that can be class teachers (including class_teacher role and regular teachers)
    teachers = User.objects.filter(
        profile__role__in=['class_teacher', 'teacher', 'admin', 'principal'],
        profile__is_approved=True,
        is_active=True
    ).order_by('first_name', 'last_name')
    
    if request.method == 'POST':
        class_id = request.POST.get('class_id')
        teacher_id = request.POST.get('teacher_id')
        
        class_obj = get_object_or_404(Class, id=class_id)
        
        if teacher_id:
            teacher = get_object_or_404(User, id=teacher_id)
            class_obj.class_teacher = teacher
            class_obj.save()
            
            # Update user's role to class_teacher if they are a regular teacher
            if teacher.profile.role == 'teacher':
                teacher.profile.role = 'class_teacher'
                teacher.profile.save()
            
            messages.success(request, f"{teacher.get_full_name()} assigned as class teacher for {class_obj.name}")
        else:
            # Remove class teacher
            old_teacher = class_obj.class_teacher
            class_obj.class_teacher = None
            class_obj.save()
            
            # Optionally revert role back to teacher (if they have no other classes)
            if old_teacher:
                other_classes = Class.objects.filter(class_teacher=old_teacher).exclude(id=class_obj.id)
                if not other_classes.exists() and old_teacher.profile.role == 'class_teacher':
                    old_teacher.profile.role = 'teacher'
                    old_teacher.profile.save()
            
            messages.success(request, f"Class teacher removed for {class_obj.name}")
        
        return redirect('digitallibrary:assign_class_teachers')
    
    context = {
        'classes': classes,
        'teachers': teachers,
        'title': 'Assign Class Teachers',
    }
    return render(request, 'digitallibrary/assign_class_teachers.html', context)
@login_required
@role_required(['admin', 'principal'])
def class_teacher_dashboard(request):
    """Dashboard for class teachers to see their assigned class"""
    
    if request.user.profile.role == 'class_teacher':
        # Get the class this teacher is assigned to
        assigned_class = Class.objects.filter(class_teacher=request.user).first()
        
        if assigned_class:
            # Get students in this class
            students = Student.objects.filter(current_class=assigned_class, is_active=True)
            
            context = {
                'assigned_class': assigned_class,
                'students': students,
                'total_students': students.count(),
                'title': f'Class Teacher Dashboard - {assigned_class.name}',
            }
            return render(request, 'digitallibrary/class_teacher_dashboard.html', context)
        else:
            messages.warning(request, "You are not assigned to any class yet.")
            return redirect('digitallibrary:home')
    
    # For admin/principal viewing all classes
    classes = Class.objects.all().order_by('name')
    context = {
        'classes': classes,
        'title': 'Class Teacher Overview',
    }
    return render(request, 'digitallibrary/class_teacher_overview.html', context)

def add_user(request):
    """Add a new user to the system"""
    from django.contrib.auth.models import User
    from digitallibrary.models import UserProfile, SchoolSetting
    from django.core.mail import send_mail
    from django.conf import settings
    
    if request.user.profile.role not in ['admin', 'principal']:
        messages.error(request, "Access Denied.")
        return redirect('digitallibrary:home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        role = request.POST.get('role')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validation
        errors = []
        if User.objects.filter(username=username).exists():
            errors.append(f"Username '{username}' already exists.")
        if User.objects.filter(email=email).exists():
            errors.append(f"Email '{email}' already exists.")
        if not password:
            errors.append("Password is required.")
        elif password != confirm_password:
            errors.append("Passwords do not match.")
        elif len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Create profile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.is_approved = True
            profile.save()
            
            messages.success(request, f"User '{username}' created successfully! Password: {password}")
            return redirect('digitallibrary:user_management')
    
    school = SchoolSetting.objects.first()
    context = {
        'roles': UserProfile.ROLE_CHOICES,
        'title': 'Add New User',
        'school': school,
    }
    return render(request, 'digitallibrary/user_form.html', context)
from django.contrib.auth.decorators import login_required

@login_required
def edit_user(request, user_id):
    """Edit user details"""
    from django.contrib.auth.models import User
    from digitallibrary.models import UserProfile, SchoolSetting
    
    if request.user.profile.role not in ['admin', 'principal']:
        messages.error(request, "Access Denied.")
        return redirect('digitallibrary:home')
    
    edit_user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        edit_user.first_name = request.POST.get('first_name')
        edit_user.last_name = request.POST.get('last_name')
        edit_user.email = request.POST.get('email')
        edit_user.is_active = request.POST.get('is_active') == 'on'
        
        # Update role
        new_role = request.POST.get('role')
        if new_role:
            profile, created = UserProfile.objects.get_or_create(user=edit_user)
            profile.role = new_role
            profile.save()
        
        # Check if password reset is requested
        new_password = request.POST.get('new_password')
        if new_password and len(new_password) >= 6:
            edit_user.set_password(new_password)
            messages.success(request, f"Password for '{edit_user.username}' has been reset to: {new_password}")
        
        edit_user.save()
        
        messages.success(request, f"User '{edit_user.username}' updated successfully!")
        return redirect('digitallibrary:user_management')
    
    school = SchoolSetting.objects.first()
    context = {
        'edit_user': edit_user,
        'roles': UserProfile.ROLE_CHOICES,
        'title': f'Edit User - {edit_user.username}',
        'school': school,
    }
    return render(request, 'digitallibrary/user_form.html', context)
@login_required
def reset_user_password(request, user_id):
    """Reset user password"""
    if request.user.profile.role not in ['admin', 'principal']:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
        messages.error(request, "Access Denied.")
        return redirect('digitallibrary:user_management')
    
    if request.method == 'POST':
        try:
            # Handle JSON request from fetch API
            if request.headers.get('Content-Type') == 'application/json':
                data = json.loads(request.body)
                new_password = data.get('password')
            else:
                new_password = request.POST.get('new_password')
            
            user = get_object_or_404(User, id=user_id)
            
            if not new_password or len(new_password) < 6:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Password must be at least 6 characters'})
                messages.error(request, "Password must be at least 6 characters.")
                return redirect('digitallibrary:user_management')
            
            # Set new password
            user.set_password(new_password)
            user.save()
            
            # Send email notification (optional)
            try:
                send_mail(
                    subject="Your Password Has Been Reset",
                    message=f"""
                    Hello {user.first_name} {user.last_name},
                    
                    Your password has been reset by an administrator.
                    
                    New Login Details:
                    Username: {user.username}
                    Password: {new_password}
                    
                    Please change your password after logging in.
                    
                    Regards,
                    Administration
                    """,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email] if user.email else [],
                    fail_silently=True,
                )
            except:
                pass
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Password reset to: {new_password}'})
            
            messages.success(request, f"Password for '{user.username}' has been reset to: {new_password}")
            return redirect('digitallibrary:user_management')
            
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(e)})
            messages.error(request, f"Error: {str(e)}")
            return redirect('digitallibrary:user_management')
    
    # For GET requests, show a simple form
    context = {
        'user': get_object_or_404(User, id=user_id),
        'title': 'Reset Password',
    }
    return render(request, 'digitallibrary/reset_password.html', context)
@login_required
def get_user_json(request, user_id):
    """Get user data as JSON for modal forms"""
    if request.user.profile.role not in ['admin', 'principal']:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    user = get_object_or_404(User, id=user_id)
    return JsonResponse({
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'role': user.profile.role,
        'is_active': user.is_active,
    })
@login_required
def toggle_user_status(request, user_id):
    """Activate/Deactivate user"""
    if request.user.profile.role not in ['admin', 'principal']:
        messages.error(request, "Access Denied.")
        return redirect('digitallibrary:user_management')
    
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('digitallibrary:user_management')
    
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()
    
    status = "activated" if user.is_active else "deactivated"
    messages.success(request, f"User '{user.username}' has been {status}.")
    
    return redirect('digitallibrary:user_management')

@login_required
def delete_user(request, user_id):
    """Delete user (soft delete or hard delete)"""
    if request.user.profile.role != 'admin':
        messages.error(request, "Access Denied. Only administrators can delete users.")
        return redirect('digitallibrary:user_management')
    
    # Only allow POST requests for security
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect('digitallibrary:user_management')
    
    user = get_object_or_404(User, id=user_id)
    
    # Don't allow deleting yourself
    if user.id == request.user.id:
        messages.error(request, "You cannot delete your own account.")
        return redirect('digitallibrary:user_management')
    
    username = user.username
    user.delete()
    messages.success(request, f"User '{username}' has been deleted.")
    
    return redirect('digitallibrary:user_management')
# ========== PERFORMANCE VIEWS ==========

@staff_member_required
@tenant_app_view
def exam_list(request):
    """List all exams with class filtering and results count"""
    exams = Exam.objects.all().select_related('student_class').order_by('-academic_year', '-term', 'name')
    
    year = request.GET.get('year')
    term = request.GET.get('term')
    class_id = request.GET.get('class')
    
    if year:
        exams = exams.filter(academic_year=year)
    if term:
        exams = exams.filter(term=term)
    if class_id:
        exams = exams.filter(student_class_id=class_id)
    
    # Add results count and student count for each exam
    for exam in exams:
        # Count distinct students who have results for this exam
        exam.results_count = StudentResult.objects.filter(exam=exam).values('student').distinct().count()
        # Get total students for this exam
        exam.total_students = exam.get_students_for_exam().count()
    
    # Get available years for filter
    available_years = Exam.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    
    context = {
        'exams': exams,
        'current_year': request.GET.get('year', str(timezone.now().year)),
        'current_term': request.GET.get('term', ''),
        'selected_class': request.GET.get('class', ''),
        'classes': Class.objects.all().order_by('name'),
        'available_years': available_years,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'performance/exam_list.html', context)

@staff_member_required
def exam_create(request):
    """Create a new exam"""
    if request.method == 'POST':
        form = ExamForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Exam created successfully!')
            return redirect('digitallibrary:exam_list')
    else:
        form = ExamForm()
    
    return render(request, 'performance/exam_form.html', {'form': form, 'title': 'Create Exam'})
@tenant_app_view
def bulk_select(request):
    """Step 1: Select exam and subject for bulk entry"""
    from .models import Exam, Subject, Student
    
    exams = Exam.objects.all().order_by('-academic_year', '-created_at')
    subjects = Subject.objects.all().order_by('name')
    
    selected_exam_id = None
    selected_subject_id = None
    selected_exam = None
    total_students = 0
    
    if request.method == 'POST':
        exam_id = request.POST.get('exam')
        subject_id = request.POST.get('subject')
        
        if exam_id and subject_id:
            try:
                exam = Exam.objects.get(id=exam_id)
                subject = Subject.objects.get(id=subject_id)
                return redirect('digitallibrary:bulk_results_entry', exam_id=exam.id, subject_id=subject.id)
            except (Exam.DoesNotExist, Subject.DoesNotExist):
                messages.error(request, 'Invalid selection')
        
        selected_exam_id = exam_id
        selected_subject_id = subject_id
        if selected_exam_id:
            try:
                selected_exam = Exam.objects.get(id=selected_exam_id)
            except Exam.DoesNotExist:
                pass
    else:
        exam_id = request.GET.get('exam')
        if exam_id:
            try:
                selected_exam = Exam.objects.get(id=exam_id)
                selected_exam_id = exam_id
            except Exam.DoesNotExist:
                pass
    
    if selected_exam:
        if selected_exam.student_class:
            total_students = selected_exam.student_class.students.filter(is_active=True).count()
        else:
            total_students = Student.objects.filter(is_active=True).count()
    
    context = {
        'exams': exams,
        'subjects': subjects,
        'selected_exam_id': selected_exam_id,
        'selected_subject_id': selected_subject_id,
        'selected_exam': selected_exam,
        'total_students': total_students,
    }
    
    return render(request, 'digitallibrary/bulk_select.html', context)


@tenant_app_view
def bulk_results_entry(request, exam_id, subject_id):
    """Step 2: Enter results for all students in a table"""
    from .models import Exam, Subject, Student
    
    exam = Exam.objects.get(id=exam_id)
    subject = Subject.objects.get(id=subject_id)
    
    if exam.student_class:
        students = exam.student_class.students.filter(is_active=True)
    else:
        students = Student.objects.filter(is_active=True)
    
    students = students.order_by('first_name', 'last_name')
    
    existing_results = {}
    try:
        from .models import Result
        results = Result.objects.filter(exam=exam, subject=subject, student__in=students)
        existing_results = {r.student_id: r for r in results}
    except ImportError:
        pass
    
    if request.method == 'POST':
        saved_count = 0
        for key, value in request.POST.items():
            if key.startswith('score_') and value:
                student_id = key.replace('score_', '')
                try:
                    score = float(value)
                    student = Student.objects.get(id=student_id)
                    
                    try:
                        from .models import Result
                        result, created = Result.objects.update_or_create(
                            exam=exam,
                            subject=subject,
                            student=student,
                            defaults={'score': score}
                        )
                        saved_count += 1
                    except ImportError:
                        saved_count += 1
                except (ValueError, Student.DoesNotExist):
                    continue
        
        messages.success(request, f'Successfully saved {saved_count} results for {subject.name}')
        return redirect('digitallibrary:bulk_results_entry', exam_id=exam.id, subject_id=subject.id)
    
    context = {
        'exam': exam,
        'subject': subject,
        'students': students,
        'existing_results': existing_results,
        'completion_percentage': int((len(existing_results) / len(students)) * 100) if students else 0,
        'pending_count': len(students) - len(existing_results) if students else 0,
    }
    
    return render(request, 'digitallibrary/bulk_results_entry.html', context)
@staff_member_required
def download_excel_template(request):
    """Download Excel template for bulk upload"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="exam_results_template.xlsx"'
    
    # Create workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Exam Results Template"
    
    # Headers
    headers = ['Admission Number', 'Score', 'Student Name (Optional)']
    
    # Style for headers
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1a4d8c", end_color="1a4d8c", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    # Sample data
    sample_data = [
        ['2024001', 85.5, 'John Doe'],
        ['2024002', 92.0, 'Jane Smith'],
        ['2024003', 76.5, 'Mike Johnson'],
        ['2024004', 68.0, 'Sarah Williams'],
        ['2024005', 94.5, 'David Brown'],
    ]
    
    for row_idx, row_data in enumerate(sample_data, 2):
        for col_idx, value in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col_idx, value=value)
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 18
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 25
    
    # Add instructions sheet
    instructions_ws = wb.create_sheet("Instructions")
    instructions_ws['A1'] = "Instructions for Bulk Upload"
    instructions_ws['A1'].font = Font(bold=True, size=14)
    
    instructions = [
        "",
        "1. Admission Number column is REQUIRED - must match existing student admission numbers",
        "2. Score column is REQUIRED - must be a number between 0 and the exam's max score",
        "3. Student Name column is OPTIONAL - for reference only",
        "4. The first row contains column headers - do not delete or modify",
        "5. You can add as many rows as needed",
        "6. Scores will be created or updated for the selected exam and subject",
        "7. Make sure students already exist in the system before uploading",
    ]
    
    for i, instruction in enumerate(instructions, 1):
        instructions_ws.cell(row=i, column=1, value=instruction)
    
    instructions_ws.column_dimensions['A'].width = 60
    
    wb.save(response)
    return response
@staff_member_required
def exam_edit(request, pk):
    """Edit an exam"""
    exam = get_object_or_404(Exam, pk=pk)
    
    if request.method == 'POST':
        form = ExamForm(request.POST, instance=exam)
        if form.is_valid():
            form.save()
            messages.success(request, 'Exam updated successfully!')
            return redirect('digitallibrary:exam_list')
    else:
        form = ExamForm(instance=exam)
    
    return render(request, 'performance/exam_form.html', {'form': form, 'title': 'Edit Exam'})

def system_dashboard(request):
    """Executive dashboard with filtering by term, class, year, and subject"""
    from .models import Exam, Class, Subject, Student, StudentResult
    from django.db.models import Avg, Sum, Count, Q
    
    # Get filter parameters
    current_year = request.GET.get('year', '')
    current_term = request.GET.get('term', '')
    selected_class = request.GET.get('class', '')
    selected_subject = request.GET.get('subject', '')
    
    # Build exams queryset with filters
    exams_qs = Exam.objects.all().order_by('-academic_year', '-created_at')
    
    # Apply year filter
    if current_year:
        exams_qs = exams_qs.filter(academic_year=current_year)
    
    # Apply term filter
    if current_term:
        exams_qs = exams_qs.filter(term=current_term)
    
    # Apply class filter
    if selected_class:
        exams_qs = exams_qs.filter(student_class_id=selected_class)
    
    # Debug: Print the count
    print(f"Exams found: {exams_qs.count()}")
    print(f"Filters - Year: {current_year}, Term: {current_term}, Class: {selected_class}")
    
    # Get available years for filter dropdown
    available_years = Exam.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    
    # Get filtered exams with completion rates
    recent_exams = []
    for exam in exams_qs:
        # Get total students for this exam
        if exam.student_class:
            total_students = exam.student_class.students.filter(is_active=True).count()
        else:
            total_students = Student.objects.filter(is_active=True).count()
        
        # Get results count based on filters
        results_qs = StudentResult.objects.filter(exam=exam)
        
        # Apply subject filter to results count
        if selected_subject:
            results_qs = results_qs.filter(subject_id=selected_subject)
            results_count = results_qs.values('student').distinct().count()
        else:
            results_count = results_qs.values('student').distinct().count()
        
        # Calculate completion rate
        completion_rate = (results_count / total_students * 100) if total_students > 0 else 0
        
        recent_exams.append({
            'id': exam.id,
            'name': exam.name,
            'academic_year': exam.academic_year,
            'term': exam.term,
            'class_name': exam.student_class.name if exam.student_class else 'All Classes',
            'completion_rate': completion_rate,
            'total_students': total_students,
            'results_count': results_count,
        })
    
    # Calculate overall metrics with filters
    results_qs = StudentResult.objects.all()
    
    # Apply all filters to results
    if current_year:
        results_qs = results_qs.filter(exam__academic_year=current_year)
    if current_term:
        results_qs = results_qs.filter(exam__term=current_term)
    if selected_class:
        results_qs = results_qs.filter(student__current_class_id=selected_class)
    if selected_subject:
        results_qs = results_qs.filter(subject_id=selected_subject)
    
    # Calculate averages
    avg_data = results_qs.aggregate(avg=Avg('score'))
    avg_score = avg_data['avg'] or 0
    
    # Calculate pass rate
    total_results = results_qs.count()
    passed_results = results_qs.filter(score__gte=50).count()
    pass_rate = (passed_results / total_results * 100) if total_results > 0 else 0
    
    # Get total students
    students_qs = Student.objects.filter(is_active=True)
    if selected_class:
        students_qs = students_qs.filter(current_class_id=selected_class)
    total_students = students_qs.count()
    
    # Get total exams count after filters
    total_exams = exams_qs.count()
    
    # Get classes and subjects for filter dropdowns
    classes = Class.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('name')
    
    # Get selected class/subject names for display
    selected_class_name = None
    if selected_class:
        class_obj = Class.objects.filter(id=selected_class).first()
        selected_class_name = class_obj.name if class_obj else None
    
    selected_subject_name = None
    if selected_subject:
        subject_obj = Subject.objects.filter(id=selected_subject).first()
        selected_subject_name = subject_obj.name if subject_obj else None
    
    context = {
        'total_students': total_students,
        'total_exams': total_exams,
        'avg_score': avg_score,
        'pass_rate': pass_rate,
        'recent_exams': recent_exams,
        'current_year': current_year,
        'current_term': current_term,
        'selected_class': selected_class,
        'selected_subject': selected_subject,
        'selected_class_name': selected_class_name,
        'selected_subject_name': selected_subject_name,
        'classes': classes,
        'subjects': subjects,
        'available_years': available_years,
    }
    
    return render(request, 'performance/system_dashboard.html', context)
@staff_member_required
def student_performance(request, student_id):
    """View individual student performance"""
    student = get_object_or_404(Student, pk=student_id)
    results = StudentResult.objects.filter(student=student).select_related('exam', 'subject').order_by('-exam__academic_year', '-exam__term', 'subject__name')
    summaries = PerformanceSummary.objects.filter(student=student).order_by('-academic_year', '-term')
    
    all_scores = results.values_list('score', flat=True)
    overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0
    
    context = {
        'student': student,
        'results': results,
        'summaries': summaries,
        'overall_avg': overall_avg,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'performance/student_performance.html', context)


@staff_member_required
def enter_results(request):
    """Page for entering exam results"""
    exam_id = request.GET.get('exam')
    
    if exam_id:
        try:
            exam = Exam.objects.get(id=exam_id)
            
            if exam.student_class:
                students = Student.objects.filter(current_class=exam.student_class, is_active=True).order_by('admission_number')
            else:
                students = Student.objects.filter(is_active=True).order_by('admission_number')
            
            existing_results = StudentResult.objects.filter(exam=exam)
            existing_scores = {r.student_id: r.score for r in existing_results}
            
            context = {
                'exam': exam,
                'students': students,
                'existing_scores': existing_scores,
                'school': SchoolSetting.objects.first(),
            }
            return render(request, 'performance/enter_results_form.html', context)
            
        except Exam.DoesNotExist:
            messages.error(request, 'The selected exam does not exist.')
            return redirect('digitallibrary:performance_dashboard')
    
    exams = Exam.objects.all().order_by('-created_at')
    subjects = Subject.objects.all().order_by('name')
    classes = Class.objects.all().order_by('name')
    
    context = {
        'exams': exams,
        'subjects': subjects,
        'classes': classes,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'performance/select_exam.html', context)



@staff_member_required
def exam_results_entry(request, exam_id):
    """Enter or edit results for an exam - by subject"""
    exam = get_object_or_404(Exam, pk=exam_id)
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    
    # Get selected subject from GET or default to first
    selected_subject_id = request.GET.get('subject')
    if not selected_subject_id and subjects.exists():
        selected_subject_id = subjects.first().id
        return redirect(f'{request.path}?subject={selected_subject_id}')
    
    selected_subject = None
    students = []
    existing_results = {}
    
    if selected_subject_id:
        try:
            selected_subject = Subject.objects.get(pk=selected_subject_id, is_active=True)
            students = exam.get_students_for_exam()
            
            # Get ALL existing results for this exam and subject
            for result in StudentResult.objects.filter(
                exam=exam, 
                subject=selected_subject
            ).select_related('student'):
                # Store the full result object, not just the score
                existing_results[result.student.id] = result
                
        except Subject.DoesNotExist:
            pass
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        if subject_id:
            selected_subject = get_object_or_404(Subject, pk=subject_id)
            students = exam.get_students_for_exam()
            saved_count = 0
            updated_count = 0
            
            for student in students:
                score_key = f'score_{student.id}'
                if score_key in request.POST:
                    score_value = request.POST.get(score_key)
                    if score_value and score_value.strip():
                        try:
                            score = float(score_value)
                            if 0 <= score <= float(exam.max_score):
                                # Check if result already exists
                                existing = StudentResult.objects.filter(
                                    student=student,
                                    exam=exam,
                                    subject=selected_subject
                                ).first()
                                
                                if existing:
                                    # Update existing result
                                    existing.score = score
                                    existing.entered_by = request.user
                                    existing.save()
                                    updated_count += 1
                                    print(f"Updated: {student.first_name} {student.last_name} - New score: {score}")
                                else:
                                    # Create new result
                                    StudentResult.objects.create(
                                        student=student,
                                        exam=exam,
                                        subject=selected_subject,
                                        score=score,
                                        entered_by=request.user
                                    )
                                    saved_count += 1
                                    print(f"Created: {student.first_name} {student.last_name} - Score: {score}")
                        except ValueError:
                            pass
            
            if saved_count > 0 or updated_count > 0:
                messages.success(
                    request, 
                    f'Results for {exam.name} - {selected_subject.name} saved! '
                    f'{saved_count} new, {updated_count} updated.'
                )
            else:
                messages.warning(request, 'No results were saved.')
            
            # Redirect back to the same subject to show updated results
            return redirect(f'{request.path}?subject={subject_id}')
    
    context = {
        'exam': exam,
        'subjects': subjects,
        'selected_subject': selected_subject,
        'students': students,
        'existing_results': existing_results,
        'title': f'Enter/Edit Results - {exam.name}',
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'performance/exam_results_entry.html', context)
# ========== ENHANCED STUDENT ANALYTICS VIEWS ==========

@staff_member_required
def student_analytics(request, student_id):
    """Comprehensive student performance analytics with trends, recommendations, and parent summary"""
    from collections import defaultdict
    from statistics import mean, pstdev
    
    student = get_object_or_404(Student, pk=student_id)

    summaries = list(
        PerformanceSummary.objects.filter(student=student)
        .select_related("student")
        .order_by("academic_year", "term")
    )

    results = list(
        StudentResult.objects.filter(student=student)
        .select_related("exam", "subject", "student")
        .order_by("exam__academic_year", "exam__term", "exam__name", "subject__name")
    )

    latest_summary = summaries[-1] if summaries else None
    previous_summary = summaries[-2] if len(summaries) > 1 else None

    latest_avg = round(float(latest_summary.average_score), 1) if latest_summary else 0.0
    previous_avg = round(float(previous_summary.average_score), 1) if previous_summary else 0.0
    avg_change = round(latest_avg - previous_avg, 1) if previous_summary else 0.0
    performance_status = _status_from_change(avg_change)
    overall_grade = _grade_from_score_analytics(latest_avg)

    latest_rank = latest_summary.rank_in_class if latest_summary and latest_summary.rank_in_class else None
    previous_rank = previous_summary.rank_in_class if previous_summary and previous_summary.rank_in_class else None
    rank_change = (previous_rank - latest_rank) if latest_rank and previous_rank else None

    class_average = 0.0
    class_rank = latest_rank

    if latest_summary and getattr(student, "current_class", None):
        class_average_value = (
            PerformanceSummary.objects.filter(
                student__current_class=student.current_class,
                academic_year=latest_summary.academic_year,
                term=latest_summary.term,
            ).aggregate(avg=Avg("average_score"))["avg"]
            or 0
        )
        class_average = round(float(class_average_value), 1)

    trend_labels = []
    trend_scores = []
    overall_scores = []

    terms_data = {}
    for summary in summaries:
        label = f"Term {summary.term} - {summary.academic_year}"
        score = round(float(summary.average_score), 1)
        trend_labels.append(label)
        trend_scores.append(score)
        overall_scores.append(score)

        terms_data[label] = {
            "average": score,
            "term": summary.term,
            "year": summary.academic_year,
            "rank": summary.rank_in_class,
            "grade": summary.overall_grade or _grade_from_score_analytics(score),
            "points": round(float(summary.average_points), 1) if summary.average_points is not None else 0.0,
            "subjects": [],
        }

    consistency_label, score_deviation = _consistency_label(overall_scores)

    subject_history = defaultdict(list)
    exams_data = defaultdict(lambda: {"exam": None, "subjects": [], "average": 0.0})

    for result in results:
        term_label = f"T{result.exam.term} {result.exam.academic_year}"
        score = round(float(result.score), 1)

        subject_history[result.subject.name].append(
            {
                "term": result.exam.term,
                "year": result.exam.academic_year,
                "term_label": term_label,
                "exam_name": result.exam.name,
                "score": score,
            }
        )

        exam_key = result.exam.id
        exams_data[exam_key]["exam"] = result.exam
        exams_data[exam_key]["subjects"].append(
            {
                "name": result.subject.name,
                "score": score,
            }
        )

        summary_key = f"Term {result.exam.term} - {result.exam.academic_year}"
        if summary_key in terms_data:
            terms_data[summary_key]["subjects"].append(
                {
                    "name": result.subject.name,
                    "score": score,
                }
            )

    for exam_id, exam_block in exams_data.items():
        subject_scores = [item["score"] for item in exam_block["subjects"]]
        exam_block["average"] = _safe_mean(subject_scores)

    subject_analysis = []
    subject_comparison = []
    subject_trends = {}
    subjects_data = {}
    improving_subjects = []
    declining_subjects = []
    risk_subjects = []
    strong_subjects = []

    for subject_name, items in subject_history.items():
        items = sorted(items, key=lambda x: (int(x["year"]), int(x["term"]), x["exam_name"]))
        subjects_data[subject_name] = items

        scores = [item["score"] for item in items]
        first_score = round(scores[0], 1)
        latest_score = round(scores[-1], 1)
        best_score = round(max(scores), 1)
        lowest_score = round(min(scores), 1)
        average_score = _safe_mean(scores)
        subject_change = round(latest_score - first_score, 1) if len(scores) >= 2 else 0.0
        subject_status = _status_from_change(subject_change) if len(scores) >= 2 else "Stable"

        latest_item = items[-1]
        latest_term = latest_item["term"]
        latest_year = latest_item["year"]

        class_avg_value = (
            StudentResult.objects.filter(
                subject__name=subject_name,
                exam__term=latest_term,
                exam__academic_year=latest_year,
                student__current_class=student.current_class,
            ).aggregate(avg=Avg("score"))["avg"]
            or 0
        )
        class_avg = round(float(class_avg_value), 1)
        difference = round(latest_score - class_avg, 1)

        subject_analysis.append(
            {
                "name": subject_name,
                "first_score": first_score,
                "latest_score": latest_score,
                "best_score": best_score,
                "lowest_score": lowest_score,
                "average_score": average_score,
                "change": subject_change,
                "status": subject_status,
                "grade": _grade_from_score_analytics(latest_score),
                "class_average": class_avg,
                "class_diff": difference,
                "better_than_class": difference >= 0,
                "at_risk": latest_score < 50,
                "strong": latest_score >= 70,
            }
        )

        subject_comparison.append(
            {
                "name": subject_name,
                "student_avg": latest_score,
                "class_avg": class_avg,
                "difference": difference,
                "better": difference >= 0,
            }
        )

        subject_trends[subject_name] = {
            "first": first_score,
            "last": latest_score,
            "improvement": subject_change,
        }

        if len(scores) >= 2:
            if subject_change >= 3:
                improving_subjects.append(subject_name)
            elif subject_change <= -3:
                declining_subjects.append(subject_name)

        if latest_score < 50:
            risk_subjects.append(subject_name)
        if latest_score >= 70:
            strong_subjects.append(subject_name)

    subject_analysis.sort(key=lambda x: x["latest_score"], reverse=True)
    subject_comparison.sort(key=lambda x: x["difference"], reverse=True)

    teacher_recommendations = []
    parent_recommendations = []

    if risk_subjects:
        teacher_recommendations.append(
            f"Provide immediate remediation in {', '.join(risk_subjects[:3])} and review recent assessment errors."
        )
        parent_recommendations.append(
            f"Set aside extra weekly revision time for {', '.join(risk_subjects[:3])} using short and regular practice."
        )

    if declining_subjects:
        teacher_recommendations.append(
            f"Closely monitor declining performance in {', '.join(declining_subjects[:3])} and compare classwork against exam performance."
        )
        parent_recommendations.append(
            f"Discuss challenges in {', '.join(declining_subjects[:3])} and track homework completion more closely."
        )

    if strong_subjects:
        teacher_recommendations.append(
            f"Extend learning in {', '.join(strong_subjects[:3])} through more challenging class activities."
        )
        parent_recommendations.append(
            f"Maintain motivation in {', '.join(strong_subjects[:3])} with praise and consistent revision routines."
        )

    if not teacher_recommendations:
        teacher_recommendations.append("Maintain current support, continue tracking progress, and reinforce good study habits.")

    if not parent_recommendations:
        parent_recommendations.append("Maintain a consistent study routine and review school feedback regularly.")

    parent_summary = _build_parent_summary(
        student_name=f"{student.first_name} {student.last_name}",
        latest_avg=latest_avg,
        avg_change=avg_change,
        performance_status=performance_status,
        strong_subjects=strong_subjects,
        risk_subjects=risk_subjects,
        declining_subjects=declining_subjects,
    )

    context = {
        "student": student,
        "summaries": list(reversed(summaries)),
        "results": results,
        "total_terms": len(summaries),
        "overall_avg": latest_avg,
        "overall_grade": overall_grade,
        "class_rank": class_rank,
        "class_average": class_average,
        "latest_avg": latest_avg,
        "previous_avg": previous_avg,
        "avg_change": avg_change,
        "performance_status": performance_status,
        "latest_rank": latest_rank,
        "previous_rank": previous_rank,
        "rank_change": rank_change,
        "trend_labels": trend_labels,
        "trend_scores": trend_scores,
        "terms_data": terms_data,
        "exams_data": dict(exams_data),
        "subjects_data": dict(subjects_data),
        "subject_analysis": subject_analysis,
        "subject_comparison": subject_comparison,
        "subject_trends": subject_trends,
        "improving_subjects": improving_subjects,
        "declining_subjects": declining_subjects,
        "risk_subjects": risk_subjects,
        "strong_subjects": strong_subjects,
        "consistency_label": consistency_label,
        "score_deviation": score_deviation,
        "teacher_recommendations": teacher_recommendations,
        "parent_recommendations": parent_recommendations,
        "parent_summary": parent_summary,
        "school": SchoolSetting.objects.first(),
    }
    return render(request, "digitallibrary/student_analytics.html", context)


# ========== CLASS PERFORMANCE ANALYTICS VIEW ==========

@staff_member_required
def class_performance_analytics(request, class_id):
    """Class-level performance analytics with metrics and graphs"""
    import json
    
    student_class = get_object_or_404(Class, pk=class_id)
    academic_year = request.GET.get('year', str(timezone.now().year))
    
    students = Student.objects.filter(current_class=student_class, is_active=True)
    summaries = PerformanceSummary.objects.filter(
        student__in=students,
        academic_year=academic_year
    ).select_related('student').order_by('term', 'rank_in_class')
    
    term_data = {}
    for term in [1, 2, 3]:
        term_summaries = summaries.filter(term=term)
        if term_summaries.exists():
            term_data[f'Term {term}'] = {
                'average': term_summaries.aggregate(Avg('average_score'))['average_score__avg'] or 0,
                'pass_rate': term_summaries.filter(average_score__gte=50).count() / term_summaries.count() * 100 if term_summaries.count() > 0 else 0,
                'top_student': term_summaries.order_by('-average_score').first().student.get_full_name() if term_summaries.exists() else 'N/A',
                'top_score': term_summaries.aggregate(Max('average_score'))['average_score__max'] or 0,
            }
    
    latest_term = summaries.aggregate(Max('term'))['term__max'] or 1
    latest_summaries = summaries.filter(term=latest_term)
    grade_distribution = {
        'A': latest_summaries.filter(overall_grade='A').count(),
        'A-': latest_summaries.filter(overall_grade='A-').count(),
        'B+': latest_summaries.filter(overall_grade='B+').count(),
        'B': latest_summaries.filter(overall_grade='B').count(),
        'B-': latest_summaries.filter(overall_grade='B-').count(),
        'C+': latest_summaries.filter(overall_grade='C+').count(),
        'C': latest_summaries.filter(overall_grade='C').count(),
        'C-': latest_summaries.filter(overall_grade='C-').count(),
        'D+': latest_summaries.filter(overall_grade='D+').count(),
        'D': latest_summaries.filter(overall_grade='D').count(),
        'E': latest_summaries.filter(overall_grade='E').count(),
    }
    
    top_students = summaries.filter(term=latest_term).order_by('rank_in_class')[:10]
    subject_performance = []
    subjects = Subject.objects.filter(is_active=True)
    
    for subject in subjects:
        results = StudentResult.objects.filter(
            exam__subject=subject,
            exam__academic_year=academic_year,
            student__in=students
        )
        if results.exists():
            avg_score = results.aggregate(Avg('score'))['score__avg'] or 0
            pass_count = results.filter(score__gte=50).values('student').distinct().count()
            subject_performance.append({
                'name': subject.name,
                'average': round(avg_score, 1),
                'pass_rate': round(pass_count / students.count() * 100, 1) if students.count() > 0 else 0,
                'students': results.values('student').distinct().count()
            })
    
    term_labels = list(term_data.keys())
    term_averages = [term_data[t]['average'] for t in term_labels]
    term_pass_rates = [term_data[t]['pass_rate'] for t in term_labels]
    
    context = {
        'class': student_class,
        'students': students,
        'summaries': summaries,
        'term_data': term_data,
        'term_labels': json.dumps(term_labels),
        'term_averages': json.dumps(term_averages),
        'term_pass_rates': json.dumps(term_pass_rates),
        'subject_performance': subject_performance,
        'grade_distribution': grade_distribution,
        'top_students': top_students,
        'academic_year': academic_year,
        'total_students': students.count(),
        'latest_term': latest_term,
        'title': f'Class Performance - {student_class.name}',
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'performance/class_analytics.html', context)


# ========== STUDENT REPORT CARD VIEW ==========

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django_tenants.utils import get_tenant
from datetime import datetime
from .models import Student, Exam, StudentResult, PerformanceSummary, SchoolSetting

# ========== STUDENT REPORT CARD VIEW ==========

def student_report_card(request, student_id, exam_id=None):
    """Generate a printable report card for a student"""
    
    # Get the student
    student = get_object_or_404(Student, pk=student_id, is_active=True)
    
    # Get exam
    if exam_id:
        exam = get_object_or_404(Exam, pk=exam_id)
    else:
        exam = Exam.objects.filter(
            student_class=student.current_class,
            is_active=True
        ).order_by('-academic_year', '-term').first()
    
    if not exam:
        messages.error(request, "No exam results available for this student.")
        return redirect('digitallibrary:student_performance', student_id=student.id)
    
    # Get results
    results = StudentResult.objects.filter(
        student=student,
        exam=exam
    ).select_related('subject').order_by('subject__name')
    
    if not results.exists():
        messages.warning(request, "No subject results found for this exam.")
        return redirect('digitallibrary:student_performance', student_id=student.id)
    
    # Calculate totals
    total_marks = sum(float(r.score) for r in results)
    overall_average = total_marks / len(results) if results else 0
    
    # Get tenant
    tenant = get_tenant(request)
    
    context = {
        'student': student,
        'exam': exam,
        'results': results,
        'total_marks': total_marks,
        'overall_average': overall_average,
        'tenant': tenant,
        'current_date': timezone.now(),
    }
    
    return render(request, 'performance/student_report_card.html', context)
# ========== BULK RESULTS ENTRY VIEWS ==========

@staff_member_required
def bulk_enter_results(request):
    """Step 1: Select exam and class for bulk entry"""
    if request.method == 'POST':
        form = BulkResultForm(request.POST)
        if form.is_valid():
            exam = form.cleaned_data['exam']
            student_class = form.cleaned_data['student_class']
            
            request.session['bulk_exam_id'] = exam.id
            request.session['bulk_class_id'] = student_class.id if student_class else None
            
            return redirect('digitallibrary:bulk_results_entry')
    else:
        initial = {}
        exam_id = request.GET.get('exam')
        if exam_id:
            try:
                initial['exam'] = Exam.objects.get(id=exam_id)
            except Exam.DoesNotExist:
                pass
        
        class_id = request.GET.get('class')
        if class_id:
            try:
                initial['student_class'] = Class.objects.get(id=class_id)
            except Class.DoesNotExist:
                pass
        
        form = BulkResultForm(initial=initial)
    
    context = {
        'form': form,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'performance/bulk_select.html', context)


def bulk_results_entry(request, exam_id, subject_id):
    """Step 2: Enter results for all students in a table"""
    from .models import Exam, Subject, Student
    
    exam = Exam.objects.get(id=exam_id)
    subject = Subject.objects.get(id=subject_id)
    
    # Get students
    if exam.student_class:
        students = exam.student_class.students.filter(is_active=True)
    else:
        students = Student.objects.filter(is_active=True)
    
    students = students.order_by('first_name', 'last_name')
    
    # Get existing results
    existing_results = {}
    try:
        from .models import Result
        results = Result.objects.filter(exam=exam, subject=subject, student__in=students)
        existing_results = {r.student_id: r for r in results}
    except ImportError:
        pass
    
    if request.method == 'POST':
        saved_count = 0
        for key, value in request.POST.items():
            if key.startswith('score_') and value:
                student_id = key.replace('score_', '')
                try:
                    score = float(value)
                    student = Student.objects.get(id=student_id)
                    
                    try:
                        from .models import Result
                        result, created = Result.objects.update_or_create(
                            exam=exam,
                            subject=subject,
                            student=student,
                            defaults={'score': score}
                        )
                        saved_count += 1
                    except ImportError:
                        saved_count += 1
                except (ValueError, Student.DoesNotExist):
                    continue
        
        messages.success(request, f'Successfully saved {saved_count} results for {subject.name}')
        return redirect('digitallibrary:bulk_results_entry', exam_id=exam.id, subject_id=subject.id)
    
    context = {
        'exam': exam,
        'subject': subject,
        'students': students,
        'existing_results': existing_results,
    }
    
    return render(request, 'digitallibrary/bulk_results_entry.html', context)

# ========== BULK EXCEL UPLOAD VIEW ==========

@staff_member_required
def bulk_excel_upload(request):
    """Upload Excel file with results for bulk entry"""
    from .forms import ExcelResultsUploadForm
    
    if request.method == 'POST':
        form = ExcelResultsUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            exam = form.cleaned_data['exam']
            subject = form.cleaned_data['subject']
            
            try:
                workbook = openpyxl.load_workbook(excel_file)
                sheet = workbook.active
                
                # Find column indices
                admission_col = None
                score_col = None
                
                for idx, cell in enumerate(sheet[1], 1):
                    header = str(cell.value).lower().strip() if cell.value else ''
                    if 'admission' in header or 'adm' in header or 'reg' in header:
                        admission_col = idx
                    elif 'score' in header or 'mark' in header or 'result' in header:
                        score_col = idx
                
                if admission_col is None or score_col is None:
                    messages.error(request, 'Excel file must have "Admission Number" and "Score" columns')
                    return redirect('digitallibrary:bulk_excel_upload')
                
                results_processed = 0
                errors = []
                
                for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                    if not row:
                        continue
                    
                    admission_number = str(row[admission_col - 1]).strip() if row[admission_col - 1] else None
                    score_value = row[score_col - 1] if score_col - 1 < len(row) else None
                    
                    if not admission_number or score_value is None:
                        continue
                    
                    try:
                        score = float(score_value)
                        max_score = float(exam.max_score) if exam.max_score else 100.0
                        
                        if score < 0 or score > max_score:
                            errors.append(f"Row {row_idx}: Score {score} is outside valid range (0-{max_score})")
                            continue
                        
                        student = Student.objects.get(admission_number=admission_number, is_active=True)
                        
                        StudentResult.objects.update_or_create(
                            student=student,
                            exam=exam,
                            subject=subject,
                            defaults={'score': score, 'entered_by': request.user}
                        )
                        results_processed += 1
                        
                    except Student.DoesNotExist:
                        errors.append(f"Row {row_idx}: Student with admission number '{admission_number}' not found")
                    except ValueError:
                        errors.append(f"Row {row_idx}: Invalid score value '{score_value}'")
                    except Exception as e:
                        errors.append(f"Row {row_idx}: {str(e)}")
                
                if results_processed > 0:
                    messages.success(request, f'Successfully processed {results_processed} results for {exam.name} - {subject.name}')
                    return redirect('digitallibrary:exam_results_entry', exam_id=exam.id)
                
                if errors:
                    for error in errors[:5]:
                        messages.warning(request, error)
                    if len(errors) > 5:
                        messages.warning(request, f'... and {len(errors) - 5} more errors')
                
                if results_processed == 0:
                    messages.warning(request, 'No valid results were found in the file.')
                    
            except Exception as e:
                messages.error(request, f'Error processing file: {str(e)}')
                return redirect('digitallibrary:bulk_excel_upload')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ExcelResultsUploadForm()
    
    context = {
        'form': form,
        'title': 'Bulk Excel Upload',
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'performance/bulk_excel_upload.html', context)
# ========== BULK RESULTS ENTRY VIEWS ==========

@staff_member_required
def bulk_enter_results(request):
    """Step 1: Select exam and class for bulk entry"""
    if request.method == 'POST':
        form = BulkResultForm(request.POST)
        if form.is_valid():
            exam = form.cleaned_data['exam']
            student_class = form.cleaned_data['student_class']
            
            request.session['bulk_exam_id'] = exam.id
            request.session['bulk_class_id'] = student_class.id if student_class else None
            
            return redirect('digitallibrary:bulk_results_entry')
    else:
        initial = {}
        exam_id = request.GET.get('exam')
        if exam_id:
            try:
                initial['exam'] = Exam.objects.get(id=exam_id)
            except Exam.DoesNotExist:
                pass
        
        class_id = request.GET.get('class')
        if class_id:
            try:
                initial['student_class'] = Class.objects.get(id=class_id)
            except Class.DoesNotExist:
                pass
        
        form = BulkResultForm(initial=initial)
    
    context = {
        'form': form,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'performance/bulk_select.html', context)


# ========== TEACHER DASHBOARD ==========
@login_required
@tenant_app_view
def teacher_dashboard(request):
    """Teacher dashboard showing class teacher and subject teacher responsibilities"""
    
    if request.user.profile.role != 'teacher':
        messages.error(request, "Access Denied. Only teachers can access this page.")
        return redirect('digitallibrary:home')
    
    # Check if teacher is a class teacher (homeroom)
    my_class = Class.objects.filter(class_teacher=request.user).first()
    
    # Get subjects they teach
    from .models import TeacherSubject, StudentResult, Exam
    my_subjects = TeacherSubject.objects.filter(
        teacher=request.user
    ).select_related('subject', 'class_assigned')
    
    # Get recent exams for subjects they teach
    subject_ids = my_subjects.values_list('subject_id', flat=True)
    recent_exams = Exam.objects.filter(
        subject__id__in=subject_ids
    ).order_by('-created_at')[:5] if subject_ids else []
    
    # Get recent results they entered
    recent_results = StudentResult.objects.filter(
        entered_by=request.user
    ).select_related('student', 'exam', 'subject')[:10]
    
    context = {
        'my_class': my_class,
        'my_subjects': my_subjects,
        'recent_exams': recent_exams,
        'recent_results': recent_results,
        'has_class': my_class is not None,
        'has_subjects': my_subjects.exists(),
        'has_results': recent_results.exists(),
        'title': 'Teacher Dashboard',
    }
    return render(request, 'digitallibrary/teacher_dashboard.html', context)


def class_teacher_dashboard(request):
    """Class teacher dashboard"""
    from .models import Exam, Result, Student
    
    exams = Exam.objects.all().order_by('-academic_year', '-created_at')
    total_students = Student.objects.filter(is_active=True).count()
    
    exams_data = []
    for exam in exams:
        results_count_total = Result.objects.filter(exam=exam).values('student').distinct().count()
        
        exams_data.append({
            'id': exam.id,
            'name': exam.name,
            'academic_year': exam.academic_year,
            'term': exam.term,
            'results_count': results_count_total,
            'total_students': total_students,
            'subject_progress': [],
        })
    
    context = {
        'assigned_class': None,
        'total_exams': exams.count(),
        'completed_exams': 0,
        'in_progress_exams': 0,
        'total_students': total_students,
        'exams': exams_data,
        'top_students': [],
    }
    
    return render(request, 'performance/class_teacher_dashboard.html', context)


def compile_results_overview(request):
    """Overview of all exams ready for compilation"""
    from .models import Exam
    
    exams = Exam.objects.all().order_by('-academic_year', '-created_at')
    
    context = {
        'exams': exams,
    }
    
    return render(request, 'performance/compile_results_overview.html', context)


def exam_compilation(request, exam_id):
    """Compile results for a specific exam"""
    from .models import Exam, Result, Student
    
    exam = Exam.objects.get(id=exam_id)
    total_students = Student.objects.filter(is_active=True).count()
    
    # Get subjects for this exam
    from .models import Subject
    subjects = Subject.objects.all()
    
    subjects_data = []
    subjects_completed = 0
    
    for subject in subjects:
        results_count = Result.objects.filter(exam=exam, subject=subject).count()
        completion_rate = (results_count / total_students * 100) if total_students > 0 else 0
        
        if completion_rate == 100:
            subjects_completed += 1
        
        subjects_data.append({
            'subject': subject,
            'results_entered': results_count,
            'completion_rate': completion_rate,
            'teacher': 'Not assigned',
        })
    
    completion_percentage = (subjects_completed / len(subjects) * 100) if subjects else 0
    all_subjects_complete = subjects_completed == len(subjects) if subjects else False
    
    if request.method == 'POST' and all_subjects_complete:
        # Compile results - calculate total scores and ranks
        from .models import ExamResultSummary
        
        students = Student.objects.filter(is_active=True)
        
        for student in students:
            # Get all results for this student in this exam
            results = Result.objects.filter(exam=exam, student=student)
            total_score = sum(r.score for r in results)
            avg_score = total_score / results.count() if results.count() > 0 else 0
            
            # Calculate grade
            if avg_score >= 80:
                grade = 'A'
            elif avg_score >= 70:
                grade = 'B'
            elif avg_score >= 60:
                grade = 'C'
            elif avg_score >= 50:
                grade = 'D'
            else:
                grade = 'E'
            
            summary, created = ExamResultSummary.objects.update_or_create(
                exam=exam,
                student=student,
                defaults={
                    'total_score': total_score,
                    'average_score': avg_score,
                    'overall_grade': grade,
                }
            )
        
        # Calculate ranks
        summaries = ExamResultSummary.objects.filter(exam=exam).order_by('-average_score')
        for idx, summary in enumerate(summaries, 1):
            summary.rank = idx
            summary.save()
        
        messages.success(request, f'Results compiled successfully for {exam.name}!')
        return redirect('digitallibrary:exam_ranking', exam_id=exam.id)
    
    context = {
        'exam': exam,
        'subjects_data': subjects_data,
        'total_subjects': len(subjects),
        'subjects_completed': subjects_completed,
        'completion_percentage': completion_percentage,
        'all_subjects_complete': all_subjects_complete,
        'total_students': total_students,
        'subjects_incomplete': len(subjects) - subjects_completed,
    }
    
    return render(request, 'performance/exam_compilation.html', context)


def exam_ranking(request, exam_id):
    """View rankings for a compiled exam"""
    from .models import Exam, ExamResultSummary, Student
    
    exam = Exam.objects.get(id=exam_id)
    rankings = ExamResultSummary.objects.filter(exam=exam).select_related('student').order_by('rank')
    
    # Calculate class average and pass rate
    class_average = rankings.aggregate(avg=models.Avg('average_score'))['avg'] or 0
    pass_count = rankings.filter(average_score__gte=50).count()
    pass_rate = (pass_count / rankings.count() * 100) if rankings.count() > 0 else 0
    
    top_student = rankings.first()
    
    context = {
        'exam': exam,
        'rankings': rankings,
        'class_average': class_average,
        'pass_rate': pass_rate,
        'top_student': top_student.student if top_student else None,
    }
    
    return render(request, 'performance/exam_ranking.html', context)


def class_ranking(request, class_id):
    """View rankings for a class across all exams"""
    from .models import Class, Student, ExamResultSummary
    
    class_obj = Class.objects.get(id=class_id)
    students = Student.objects.filter(current_class=class_obj, is_active=True)
    
    student_summaries = []
    for student in students:
        summaries = ExamResultSummary.objects.filter(student=student)
        if summaries.exists():
            avg_overall = summaries.aggregate(avg=models.Avg('average_score'))['avg'] or 0
            student_summaries.append({
                'student': student,
                'average_score': avg_overall,
                'exams_taken': summaries.count(),
            })
    
    student_summaries.sort(key=lambda x: x['average_score'], reverse=True)
    
    context = {
        'class_obj': class_obj,
        'rankings': student_summaries,
    }
    
    return render(request, 'performance/class_ranking.html', context)


def export_ranking_csv(request, exam_id):
    """Export exam rankings to CSV"""
    import csv
    from django.http import HttpResponse
    from .models import Exam, ExamResultSummary
    
    exam = Exam.objects.get(id=exam_id)
    rankings = ExamResultSummary.objects.filter(exam=exam).select_related('student').order_by('rank')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{exam.name}_rankings.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Rank', 'Admission Number', 'Student Name', 'Total Score', 'Average Score', 'Grade'])
    
    for ranking in rankings:
        writer.writerow([
            ranking.rank,
            ranking.student.admission_number,
            f"{ranking.student.first_name} {ranking.student.last_name}",
            ranking.total_score,
            ranking.average_score,
            ranking.overall_grade,
        ])
    
    return response


def subject_exam_performance(request, subject_id, exam_id):
    """View performance for a specific subject in an exam"""
    from .models import Subject, Exam, Result, Student
    
    subject = Subject.objects.get(id=subject_id)
    exam = Exam.objects.get(id=exam_id)
    
    results = Result.objects.filter(exam=exam, subject=subject).select_related('student')
    
    total_students = Student.objects.filter(is_active=True).count()
    avg_score = results.aggregate(avg=models.Avg('score'))['avg'] or 0
    top_score = results.aggregate(max=models.Max('score'))['max'] or 0
    lowest_score = results.aggregate(min=models.Min('score'))['min'] or 0
    
    context = {
        'subject': subject,
        'exam': exam,
        'results': results,
        'total_students': total_students,
        'avg_score': avg_score,
        'top_score': top_score,
        'lowest_score': lowest_score,
    }
    
    return render(request, 'performance/subject_exam_performance.html', context)


def view_subject_results(request, exam_id, subject_id):
    """View all results for a subject in an exam (for class teacher)"""
    from .models import Exam, Subject, Result
    
    exam = Exam.objects.get(id=exam_id)
    subject = Subject.objects.get(id=subject_id)
    results = Result.objects.filter(exam=exam, subject=subject).select_related('student').order_by('-score')
    
    context = {
        'exam': exam,
        'subject': subject,
        'results': results,
    }
    
    return render(request, 'performance/view_subject_results.html', context)


def student_performance_tracking(request, student_id):
    """Track student performance across different exams"""
    from .models import Student, Result, Exam
    
    student = Student.objects.get(id=student_id)
    
    # Get all results grouped by subject and exam
    results = Result.objects.filter(student=student).select_related('exam', 'subject').order_by('-exam__academic_year', '-exam__created_at')
    
    # Group by subject
    subjects_data = {}
    for result in results:
        subject_name = result.subject.name
        if subject_name not in subjects_data:
            subjects_data[subject_name] = []
        
        subjects_data[subject_name].append({
            'exam_name': result.exam.name,
            'exam_term': result.exam.term,
            'exam_year': result.exam.academic_year,
            'score': result.score,
            'grade': result.grade if hasattr(result, 'grade') else 'C',
        })
    
    # Get overall averages per subject
    subject_averages = {}
    for subject_name, scores in subjects_data.items():
        avg = sum(s['score'] for s in scores) / len(scores) if scores else 0
        subject_averages[subject_name] = avg
    
    context = {
        'student': student,
        'subjects_data': subjects_data,
        'subject_averages': subject_averages,
        'total_exams': results.values('exam').distinct().count(),
    }
    
    return render(request, 'performance/student_performance_tracking.html', context)

# ========== SUBJECT PERFORMANCE VIEW ==========

@staff_member_required
def subject_performance(request, subject_id):
    """View performance for a specific subject"""
    subject = get_object_or_404(Subject, pk=subject_id)
    academic_year = request.GET.get('year', str(timezone.now().year))
    term = request.GET.get('term', '1')
    
    exams = Exam.objects.filter(academic_year=academic_year, term=term)
    results = StudentResult.objects.filter(
        subject=subject,
        exam__in=exams
    ).select_related('student', 'exam')
    
    avg_score = results.aggregate(Avg('score'))['score__avg'] or 0
    top_score = results.aggregate(Max('score'))['score__max'] or 0
    lowest_score = results.aggregate(Min('score'))['score__min'] or 0
    
    context = {
        'subject': subject,
        'exams': exams,
        'results': results,
        'avg_score': avg_score,
        'top_score': top_score,
        'lowest_score': lowest_score,
        'academic_year': academic_year,
        'term': term,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'performance/subject_performance.html', context)


# ========== CLASS PERFORMANCE VIEW ==========

@staff_member_required
def class_performance(request, class_id):
    """View performance for a specific class"""
    student_class = get_object_or_404(Class, pk=class_id)
    academic_year = request.GET.get('year', str(timezone.now().year))
    term = request.GET.get('term', '1')
    
    students = Student.objects.filter(current_class=student_class, is_active=True)
    summaries = PerformanceSummary.objects.filter(
        student__in=students,
        academic_year=academic_year,
        term=term
    ).select_related('student').order_by('rank_in_class')
    
    avg_class_score = summaries.aggregate(Avg('average_score'))['average_score__avg'] or 0
    total_passed = summaries.filter(average_score__gte=50).count()
    
    context = {
        'class': student_class,
        'summaries': summaries,
        'academic_year': academic_year,
        'term': term,
        'avg_class_score': avg_class_score,
        'total_students': students.count(),
        'total_passed': total_passed,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'performance/class_performance.html', context)


# ========== PERFORMANCE REPORTS VIEW ==========

@staff_member_required
@tenant_app_view
def performance_reports(request):
    """Comprehensive performance reports with grade distribution and summaries"""
    from .models import Exam, Class, Subject, Student, StudentResult
    from django.db.models import Avg, Count, Q, Sum
    from collections import defaultdict
    
    # Get filter parameters
    academic_year = request.GET.get('year', '')
    term = request.GET.get('term', '')
    selected_class = request.GET.get('class', '')
    selected_exam = request.GET.get('exam', '')
    
    # Base queryset for results
    results_qs = StudentResult.objects.all()
    
    # Apply filters
    if academic_year:
        results_qs = results_qs.filter(exam__academic_year=academic_year)
    if term:
        results_qs = results_qs.filter(exam__term=term)
    if selected_class:
        results_qs = results_qs.filter(student__current_class_id=selected_class)
    if selected_exam:
        results_qs = results_qs.filter(exam_id=selected_exam)
    
    # Get total students
    students_qs = Student.objects.filter(is_active=True)
    if selected_class:
        students_qs = students_qs.filter(current_class_id=selected_class)
    total_students = students_qs.count()
    
    # Calculate overall metrics
    avg_data = results_qs.aggregate(avg=Avg('score'))
    avg_score = avg_data['avg'] or 0
    
    total_results = results_qs.count()
    passed_results = results_qs.filter(score__gte=50).count()
    pass_rate = (passed_results / total_results * 100) if total_results > 0 else 0
    
    # Calculate passed students count
    passed_students = results_qs.filter(score__gte=50).values('student').distinct().count()
    
    # Overall Grade Distribution
    grade_ranges = {
        'A': (80, 100),
        'A-': (75, 79),
        'B+': (70, 74),
        'B': (65, 69),
        'B-': (60, 64),
        'C+': (55, 59),
        'C': (50, 54),
        'C-': (45, 49),
        'D+': (40, 44),
        'D': (35, 39),
        'E': (0, 34),
    }
    
    overall_grade_distribution = {}
    total_grade_count = 0
    
    for grade, (min_score, max_score) in grade_ranges.items():
        count = results_qs.filter(score__gte=min_score, score__lte=max_score).count()
        overall_grade_distribution[grade] = {
            'count': count,
            'percentage': (count / total_results * 100) if total_results > 0 else 0
        }
        total_grade_count += count
    
    # Exams Summary
    exams_summary = []
    exams = Exam.objects.all()
    if academic_year:
        exams = exams.filter(academic_year=academic_year)
    if term:
        exams = exams.filter(term=term)
    if selected_class:
        exams = exams.filter(student_class_id=selected_class)
    if selected_exam:
        exams = exams.filter(id=selected_exam)
    
    for exam in exams:
        exam_results = results_qs.filter(exam=exam)
        if exam_results.exists():
            avg = exam_results.aggregate(avg=Avg('score'))['avg'] or 0
            passed = exam_results.filter(score__gte=50).count()
            pass_rate_exam = (passed / exam_results.count() * 100) if exam_results.count() > 0 else 0
            
            # Get top grade in this exam
            top_score = exam_results.aggregate(max=Avg('score'))['max'] or 0
            if top_score >= 80:
                top_grade = 'A'
            elif top_score >= 75:
                top_grade = 'A-'
            elif top_score >= 70:
                top_grade = 'B+'
            elif top_score >= 65:
                top_grade = 'B'
            elif top_score >= 60:
                top_grade = 'B-'
            else:
                top_grade = 'C'
            
            exams_summary.append({
                'id': exam.id,
                'name': exam.name,
                'academic_year': exam.academic_year,
                'term': exam.term,
                'students': exam_results.values('student').distinct().count(),
                'avg_score': avg,
                'pass_rate': pass_rate_exam,
                'top_grade': top_grade,
            })
    
    # Exam Grade Distribution
    exam_grade_distribution = []
    for exam in exams[:10]:  # Limit to 10 exams for performance
        exam_results = results_qs.filter(exam=exam)
        if exam_results.exists():
            distribution = {}
            for grade, (min_score, max_score) in grade_ranges.items():
                count = exam_results.filter(score__gte=min_score, score__lte=max_score).count()
                if count > 0:
                    distribution[grade] = count
            
            exam_grade_distribution.append({
                'id': exam.id,
                'name': exam.name,
                'academic_year': exam.academic_year,
                'term': exam.term,
                'distribution': distribution,
                'total_results': exam_results.count(),
            })
    
    # Top Students
    top_students_data = results_qs.values('student').annotate(
        avg=Avg('score'),
        exams_taken=Count('exam', distinct=True)
    ).order_by('-avg')[:20]
    
    top_students = []
    for ts in top_students_data:
        student = Student.objects.filter(id=ts['student']).first()
        if student:
            avg = ts['avg']
            if avg >= 80:
                grade = 'A'
            elif avg >= 75:
                grade = 'A-'
            elif avg >= 70:
                grade = 'B+'
            elif avg >= 65:
                grade = 'B'
            elif avg >= 60:
                grade = 'B-'
            elif avg >= 55:
                grade = 'C+'
            elif avg >= 50:
                grade = 'C'
            else:
                grade = 'D'
            
            top_students.append({
                'student': student,
                'average': avg,
                'grade': grade,
                'exams_taken': ts['exams_taken'],
            })
    
    # Subject Performance
    subject_performance = []
    subjects = Subject.objects.all()
    for subject in subjects:
        subject_results = results_qs.filter(subject=subject)
        if subject_results.exists():
            avg = subject_results.aggregate(avg=Avg('score'))['avg'] or 0
            passed = subject_results.filter(score__gte=50).count()
            pass_rate_subj = (passed / subject_results.count() * 100) if subject_results.count() > 0 else 0
            
            if avg >= 80:
                grade = 'A'
            elif avg >= 70:
                grade = 'B'
            elif avg >= 60:
                grade = 'C'
            elif avg >= 50:
                grade = 'D'
            else:
                grade = 'E'
            
            subject_performance.append({
                'name': subject.name,
                'students': subject_results.values('student').distinct().count(),
                'average': avg,
                'pass_rate': pass_rate_subj,
                'grade': grade,
            })
    
    # Class Performance
    class_performance = []
    classes = Class.objects.all()
    for class_obj in classes:
        class_results = results_qs.filter(student__current_class=class_obj)
        if class_results.exists():
            avg = class_results.aggregate(avg=Avg('score'))['avg'] or 0
            passed = class_results.filter(score__gte=50).count()
            pass_rate_class = (passed / class_results.count() * 100) if class_results.count() > 0 else 0
            
            if avg >= 80:
                grade = 'A'
            elif avg >= 70:
                grade = 'B'
            elif avg >= 60:
                grade = 'C'
            elif avg >= 50:
                grade = 'D'
            else:
                grade = 'E'
            
            class_performance.append({
                'name': class_obj.name,
                'students': class_results.values('student').distinct().count(),
                'average': avg,
                'pass_rate': pass_rate_class,
                'grade': grade,
            })
    
    # Year choices for filter
    year_choices = Exam.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    
    # Classes for filter
    classes = Class.objects.all().order_by('name')
    
    # Exams for filter
    exam_choices = Exam.objects.all().order_by('-academic_year', '-created_at')
    
    context = {
        # Existing context
        'total_students': total_students,
        'avg_score': avg_score,
        'pass_rate': pass_rate,
        'pass_count': passed_students,
        'top_students': top_students,
        'subject_performance': subject_performance,
        'class_performance': class_performance,
        'year_choices': year_choices,
        'academic_year': academic_year,
        'term': term,
        'selected_class': selected_class,
        'classes': classes,
        
        # NEW context variables
        'total_exams': exams.count(),
        'total_results_count': total_results,
        'overall_grade_distribution': overall_grade_distribution,
        'exams_summary': exams_summary,
        'exam_grade_distribution': exam_grade_distribution,
        'exam_choices': exam_choices,
        'selected_exam': selected_exam,
    }
    
    return render(request, 'performance/performance_reports.html', context)
def export_performance_report(request):
    """Export performance report to CSV"""
    import csv
    from django.http import HttpResponse
    from .models import StudentResult, Student, Exam, Subject
    from django.db.models import Avg
    
    # Get filter parameters
    academic_year = request.GET.get('year', '')
    term = request.GET.get('term', '')
    selected_class = request.GET.get('class', '')
    selected_exam = request.GET.get('exam', '')
    
    # Base queryset
    results_qs = StudentResult.objects.all()
    
    if academic_year:
        results_qs = results_qs.filter(exam__academic_year=academic_year)
    if term:
        results_qs = results_qs.filter(exam__term=term)
    if selected_class:
        results_qs = results_qs.filter(student__current_class_id=selected_class)
    if selected_exam:
        results_qs = results_qs.filter(exam_id=selected_exam)
    
    # Get top students
    top_students = results_qs.values('student').annotate(
        avg=Avg('score')
    ).order_by('-avg')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="performance_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Rank', 'Admission Number', 'Student Name', 'Class', 'Average Score', 'Grade'])
    
    for idx, ts in enumerate(top_students, 1):
        student = Student.objects.filter(id=ts['student']).first()
        if student:
            avg = ts['avg']
            if avg >= 80:
                grade = 'A'
            elif avg >= 70:
                grade = 'B'
            elif avg >= 60:
                grade = 'C'
            elif avg >= 50:
                grade = 'D'
            else:
                grade = 'E'
            
            writer.writerow([
                idx,
                student.admission_number,
                f"{student.first_name} {student.last_name}",
                student.current_class.name if student.current_class else 'N/A',
                f"{avg:.1f}",
                grade
            ])
    
    return response
# ========== API SUBMIT RESULTS ==========

@csrf_exempt
@login_required
def submit_results_api(request):
    """API endpoint to submit exam results"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)
    
    try:
        data = json.loads(request.body)
        results = data.get('results', [])
        
        if not results:
            return JsonResponse({'success': False, 'error': 'No results provided'}, status=400)
        
        saved_count = 0
        errors = []
        
        for result_data in results:
            try:
                student_id = result_data.get('student_id')
                exam_id = result_data.get('exam_id')
                score = result_data.get('score')
                
                if not all([student_id, exam_id, score is not None]):
                    errors.append(f"Missing data for student {student_id}")
                    continue
                
                exam = Exam.objects.get(id=exam_id)
                student = Student.objects.get(id=student_id)
                
                StudentResult.objects.update_or_create(
                    student=student,
                    exam=exam,
                    defaults={'score': float(score), 'entered_by': request.user}
                )
                saved_count += 1
                
            except Exam.DoesNotExist:
                errors.append(f"Exam {exam_id} not found")
            except Student.DoesNotExist:
                errors.append(f"Student {student_id} not found")
            except Exception as e:
                errors.append(str(e))
        
        return JsonResponse({
            'success': True,
            'saved': saved_count,
            'errors': errors if errors else None
        })
        
    except json.JSONDecodeError as e:
        return JsonResponse({'success': False, 'error': f'Invalid JSON: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
# ========== SMS DASHBOARD VIEWS ==========



@sms_access  # Allows admin, principal, and bursar
def sms_dashboard(request):
    """SMS management dashboard"""
    from django.conf import settings
    
    # Removed manual role check since decorator handles it
    
    total_teachers = UserProfile.objects.filter(role='teacher').count()
    total_students = Student.objects.filter(is_active=True).count()
    students_with_phone = Student.objects.filter(is_active=True, parent_phone__isnull=False).exclude(parent_phone='').count()
    
    all_students = Student.objects.filter(is_active=True).select_related('current_class').order_by('first_name', 'last_name')
    paginator = Paginator(all_students, 20)
    page_number = request.GET.get('page', 1)
    students = paginator.get_page(page_number)
    
    classes = Class.objects.all().order_by('name')
    
    # Get SMS mode status
    mock_sms_mode = getattr(settings, 'MOCK_SMS_MODE', True)
    africastalking_username = getattr(settings, 'AFRICASTALKING_USERNAME', 'sandbox')
    
    # Determine SMS mode
    if not mock_sms_mode and africastalking_username != 'sandbox':
        sms_mode = 'LIVE'
        sms_mode_color = 'green'
        sms_mode_text = 'LIVE MODE'
        sms_mode_subtext = 'Real SMS - Charges apply'
        sms_status_icon = '✅'
    else:
        sms_mode = 'TEST'
        sms_mode_color = 'yellow'
        sms_mode_text = 'TEST MODE'
        sms_mode_subtext = 'Mock SMS - No charges'
        sms_status_icon = '🔧'
    
    context = {
        'title': 'SMS Dashboard',
        'total_teachers': total_teachers,
        'total_students': total_students,
        'students_with_phone': students_with_phone,
        'students': students,
        'classes': classes,
        'messages_sent': 0,
        'school': SchoolSetting.objects.first(),
        # SMS Mode variables
        'sms_mode': sms_mode,
        'sms_mode_color': sms_mode_color,
        'sms_mode_text': sms_mode_text,
        'sms_mode_subtext': sms_mode_subtext,
        'sms_status_icon': sms_status_icon,
        'mock_sms_mode': mock_sms_mode,
    }
    return render(request, "digitallibrary/sms/dashboard.html", context)


@sms_access  # Allows admin, principal, and bursar
@require_http_methods(["POST"])
def send_bulk_sms_view(request):
    """Send bulk SMS to selected recipients"""
    # Removed manual role check since decorator handles it
    
    recipient_type = request.POST.get('recipient_type')
    message = request.POST.get('message', '').strip()
    student_ids = request.POST.get('student_ids', '')
    class_id = request.POST.get('class_id')
    
    if not message:
        return JsonResponse({'error': 'Message cannot be empty'}, status=400)
    
    if len(message) > 160:
        return JsonResponse({'error': 'Message exceeds 160 characters'}, status=400)
    
    phone_numbers = []
    recipients_info = []
    
    if recipient_type == 'selected' and student_ids:
        student_id_list = [int(id) for id in student_ids.split(',') if id]
        students = Student.objects.filter(id__in=student_id_list, is_active=True)
        for student in students:
            if student.parent_phone:
                formatted = format_phone_number(student.parent_phone)
                if formatted:
                    phone_numbers.append(formatted)
                    recipients_info.append({
                        'name': student.get_full_name(),
                        'phone': formatted,
                        'admission': student.admission_number
                    })
    
    elif recipient_type == 'all':
        students = Student.objects.filter(is_active=True, parent_phone__isnull=False).exclude(parent_phone='')
        for student in students:
            formatted = format_phone_number(student.parent_phone)
            if formatted:
                phone_numbers.append(formatted)
                recipients_info.append({
                    'name': student.get_full_name(),
                    'phone': formatted,
                    'admission': student.admission_number
                })
    
    elif recipient_type == 'class' and class_id:
        students = Student.objects.filter(current_class_id=class_id, is_active=True, parent_phone__isnull=False).exclude(parent_phone='')
        for student in students:
            formatted = format_phone_number(student.parent_phone)
            if formatted:
                phone_numbers.append(formatted)
                recipients_info.append({
                    'name': student.get_full_name(),
                    'phone': formatted,
                    'admission': student.admission_number
                })
    
    if not phone_numbers:
        return JsonResponse({'success': False, 'error': 'No valid phone numbers found.'}, status=400)
    
    if MOCK_SMS_MODE:
        for info in recipients_info[:5]:
            print(f"[TEST MODE] Would send SMS to {info['name']} ({info['phone']})")
        
        return JsonResponse({
            'success': True,
            'successful': len(phone_numbers),
            'failed': 0,
            'total': len(phone_numbers),
            'message': f"✓ Test Mode: {len(phone_numbers)} SMS message(s) would be sent to {len(recipients_info)} recipient(s)."
        })
    else:
        try:
            result = send_bulk_sms(phone_numbers, message)
            return JsonResponse({
                'success': True,
                'successful': result.get('successful', 0),
                'failed': result.get('failed', 0),
                'total': result.get('total', 0),
                'message': f"✓ Successfully sent to {result.get('successful', 0)} out of {result.get('total', 0)} recipients"
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@sms_access  # Allows admin, principal, and bursar
@require_http_methods(["POST"])
def send_test_sms(request):
    """Send a test SMS to a single number"""
    # Removed manual role check since decorator handles it
    
    phone_number = request.POST.get('phone_number', '').strip()
    message = request.POST.get('message', '').strip()
    
    if not phone_number or not message:
        return JsonResponse({'error': 'Phone number and message are required'}, status=400)
    
    if not phone_number.startswith('+'):
        if phone_number.startswith('0'):
            phone_number = '+254' + phone_number[1:]
        elif phone_number.startswith('254'):
            phone_number = '+' + phone_number
    
    result = send_sms(phone_number, message)
    
    if result['success']:
        ActivityLog.objects.create(
            user=request.user,
            action="sms_test",
            description=f"Test SMS sent to {phone_number}"
        )
        return JsonResponse({'success': True, 'response': result['response']})
    else:
        return JsonResponse({'success': False, 'error': result['error']}, status=500)

# ========== API ENDPOINTS FOR STUDENTS ==========

@login_required
def get_students_by_class_api(request, class_id):
    """API to get students by class"""
    if request.user.profile.role not in ['admin', 'principal', 'teacher']:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    students = Student.objects.filter(current_class_id=class_id, is_active=True)
    
    data = {
        'students': [
            {
                'id': s.id,
                'admission_number': s.admission_number,
                'first_name': s.first_name,
                'last_name': s.last_name,
                'class_name': s.current_class.name if s.current_class else None
            }
            for s in students
        ]
    }
    return JsonResponse(data)


@login_required
def get_all_students_api(request):
    """API to get all active students"""
    if request.user.profile.role not in ['admin', 'principal', 'teacher']:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    students = Student.objects.filter(is_active=True).select_related('current_class')
    
    data = {
        'students': [
            {
                'id': s.id,
                'admission_number': s.admission_number,
                'first_name': s.first_name,
                'last_name': s.last_name,
                'class_name': s.current_class.name if s.current_class else None
            }
            for s in students
        ]
    }
    return JsonResponse(data)


# ========== FEEDBACK SYSTEM VIEWS ==========

@login_required
def share_feedback(request):
    """Submit user feedback"""
    if request.method == 'POST':
        form = FeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.page_url = request.META.get('HTTP_REFERER', '')
            feedback.school_id = getattr(settings, 'SCHOOL_ID', 'unknown')
            feedback.school_name = getattr(settings, 'SCHOOL_NAME', 'Unknown School')
            feedback.school_location = getattr(settings, 'SCHOOL_LOCATION', 'Unknown Location')
            feedback.save()
            
            # Send email notification
            subject = f"[Feedback] {feedback.school_name} - {feedback.subject}"
            message = f"""
School: {feedback.school_name}
Location: {feedback.school_location}
From: {feedback.user.get_full_name() or feedback.user.username}
Email: {feedback.user.email}
Role: {feedback.user.profile.role}
Type: {feedback.get_feedback_type_display()}
Rating: {feedback.rating}/5
Priority: {feedback.priority}

Subject: {feedback.subject}

Message:
{feedback.message}

---
View all feedback: {request.build_absolute_uri('/admin/digitallibrary/feedback/')}
Reply to user: mailto:{feedback.user.email}
"""
            
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=settings.ADMIN_EMAILS,
                    fail_silently=False,
                )
            except Exception as e:
                print(f"Email error: {e}")
            
            messages.success(request, 'Thank you for your feedback! Our team has been notified.')
            # Changed from 'digitallibrary:feedback_success' to direct path
            return redirect('/app/feedback/success/')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = FeedbackForm()
    
    # Add try/except for SchoolSetting to prevent errors
    from .models import SchoolSetting
    try:
        school = SchoolSetting.objects.first()
    except:
        school = None
    
    context = {
        'form': form,
        'title': 'Share Feedback',
        'school': school,
    }
    return render(request, 'digitallibrary/feedback.html', context)

def feedback_success(request):
    """Feedback submission success page"""
    from .models import SchoolSetting
    try:
        school = SchoolSetting.objects.first()
    except:
        school = None
    
    context = {
        'school': school,
        'title': 'Feedback Submitted',
    }
    return render(request, 'digitallibrary/feedback_success.html', context)

@login_required
def feedback_list(request):
    """List all feedback (admin only)"""
    if request.user.profile.role not in ['admin', 'principal']:
        messages.error(request, "Access Denied.")
        return redirect('digitallibrary:home')
    
    feedbacks = Feedback.objects.all().order_by('-created_at')
    
    status = request.GET.get('status')
    if status == 'resolved':
        feedbacks = feedbacks.filter(is_resolved=True)
    elif status == 'pending':
        feedbacks = feedbacks.filter(is_resolved=False)
    
    ftype = request.GET.get('type')
    if ftype:
        feedbacks = feedbacks.filter(feedback_type=ftype)
    
    paginator = Paginator(feedbacks, 20)
    page = request.GET.get('page', 1)
    feedbacks = paginator.get_page(page)
    
    context = {
        'feedbacks': feedbacks,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'digitallibrary/feedback_list.html', context)
def update_performance_summary_for_exam(exam):
    """Update performance summaries for all students in an exam"""
    from django.db.models import Avg, Sum
    
    # Get all results for this exam
    results = StudentResult.objects.filter(exam=exam).select_related('student', 'subject')
    
    # Group by student
    student_scores = {}
    for result in results:
        student_id = result.student.id
        if student_id not in student_scores:
            student_scores[student_id] = {
                'student': result.student,
                'total_score': 0,
                'subject_count': 0,
                'scores': []
            }
        student_scores[student_id]['total_score'] += float(result.score)
        student_scores[student_id]['subject_count'] += 1
        student_scores[student_id]['scores'].append(float(result.score))
    
    # Update or create PerformanceSummary for each student
    for student_id, data in student_scores.items():
        if data['subject_count'] > 0:
            average_score = data['total_score'] / data['subject_count']
            
            # Determine grade
            if average_score >= 80:
                overall_grade = 'A'
            elif average_score >= 75:
                overall_grade = 'A-'
            elif average_score >= 70:
                overall_grade = 'B+'
            elif average_score >= 65:
                overall_grade = 'B'
            elif average_score >= 60:
                overall_grade = 'B-'
            elif average_score >= 55:
                overall_grade = 'C+'
            elif average_score >= 50:
                overall_grade = 'C'
            elif average_score >= 45:
                overall_grade = 'C-'
            elif average_score >= 40:
                overall_grade = 'D+'
            elif average_score >= 35:
                overall_grade = 'D'
            else:
                overall_grade = 'E'
            
            # Count passed subjects (score >= 50)
            subjects_passed = sum(1 for s in data['scores'] if s >= 50)
            subjects_failed = data['subject_count'] - subjects_passed
            
            # Calculate rank in class
            student_class = data['student'].current_class
            if student_class:
                class_summaries = PerformanceSummary.objects.filter(
                    student__current_class=student_class,
                    academic_year=exam.academic_year,
                    term=exam.term
                ).order_by('-average_score')
                
                rank = 1
                for i, s in enumerate(class_summaries, 1):
                    if s.student_id == student_id:
                        rank = i
                        break
            else:
                rank = 0
            
            PerformanceSummary.objects.update_or_create(
                student=data['student'],
                academic_year=exam.academic_year,
                term=exam.term,
                defaults={
                    'total_score': data['total_score'],
                    'average_score': average_score,
                    'overall_grade': overall_grade,
                    'rank_in_class': rank,
                    'subjects_passed': subjects_passed,
                    'subjects_failed': subjects_failed,
                }
            )


@staff_member_required
def exam_results_entry(request, exam_id):
    """Enter results for an exam - by subject"""
    exam = get_object_or_404(Exam, pk=exam_id)
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    
    selected_subject_id = request.GET.get('subject')
    selected_subject = None
    students = []
    existing_results = {}
    
    if selected_subject_id:
        try:
            selected_subject = Subject.objects.get(pk=selected_subject_id, is_active=True)
            students = exam.get_students_for_exam()
            for result in StudentResult.objects.filter(exam=exam, subject=selected_subject).select_related('student'):
                existing_results[result.student_id] = result
        except Subject.DoesNotExist:
            pass
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        if subject_id:
            selected_subject = get_object_or_404(Subject, pk=subject_id)
            students = exam.get_students_for_exam()
            saved_count = 0
            
            for student in students:
                score_key = f'score_{student.id}'
                if score_key in request.POST:
                    score = request.POST.get(score_key)
                    if score and score.strip():
                        try:
                            score_value = float(score)
                            if 0 <= score_value <= exam.max_score:
                                StudentResult.objects.update_or_create(
                                    student=student,
                                    exam=exam,
                                    subject=selected_subject,
                                    defaults={'score': score_value, 'entered_by': request.user}
                                )
                                saved_count += 1
                        except ValueError:
                            pass
            
            if saved_count > 0:
                # Update performance summaries for all students in this exam
                update_performance_summary_for_exam(exam)
                messages.success(request, f'Results for {exam.name} - {selected_subject.name} saved successfully! {saved_count} records updated.')
            else:
                messages.warning(request, 'No results were saved.')
            
            return redirect('digitallibrary:exam_results_entry', exam_id=exam.id)
    
    context = {
        'exam': exam,
        'subjects': subjects,
        'selected_subject': selected_subject,
        'students': students,
        'existing_results': existing_results,
        'title': f'Enter Results - {exam.name}',
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'performance/exam_results_entry.html', context)
# ========== TEMPORARY PDF DOWNLOAD (Disabled) ==========
# Comment out the original download_fee_structure function and use this one temporarily

def download_fee_structure(request, fee_structure_id):
    """Download fee structure - Currently disabled due to ReportLab"""
    messages.warning(request, "PDF download is temporarily unavailable. Please check back later.")
    return redirect('digitallibrary:fee_structure_list')
# ========== PERFORMANCE ANALYTICS HELPER FUNCTIONS ==========

def _safe_mean(values):
    return round(mean(values), 1) if values else 0.0


def _grade_from_score_analytics(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 75:
        return "A-"
    if score >= 70:
        return "B+"
    if score >= 65:
        return "B"
    if score >= 60:
        return "B-"
    if score >= 55:
        return "C+"
    if score >= 50:
        return "C"
    if score >= 45:
        return "C-"
    if score >= 40:
        return "D+"
    if score >= 35:
        return "D"
    return "E"


def _status_from_change(change: float) -> str:
    if change >= 3:
        return "Improving"
    if change <= -3:
        return "Declining"
    return "Stable"


def _consistency_label(scores):
    if len(scores) < 2:
        return "Insufficient Data", 0.0
    deviation = round(pstdev(scores), 1)
    if deviation <= 5:
        return "Very Consistent", deviation
    if deviation <= 10:
        return "Moderately Consistent", deviation
    return "Needs Monitoring", deviation


def _build_parent_summary(student_name, latest_avg, avg_change, performance_status, strong_subjects, risk_subjects, declining_subjects):
    summary = []
    summary.append(f"{student_name} currently has an overall average of {latest_avg:.1f}% and is classified as {performance_status.lower()}.")
    if avg_change > 0:
        summary.append(f"This is an improvement of {avg_change:.1f}% from the previous term.")
    elif avg_change < 0:
        summary.append(f"This is a drop of {abs(avg_change):.1f}% from the previous term.")
    else:
        summary.append("Performance is stable compared to the previous term.")
    if strong_subjects:
        summary.append(f"Strong performance is seen in {', '.join(strong_subjects[:3])}.")
    if declining_subjects:
        summary.append(f"The main subjects needing closer monitoring are {', '.join(declining_subjects[:3])}.")
    if risk_subjects:
        summary.append(f"Immediate support is recommended in {', '.join(risk_subjects[:3])}.")
    if not risk_subjects and not declining_subjects:
        summary.append("The learner is maintaining a healthy academic pattern and should continue with the current study routine.")
    return " ".join(summary)


# ========== CUSTOM LOGIN VIEW ==========

class CustomLoginView(LoginView):
    template_name = 'digitallibrary/login.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['school'] = SchoolSetting.objects.first()
        return context



def home(request):
    """Home page - supports both public and tenant schemas"""
    from django.db import connection
    from django.shortcuts import render
    
    # CRITICAL: For public schema (shulehub.org), return landing page immediately
    if connection.schema_name == 'public':
        return render(request, "digitallibrary/home.html", {
            "is_public_schema": True,
            "school": None,
            "latest": [],
            "announcements": [],
            "featured_announcement": None,
            "total_resources": 0,
            "total_teachers": 0,
            "user_role": "Guest",
            "unread_count": 0,
            "notification_unread_count": 0,
        })
    
    # For tenant schemas (school subdomains), run normal queries
    from .models import Resource, Announcement, SchoolSetting, UserProfile
    from django.db.models import Q
    from django.utils import timezone
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Initialize default values
    school = None
    latest = []
    announcements = []
    featured_announcement = None
    unread_count = 0
    notification_unread_count = 0
    total_resources = 0
    total_teachers = 0
    user_role = "Guest"
    
    try:
        # Get school settings
        try:
            school = SchoolSetting.objects.first()
        except Exception as e:
            logger.warning(f"SchoolSetting error: {e}")
        
        # Get latest resources
        try:
            latest = Resource.objects.all().order_by("-created_at")[:8]
            total_resources = Resource.objects.count()
        except Exception as e:
            logger.warning(f"Resource error: {e}")
        
        # Get total teachers
        try:
            total_teachers = UserProfile.objects.filter(role="teacher").count()
        except Exception as e:
            logger.warning(f"UserProfile error: {e}")
        
        # Get announcements
        try:
            announcements_qs = Announcement.objects.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
            )
            
            if request.user.is_authenticated:
                try:
                    user_role_from_profile = request.user.profile.role
                    if user_role_from_profile in ['admin', 'principal']:
                        pass  # Can see all announcements
                    elif user_role_from_profile == 'teacher':
                        announcements_qs = announcements_qs.filter(
                            Q(target_audience='all') | Q(target_audience='teachers') | Q(target_audience='staff')
                        )
                    elif user_role_from_profile == 'student':
                        announcements_qs = announcements_qs.filter(
                            Q(target_audience='all') | Q(target_audience='students')
                        )
                    elif user_role_from_profile == 'secretary':
                        announcements_qs = announcements_qs.filter(
                            Q(target_audience='all') | Q(target_audience='staff')
                        )
                    else:
                        announcements_qs = announcements_qs.filter(target_audience='all')
                except Exception:
                    announcements_qs = announcements_qs.filter(target_audience='all')
            else:
                announcements_qs = announcements_qs.filter(target_audience='all')
            
            announcements = announcements_qs.order_by("-is_featured", "-created_at")[:5]
            featured_announcement = announcements_qs.filter(is_featured=True).first()
            
        except Exception as e:
            logger.warning(f"Announcement error: {e}")
        
        # Get notification counts
        if request.user.is_authenticated:
            try:
                from .models import AnnouncementRead, Notification
                unread_count = AnnouncementRead.get_unread_count(request.user)
                notification_unread_count = Notification.get_unread_count(request.user)
            except Exception as e:
                logger.warning(f"Notification error: {e}")
        
        # Get user role
        if request.user.is_authenticated:
            try:
                user_role = request.user.profile.role.capitalize()
            except Exception:
                user_role = "User"
                
    except Exception as e:
        logger.error(f"Home view error: {e}")
    
    context = {
        "school": school,
        "latest": latest,
        "announcements": announcements,
        "featured_announcement": featured_announcement,
        "total_resources": total_resources,
        "total_teachers": total_teachers,
        "user_role": user_role,
        "unread_count": unread_count,
        "notification_unread_count": notification_unread_count,
        "is_public_schema": False,
    }
    
    return render(request, "digitallibrary/home.html", context)
def ai_search_page(request):
    """AI-powered semantic search page"""
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        # results = search_ai(query, k=8)  # Uncomment when AI is available
        pass
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/ai_search.html", {
        "q": query,
        "results": results,
        "school": school,
    })


# ========== TEACHER UPLOAD FUNCTIONS ==========

def can_upload(user):
    try:
        profile = user.profile
        return profile.role in ["admin", "teacher", "principal"]
    except Exception:
        return False


@login_required
def upload_resource(request):
    if not can_upload(request.user):
        messages.error(request, "Access Denied: Only teachers and administrators can upload resources.")
        return redirect("digitallibrary:library_list")

    school = SchoolSetting.objects.first()

    if request.method == "POST":
        form = ResourceForm(request.POST, request.FILES)
        if form.is_valid():
            resource = form.save(commit=False)
            resource.uploaded_by = request.user
            resource.save()
            try:
                ActivityLog.objects.create(
                    user=request.user,
                    action="upload",
                    description=f"Uploaded resource: {resource.title} (Year: {resource.year})",
                )
            except Exception:
                pass
            messages.success(request, "Resource uploaded successfully!")
            if request.user.profile.role == "admin":
                return redirect("digitallibrary:library_admin_resources")
            else:
                return redirect("digitallibrary:my_uploads")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ResourceForm()

    subjects = Subject.objects.all().order_by("name")
    categories = Category.objects.all().order_by("name")
    year_choices = get_year_choices()
    recent_uploads = Resource.objects.filter(uploaded_by=request.user).order_by("-created_at")[:5]
    
    return render(request, "digitallibrary/upload_resource.html", {
        "form": form, 
        "subjects": subjects,
        "categories": categories,
        "year_choices": year_choices,
        "school": school,
        "recent_uploads": recent_uploads,
        "is_teacher": request.user.profile.role == "teacher"
    })


@login_required
def my_uploads(request):
    if not can_upload(request.user):
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    
    school = SchoolSetting.objects.first()
    all_resources = Resource.objects.filter(uploaded_by=request.user).order_by("-created_at")
    total_uploads = all_resources.count()
    recent_uploads = all_resources.filter(created_at__gte=timezone.now() - timedelta(days=7)).count()
    total_views = all_resources.aggregate(models.Sum('views'))['views__sum'] or 0
    
    paginator = Paginator(all_resources, 12)
    page = request.GET.get("page", 1)
    resources = paginator.get_page(page)
    
    return render(request, "digitallibrary/my_uploads.html", {
        "resources": resources,
        "school": school,
        "total_uploads": total_uploads,
        "recent_uploads": recent_uploads,
        "total_views": total_views,
        "is_teacher": request.user.profile.role == "teacher"
    })


@login_required
def edit_my_resource(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    if resource.uploaded_by != request.user and request.user.profile.role != "admin":
        messages.error(request, "You don't have permission to edit this resource.")
        return redirect("digitallibrary:library_list")
    
    school = SchoolSetting.objects.first()
    
    if request.method == "POST":
        form = ResourceForm(request.POST, request.FILES, instance=resource)
        if form.is_valid():
            form.save()
            messages.success(request, "Resource updated successfully!")
            try:
                ActivityLog.objects.create(
                    user=request.user,
                    action="edit",
                    description=f"Edited resource: {resource.title} (Year: {resource.year})",
                )
            except Exception:
                pass
            if request.user.profile.role == "admin":
                return redirect("digitallibrary:library_admin_resources")
            else:
                return redirect("digitallibrary:my_uploads")
    else:
        form = ResourceForm(instance=resource)
    
    subjects = Subject.objects.all().order_by("name")
    categories = Category.objects.all().order_by("name")
    year_choices = get_year_choices()
    
    return render(request, "digitallibrary/edit_resource.html", {
        "form": form,
        "resource": resource,
        "subjects": subjects,
        "categories": categories,
        "year_choices": year_choices,
        "school": school,
        "is_teacher": request.user.profile.role == "teacher"
    })


@login_required
@require_POST
def delete_my_resource(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    if resource.uploaded_by != request.user and request.user.profile.role != "admin":
        messages.error(request, "You don't have permission to delete this resource.")
        return redirect("digitallibrary:library_list")
    
    title = resource.title
    if resource.file:
        try:
            if os.path.isfile(resource.file.path):
                os.remove(resource.file.path)
        except Exception:
            pass
    if resource.cover_image:
        try:
            if os.path.isfile(resource.cover_image.path):
                os.remove(resource.cover_image.path)
        except Exception:
            pass
    resource.delete()
    try:
        ActivityLog.objects.create(
            user=request.user,
            action="delete",
            description=f"Deleted resource: {title}",
        )
    except Exception:
        pass
    messages.success(request, f"Resource '{title}' deleted successfully.")
    if request.user.profile.role == "admin":
        return redirect("digitallibrary:library_admin_resources")
    else:
        return redirect("digitallibrary:my_uploads")


# ========== PRINTING PORTAL VIEWS ==========

@login_required
@tenant_app_view
def printing_portal(request):
    profile, _created = UserProfile.objects.get_or_create(user=request.user)
    school = SchoolSetting.objects.first()

    if request.method == "POST":
        file = request.FILES.get("file")
        copies = request.POST.get("copies", 1)
        color = request.POST.get("color", "bw")
        if file:
            job = PrintJob.objects.create(
                file=file,
                teacher=request.user,
                copies=copies,
                color=color,
                status="Pending",
                downloaded=False,
            )
            try:
                ActivityLog.objects.create(
                    user=request.user,
                    action="print_submit",
                    description=f"Submitted print job: {file.name}",
                )
                Notification.create_print_job_notification(job)
            except Exception as e:
                print(f"Error creating notifications: {e}")
            messages.success(request, "Print request submitted successfully.")
        else:
            messages.error(request, "Please select a file to print.")
        return redirect("digitallibrary:printing_portal")

    if profile.role in ["secretary", "admin"]:
        jobs = PrintJob.objects.all().order_by("-created_at")
        highlight_id = request.GET.get('highlight')
        if highlight_id:
            try:
                highlight_id = int(highlight_id)
            except ValueError:
                highlight_id = None
    else:
        jobs = PrintJob.objects.filter(teacher=request.user).order_by("-created_at")
        highlight_id = None

    pending_count = jobs.filter(status="Pending").count()
    return render(request, "digitallibrary/printing_portal.html", {
        "jobs": jobs,
        "role": profile.role,
        "pending_count": pending_count,
        "school": school,
        "highlight_id": highlight_id,
    })


@login_required
def mark_as_downloaded(request, job_id):
    if request.user.profile.role not in ["secretary", "admin"]:
        messages.error(request, "You don't have permission to do that.")
        return redirect("digitallibrary:printing_portal")
    job = get_object_or_404(PrintJob, id=job_id)
    job.mark_as_downloaded(user=request.user)
    try:
        ActivityLog.objects.create(
            user=request.user,
            action="print_download",
            description=f"Downloaded print job: {job.file.name}",
        )
        Notification.create_print_downloaded_notification(job)
    except Exception as e:
        print(f"Error creating notification: {e}")
    messages.success(request, f"Job '{job.file.name}' marked as downloaded.")
    return redirect("digitallibrary:printing_portal")


@login_required
def mark_as_completed(request, job_id):
    if request.user.profile.role not in ["secretary", "admin"]:
        messages.error(request, "You don't have permission to do that.")
        return redirect("digitallibrary:printing_portal")
    job = get_object_or_404(PrintJob, id=job_id)
    job.mark_as_completed(user=request.user)
    try:
        ActivityLog.objects.create(
            user=request.user,
            action="print_complete",
            description=f"Completed print job: {job.file.name}",
        )
        Notification.create_print_completed_notification(job)
    except Exception as e:
        print(f"Error creating notification: {e}")
    messages.success(request, f"Job '{job.file.name}' marked as completed.")
    return redirect("digitallibrary:printing_portal")


@login_required
def download_print_file(request, job_id):
    print_job = get_object_or_404(PrintJob, id=job_id)
    has_permission = False
    if request.user == print_job.teacher:
        has_permission = True
    try:
        if request.user.profile.role in ["secretary", "admin"]:
            has_permission = True
    except:
        pass
    if not has_permission:
        raise Http404("You don't have permission to download this file")
    if not print_job.file:
        raise Http404("No file associated with this print job")
    file_path = print_job.file.path
    if not os.path.exists(file_path):
        raise Http404("File not found")
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = 'application/octet-stream'
    if print_job.status in ["Pending", "Ready"]:
        print_job.status = "Downloaded"
        print_job.downloaded_at = timezone.now()
        print_job.save()
        try:
            Notification.objects.create(
                recipient=print_job.teacher,
                title="File Downloaded",
                message=f'Your print job "{print_job.file.name}" has been downloaded.',
                notification_type="success",
                link=reverse('digitallibrary:printing_portal')
            )
        except Exception as e:
            print(f"Error creating notification: {e}")
    try:
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            response['Content-Length'] = os.path.getsize(file_path)
            return response
    except Exception as e:
        raise Http404(f"Error reading file: {e}")


@login_required
def print_job_detail(request, job_id):
    job = get_object_or_404(PrintJob, id=job_id)
    try:
        user_role = request.user.profile.role
    except:
        user_role = "teacher"
    if user_role in ["secretary", "admin"] or job.teacher == request.user:
        return redirect(f"{reverse('digitallibrary:printing_portal')}?highlight={job_id}")
    else:
        messages.error(request, "You don't have permission to view this print job.")
        return redirect("digitallibrary:printing_portal")


def resource_detail(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    resource.increment_views()
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/resource_detail.html", {
        "r": resource,
        "school": school
    })


@login_required
def increment_resource_view(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    resource.increment_views()
    return JsonResponse({"success": True, "views": resource.views})


@login_required
@require_POST
def logout_view(request):
    try:
        ActivityLog.objects.create(user=request.user, action="logout", description="User logged out")
    except Exception:
        pass
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('/login/')


@login_required
def user_profile(request):
    profile = request.user.profile
    activities = ActivityLog.objects.filter(user=request.user)[:20]
    print_jobs = PrintJob.objects.filter(teacher=request.user)[:10]
    total_uploads = Resource.objects.filter(uploaded_by=request.user).count()
    recent_uploads = Resource.objects.filter(
        uploaded_by=request.user,
        created_at__gte=timezone.now() - timedelta(days=30)
    ).count()
    recent_resources = Resource.objects.filter(uploaded_by=request.user).order_by('-created_at')[:5]
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/profile.html", {
        "profile": profile,
        "activities": activities,
        "print_jobs": print_jobs,
        "total_uploads": total_uploads,
        "recent_uploads": recent_uploads,
        "recent_resources": recent_resources,
        "school": school,
    })


@login_required
def approve_teacher(request, user_id):
    if request.user.profile.role != "admin":
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    teacher = get_object_or_404(User, id=user_id)
    profile = teacher.profile
    if profile.role == "teacher":
        profile.is_approved = True
        profile.save()
        messages.success(request, f"Teacher {teacher.username} approved successfully.")
    return redirect("digitallibrary:manage_users")


@login_required
def activity_log(request):
    if request.user.profile.role != "admin":
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    activities = ActivityLog.objects.all()[:100]
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/activity_log.html", {
        "activities": activities,
        "school": school
    })


# ================== LIBRARY ADMIN VIEWS ==================

@login_required
def library_admin_dashboard(request):
    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied. Library Admin access only.")
        return redirect("digitallibrary:home")
    total_resources = Resource.objects.count()
    total_announcements = Announcement.objects.count()
    recent_resources = Resource.objects.order_by("-created_at")[:5]
    recent_announcements = Announcement.objects.order_by("-created_at")[:5]
    school = SchoolSetting.objects.first()
    context = {
        "total_resources": total_resources,
        "total_announcements": total_announcements,
        "recent_resources": recent_resources,
        "recent_announcements": recent_announcements,
        "school": school,
    }
    return render(request, "digitallibrary/library_admin/dashboard.html", context)


@login_required
def library_admin_resources(request):
    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    resources = Resource.objects.all().order_by("-created_at")
    q = request.GET.get("q", "")
    if q:
        resources = resources.filter(
            Q(title__icontains=q) | Q(author__icontains=q) | Q(grade__icontains=q) |
            Q(year__icontains=q) | Q(subject__name__icontains=q)
        )
    paginator = Paginator(resources, 20)
    page = request.GET.get("page", 1)
    resources = paginator.get_page(page)
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/library_admin/resources.html", {
        "resources": resources,
        "q": q,
        "school": school
    })


@login_required
def library_admin_resource_add(request):
    return redirect('digitallibrary:library_admin_resource_add_unified')


def library_admin_resource_edit(request, pk=None):
    from django.shortcuts import get_object_or_404, redirect, render
    from django.contrib import messages
    from .models import Resource, Subject
    from .forms import ResourceForm
    import datetime
    import os
    
    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied. Admin access required.")
        return redirect("digitallibrary:home")
    
    if pk:
        resource = get_object_or_404(Resource, id=pk)
        if request.method == 'POST':
            form = ResourceForm(request.POST, request.FILES, instance=resource)
            if form.is_valid():
                updated_resource = form.save()
                try:
                    ActivityLog.objects.create(
                        user=request.user,
                        action="edit",
                        description=f"Edited resource: {updated_resource.title}",
                    )
                except Exception:
                    pass
                messages.success(request, 'Resource updated successfully!')
                return redirect('digitallibrary:library_admin_resources')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        else:
            form = ResourceForm(instance=resource)
        current_file_name = None
        current_file_size = None
        if resource.file:
            current_file_name = os.path.basename(resource.file.name)
            try:
                current_file_size = resource.file.size
            except:
                pass
        current_cover_name = None
        if resource.cover_image:
            current_cover_name = os.path.basename(resource.cover_image.name)
    else:
        if request.method == 'POST':
            form = ResourceForm(request.POST, request.FILES)
            if form.is_valid():
                resource = form.save(commit=False)
                resource.uploaded_by = request.user
                resource.save()
                try:
                    ActivityLog.objects.create(
                        user=request.user,
                        action="upload",
                        description=f"Uploaded resource: {resource.title}",
                    )
                except Exception:
                    pass
                messages.success(request, 'Resource created successfully!')
                return redirect('digitallibrary:library_admin_resources')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        else:
            form = ResourceForm()
        current_file_name = None
        current_file_size = None
        current_cover_name = None
    
    current_year = datetime.datetime.now().year
    years = list(range(current_year + 5, 1949, -1))
    subjects = Subject.objects.all().order_by('name')
    school = SchoolSetting.objects.first()
    file_size_display = None
    if current_file_size:
        if current_file_size < 1024:
            file_size_display = f"{current_file_size} B"
        elif current_file_size < 1024 * 1024:
            file_size_display = f"{current_file_size / 1024:.1f} KB"
        else:
            file_size_display = f"{current_file_size / (1024 * 1024):.1f} MB"
    context = {
        'form': form,
        'resource': resource if pk else None,
        'years': years,
        'subjects': subjects,
        'title': 'Edit Resource' if pk else 'Add Resource',
        'school': school,
        'current_file_name': current_file_name,
        'current_file_size': file_size_display,
        'current_cover_name': current_cover_name,
    }
    return render(request, 'digitallibrary/library_admin/resource_form.html', context)


@login_required
def library_admin_resource_delete(request, pk):
    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    resource = get_object_or_404(Resource, pk=pk)
    school = SchoolSetting.objects.first()
    if request.method == "POST":
        resource.delete()
        messages.success(request, "Resource deleted successfully!")
        return redirect("digitallibrary:library_admin_resources")
    return render(request, "digitallibrary/library_admin/resource_confirm_delete.html", {
        "resource": resource,
        "school": school
    })


from django.db import connection
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q



@login_required
def library_admin_announcements(request):
    # SAFETY CHECK: Prevent access/queries on the public schema
    if connection.schema_name == 'public':
        messages.error(request, "This feature is only available for school tenants.")
        return redirect("digitallibrary:home")

    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    
    filter_form = AnnouncementFilterForm(request.GET)
    announcements = Announcement.objects.all().order_by("-created_at")
    
    if filter_form.is_valid():
        audience = filter_form.cleaned_data.get('audience')
        status = filter_form.cleaned_data.get('status')
        search = filter_form.cleaned_data.get('search')
        date_from = filter_form.cleaned_data.get('date_from')
        date_to = filter_form.cleaned_data.get('date_to')
        
        if audience:
            announcements = announcements.filter(target_audience=audience)
        if status == 'active':
            announcements = announcements.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        elif status == 'expired':
            announcements = announcements.filter(expires_at__lt=timezone.now())
        elif status == 'featured':
            announcements = announcements.filter(is_featured=True)
        if search:
            announcements = announcements.filter(Q(title__icontains=search) | Q(content__icontains=search))
        if date_from:
            announcements = announcements.filter(created_at__date__gte=date_from)
        if date_to:
            announcements = announcements.filter(created_at__date__lte=date_to)
    
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/library_admin/announcements.html", {
        "announcements": announcements,
        "filter_form": filter_form,
        "school": school
    })


@login_required
def library_admin_announcement_add(request):
    # SAFETY CHECK: Prevent access/queries on the public schema
    if connection.schema_name == 'public':
        messages.error(request, "This feature is only available for school tenants.")
        return redirect("digitallibrary:home")

    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    
    school = SchoolSetting.objects.first()
    if request.method == "POST":
        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.author = request.user
            announcement.save()
            messages.success(request, "Announcement created successfully!")
            return redirect("digitallibrary:library_admin_announcements")
    else:
        form = AnnouncementForm()
    return render(request, "digitallibrary/library_admin/announcement_form.html", {
        "form": form,
        "title": "Add New Announcement",
        "school": school
    })



@login_required
def library_admin_announcement_edit(request, pk):
    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    announcement = get_object_or_404(Announcement, pk=pk)
    school = SchoolSetting.objects.first()
    if request.method == "POST":
        form = AnnouncementForm(request.POST, request.FILES, instance=announcement)
        if form.is_valid():
            form.save()
            messages.success(request, "Announcement updated successfully!")
            return redirect("digitallibrary:library_admin_announcements")
    else:
        form = AnnouncementForm(instance=announcement)
    return render(request, "digitallibrary/library_admin/announcement_form.html", {
        "form": form,
        "title": "Edit Announcement",
        "announcement": announcement,
        "school": school
    })


@login_required
def library_admin_announcement_delete(request, pk):
    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    announcement = get_object_or_404(Announcement, pk=pk)
    school = SchoolSetting.objects.first()
    if request.method == "POST":
        announcement.delete()
        messages.success(request, "Announcement deleted successfully!")
        return redirect("digitallibrary:library_admin_announcements")
    return render(request, "digitallibrary/library_admin/announcement_confirm_delete.html", {
        "announcement": announcement,
        "school": school
    })


# ========== PUBLIC ANNOUNCEMENT VIEWS ==========

@login_required
def announcement_list(request):
    user = request.user
    try:
        user_role = user.profile.role
    except:
        user_role = 'student'
    announcements = Announcement.objects.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
    if user_role == 'admin' or user_role == 'principal':
        pass
    elif user_role == 'teacher':
        announcements = announcements.filter(Q(target_audience='all') | Q(target_audience='teachers') | Q(target_audience='staff'))
    elif user_role == 'student':
        announcements = announcements.filter(Q(target_audience='all') | Q(target_audience='students'))
    elif user_role == 'secretary':
        announcements = announcements.filter(Q(target_audience='all') | Q(target_audience='staff'))
    else:
        announcements = announcements.filter(target_audience='all')
    announcements = announcements.order_by("-is_featured", "-created_at")
    for announcement in announcements:
        AnnouncementRead.mark_as_read(announcement, user)
    unread_count = AnnouncementRead.get_unread_count(user)
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/announcement_list.html", {
        "announcements": announcements,
        "unread_count": unread_count,
        "user_role": user_role,
        "school": school
    })


@login_required
def announcement_detail(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    user = request.user
    try:
        user_role = user.profile.role
    except:
        user_role = 'student'
    can_view = False
    if user_role in ['admin', 'principal']:
        can_view = True
    elif announcement.target_audience == 'all':
        can_view = True
    elif announcement.target_audience == 'teachers' and user_role == 'teacher':
        can_view = True
    elif announcement.target_audience == 'students' and user_role == 'student':
        can_view = True
    elif announcement.target_audience == 'admin' and user_role in ['admin', 'principal']:
        can_view = True
    elif announcement.target_audience == 'staff' and user_role in ['admin', 'principal', 'teacher', 'secretary']:
        can_view = True
    if not can_view:
        messages.error(request, "You don't have permission to view this announcement.")
        return redirect('digitallibrary:announcement_list')
    AnnouncementRead.mark_as_read(announcement, user)
    read_stats = None
    if user_role in ['admin', 'principal']:
        read_stats = {
            'total_read': announcement.read_count(),
            'total_target': announcement.target_count(),
            'percentage': announcement.read_percentage(),
            'read_by': announcement.read_receipts.filter(read=True).select_related('user')[:10]
        }
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/announcement_detail.html", {
        "announcement": announcement,
        "read_stats": read_stats,
        "school": school
    })


@login_required
def create_announcement(request):
    if request.user.profile.role not in ['admin', 'principal']:
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    school = SchoolSetting.objects.first()
    if request.method == "POST":
        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.author = request.user
            announcement.save()
            messages.success(request, "Announcement created successfully!")
            return redirect("digitallibrary:announcement_list")
    else:
        form = AnnouncementForm()
    return render(request, "digitallibrary/create_announcement.html", {
        "form": form,
        "school": school
    })


@login_required
def edit_announcement(request, pk):
    if request.user.profile.role != "admin":
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    announcement = get_object_or_404(Announcement, pk=pk)
    school = SchoolSetting.objects.first()
    if request.method == "POST":
        form = AnnouncementForm(request.POST, request.FILES, instance=announcement)
        if form.is_valid():
            form.save()
            messages.success(request, "Announcement updated successfully.")
            return redirect("digitallibrary:announcement_list")
    else:
        form = AnnouncementForm(instance=announcement)
    return render(request, "digitallibrary/edit_announcement.html", {
        "form": form,
        "announcement": announcement,
        "school": school
    })


@login_required
def delete_announcement(request, pk):
    if request.user.profile.role != "admin":
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    announcement = get_object_or_404(Announcement, pk=pk)
    school = SchoolSetting.objects.first()
    announcement.delete()
    messages.success(request, "Announcement deleted successfully.")
    return redirect("digitallibrary:announcement_list")


@login_required
def announcement_read_stats(request, pk):
    if request.user.profile.role not in ['admin', 'principal']:
        return JsonResponse({"error": "Unauthorized"}, status=403)
    announcement = get_object_or_404(Announcement, pk=pk)
    target_users = announcement.get_target_user_queryset()
    read_records = {
        r.user_id: {
            'read_at': r.read_at,
            'username': r.user.username,
            'role': r.user.profile.role if hasattr(r.user, 'profile') else 'unknown'
        }
        for r in announcement.read_receipts.filter(read=True).select_related('user')
    }
    stats = []
    for user in target_users:
        stats.append({
            'user_id': user.id,
            'username': user.username,
            'role': user.profile.role if hasattr(user, 'profile') else 'unknown',
            'read': user.id in read_records,
            'read_at': read_records.get(user.id, {}).get('read_at', None)
        })
    stats.sort(key=lambda x: (x['read'], x['username']))
    return JsonResponse({
        'announcement_id': announcement.id,
        'announcement_title': announcement.title,
        'target_audience': announcement.get_target_audience_display(),
        'total_target': len(stats),
        'total_read': announcement.read_count(),
        'read_percentage': announcement.read_percentage(),
        'stats': stats
    })


# ================== ADMIN DASHBOARD VIEWS ==================

@login_required
def admin_dashboard(request):
    if request.user.profile.role != "admin":
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    total_resources = Resource.objects.count()
    total_users = User.objects.count()
    total_print_jobs = PrintJob.objects.count()
    pending_teachers = UserProfile.objects.filter(role="teacher", is_approved=False).count()
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/admin_dashboard.html", {
        "total_resources": total_resources,
        "total_users": total_users,
        "total_print_jobs": total_print_jobs,
        "pending_teachers": pending_teachers,
        "school": school,
    })


@login_required
def dashboard_statistics(request):
    if request.user.profile.role != "admin":
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    resources_by_grade = Resource.objects.values("grade").annotate(count=Count("id")).order_by("grade")
    resources_by_year = Resource.objects.values("year").annotate(count=Count("id")).order_by("-year")
    resources_by_subject = Resource.objects.values("subject__name").annotate(count=Count("id")).order_by("subject__name")
    print_jobs_by_status = PrintJob.objects.values("status").annotate(count=Count("id"))
    recent_activity = ActivityLog.objects.all()[:50]
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/dashboard_statistics.html", {
        "resources_by_grade": resources_by_grade,
        "resources_by_year": resources_by_year,
        "resources_by_subject": resources_by_subject,
        "print_jobs_by_status": print_jobs_by_status,
        "recent_activity": recent_activity,
        "school": school,
    })


@login_required
def manage_users(request):
    if request.user.profile.role != "admin":
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    users = UserProfile.objects.select_related("user").all()
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/manage_users.html", {
        "users": users,
        "school": school
    })


@login_required
def change_user_role(request, user_id):
    if request.user.profile.role != "admin":
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    profile = get_object_or_404(UserProfile, user_id=user_id)
    if request.method == "POST":
        new_role = request.POST.get("role")
        if new_role in dict(UserProfile.ROLE_CHOICES).keys():
            profile.role = new_role
            profile.save()
            messages.success(request, f"User role updated to {new_role}")
    return redirect("digitallibrary:manage_users")


# ================== NOTIFICATION VIEWS ==================

@login_required
def notification_list(request):
    notifications = Notification.objects.filter(recipient=request.user, is_archived=False).order_by("-created_at")
    unread = notifications.filter(is_read=False)
    unread.update(is_read=True, read_at=timezone.now())
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page', 1)
    notifications = paginator.get_page(page)
    school = SchoolSetting.objects.first()
    return render(request, 'digitallibrary/notifications.html', {
        'notifications': notifications,
        'school': school
    })


def api_notifications(request):
    """API endpoint for notifications"""
    from django.db import connection
    from django.http import JsonResponse
    
    # CRITICAL: Check public schema FIRST - no auth required
    if connection.schema_name == 'public':
        return JsonResponse({
            'unread_count': 0,
            'notifications': []
        })
    
    # For tenant schemas, require login
    if not request.user.is_authenticated:
        return JsonResponse({'unread_count': 0, 'notifications': []})
    
    notifications = Notification.objects.filter(
        recipient=request.user, 
        is_archived=False
    ).order_by("-created_at")[:20]
    
    def get_time_ago(created_at):
        from django.utils.timesince import timesince
        now = timezone.now()
        if created_at.date() == now.date():
            return f"{timesince(created_at)} ago"
        elif created_at.date() == now.date() - timedelta(days=1):
            return "Yesterday"
        else:
            return created_at.strftime("%b %d, %Y")
    
    data = {
        'unread_count': Notification.get_unread_count(request.user),
        'notifications': [{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'link': n.link or '#',
            'type': n.notification_type,
            'is_read': n.is_read,
            'time_ago': get_time_ago(n.created_at),
            'created_at': n.created_at.isoformat()
        } for n in notifications]
    }
    return JsonResponse(data)
def api_mark_notification_read(request, pk):
    from django.db import connection
    from django.http import JsonResponse
    
    if connection.schema_name == 'public':
        return JsonResponse({'success': True})
    
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_as_read()
    return JsonResponse({'success': True})
def api_mark_all_read(request):
    from django.db import connection
    from django.http import JsonResponse
    
    if connection.schema_name == 'public':
        return JsonResponse({'success': True})
    
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
    return JsonResponse({'success': True})

def api_archive_notification(request, pk):
    from django.db import connection
    from django.http import JsonResponse
    
    if connection.schema_name == 'public':
        return JsonResponse({'success': True})
    
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_archived = True
    notification.save()
    return JsonResponse({'success': True})

# ================== SUBJECT MANAGEMENT API VIEWS ==================

@login_required
def get_subjects(request):
    if request.user.profile.role not in ["admin", "principal"]:
        return JsonResponse({"error": "Unauthorized"}, status=403)
    subjects = Subject.objects.all().values("id", "name").order_by("name")
    return JsonResponse(list(subjects), safe=False)


@login_required
@require_POST
def add_subject(request):
    """Add a new subject via AJAX"""
    import json
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        subject_name = request.POST.get('name', '').strip()
        
        if not subject_name:
            return JsonResponse({'status': 'error', 'error': 'Subject name is required'}, status=400)
        
        # Check if subject already exists
        existing = Subject.objects.filter(name__iexact=subject_name).first()
        if existing:
            return JsonResponse({
                'status': 'success',
                'id': existing.id,
                'name': existing.name,
                'message': 'Subject already exists'
            })
        
        # Create new subject
        try:
            subject = Subject.objects.create(name=subject_name, is_active=True)
            return JsonResponse({
                'status': 'success',
                'id': subject.id,
                'name': subject.name
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'error': 'Invalid request'}, status=400)

@login_required
@require_POST
def delete_subject(request, pk):
    if request.user.profile.role != "admin":
        return JsonResponse({"error": "Unauthorized"}, status=403)
    try:
        subject = get_object_or_404(Subject, pk=pk)
        if subject.resources.exists():
            return JsonResponse({"error": "Cannot delete subject that is in use", "resources_count": subject.resources.count()}, status=400)
        subject.delete()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ================== CATEGORY MANAGEMENT API VIEWS ==================

@login_required
def get_categories(request):
    if request.user.profile.role not in ["admin", "principal"]:
        return JsonResponse({"error": "Unauthorized"}, status=403)
    categories = Category.objects.all().values("id", "name").order_by("name")
    return JsonResponse(list(categories), safe=False)


# ================== PUBLIC METRICS API ==================

@api_view(['GET'])
def test_metrics(request):
    data = {
        'resource_count': Resource.objects.count(),
        'resources': list(Resource.objects.all().values('id', 'title', 'year', 'subject__name', 'category__name')[:5]),
        'subjects': list(Subject.objects.all().values('id', 'name')),
        'subject_count': Subject.objects.count(),
        'categories': list(Category.objects.all().values('id', 'name')),
        'category_count': Category.objects.count(),
        'years': list(Resource.objects.exclude(year__isnull=True).exclude(year="").values_list('year', flat=True).distinct().order_by('-year')),
    }
    return Response(data)


# ============================================================
# CENTRAL DASHBOARD API VIEWS - REAL DATA FROM ALL TENANTS
# ============================================================

@api_view(['GET'])
def public_metrics(request):
    """Public API endpoint for central dashboard metrics - REAL DATA from all tenant schools"""
    from tenants.models import School
    from django_tenants.utils import tenant_context
    from django.core.cache import cache
    from django.db.models import Sum, Q
    from django.utils import timezone
    from datetime import timedelta
    
    cache_key = 'central_dashboard_metrics'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return Response(cached_data)
    
    try:
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get all tenants (schools)
        schools = School.objects.all()
        total_schools = schools.count()
        schools_this_month = schools.filter(created_on__gte=month_start).count()
        
        # Initialize counters
        total_teachers = 0
        teachers_this_month = 0
        total_resources = 0
        total_pdfs = 0
        total_views = 0
        downloads_today = 0
        views_today = 0
        total_print_jobs = 0
        prints_today = 0
        total_students = 0
        active_users_today = 0
        resources_by_subject = {}
        recent_uploads = []
        
        # Iterate through each school/tenant to collect real data
        for school in schools:
            try:
                with tenant_context(school):
                    # Teacher counts
                    teacher_count = UserProfile.objects.filter(role='teacher', is_approved=True).count()
                    total_teachers += teacher_count
                    teachers_new = UserProfile.objects.filter(
                        role='teacher',
                        created_at__gte=month_start
                    ).count()
                    teachers_this_month += teachers_new
                    
                    # Resource statistics
                    resources = Resource.objects.all()
                    total_resources += resources.count()
                    total_pdfs += resources.filter(resource_type='PDF').count()
                    total_views += resources.aggregate(total=Sum('views'))['total'] or 0
                    
                    # Today's activity
                    downloads_today += ActivityLog.objects.filter(
                        action='download',
                        timestamp__gte=today_start
                    ).count()
                    views_today += ActivityLog.objects.filter(
                        action='resource_view',
                        timestamp__gte=today_start
                    ).count()
                    
                    # Resources by subject
                    for subject in Subject.objects.filter(is_active=True):
                        count = resources.filter(subject=subject).count()
                        if count > 0:
                            subject_name = subject.name
                            resources_by_subject[subject_name] = resources_by_subject.get(subject_name, 0) + count
                    
                    # Recent uploads
                    recent = resources.order_by('-created_at')[:5]
                    for r in recent:
                        recent_uploads.append({
                            'title': r.title,
                            'school_name': school.name,
                            'created_at': r.created_at.isoformat()
                        })
                    
                    # Print jobs
                    total_print_jobs += PrintJob.objects.count()
                    prints_today += PrintJob.objects.filter(
                        created_at__gte=today_start
                    ).count()
                    
                    # Students
                    total_students += Student.objects.filter(is_active=True).count()
                    
                    # Active users today
                    active_users_today += ActivityLog.objects.filter(
                        timestamp__gte=today_start
                    ).values('user').distinct().count()
                    
            except Exception as e:
                print(f"Error processing tenant {school.schema_name}: {e}")
                continue
        
        # Sort recent uploads by date and take top 10
        recent_uploads.sort(key=lambda x: x['created_at'], reverse=True)
        recent_uploads = recent_uploads[:10]
        
        # Prepare resources by subject list
        resources_by_subject_list = [
            {'name': name, 'count': count, 'resource_count': count}
            for name, count in sorted(resources_by_subject.items(), key=lambda x: x[1], reverse=True)
        ]
        
        metrics = {
            'total_schools': total_schools,
            'schools_this_month': schools_this_month,
            'total_teachers': total_teachers,
            'teachers_this_month': teachers_this_month,
            'total_resources': total_resources,
            'total_pdfs': total_pdfs,
            'total_downloads': total_views,
            'total_views': total_views,
            'total_students': total_students,
            'total_print_jobs': total_print_jobs,
            'active_users_today': active_users_today,
            'downloads_today': downloads_today,
            'views_today': views_today,
            'prints_today': prints_today,
            'resources_by_subject': resources_by_subject_list,
            'recent_uploads': recent_uploads,
            'last_updated': now.isoformat(),
        }
        
        cache.set(cache_key, metrics, 300)
        return Response(metrics)
        
    except Exception as e:
        print(f"Error in public_metrics: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'error': str(e),
            'total_schools': 0,
            'schools_this_month': 0,
            'total_teachers': 0,
            'teachers_this_month': 0,
            'total_resources': 0,
            'total_pdfs': 0,
            'total_downloads': 0,
            'total_views': 0,
            'total_students': 0,
            'total_print_jobs': 0,
            'active_users_today': 0,
            'downloads_today': 0,
            'views_today': 0,
            'prints_today': 0,
            'resources_by_subject': [],
            'recent_uploads': [],
            'last_updated': timezone.now().isoformat(),
        }, status=200)


@api_view(['POST'])
def register_school_api(request):
    """API endpoint for school registration - sends email notification"""
    from django.conf import settings
    from django.core.mail import send_mail
    
    try:
        data = request.data
        
        school_name = data.get('school_name')
        admin_name = data.get('admin_name')
        email = data.get('email')
        phone = data.get('phone')
        location = data.get('location')
        teacher_count = data.get('teacher_count')
        student_count = data.get('student_count')
        
        # Validate required fields
        if not all([school_name, admin_name, email, phone, location]):
            return Response({
                'success': False,
                'error': 'Please fill in all required fields: school_name, admin_name, email, phone, location'
            }, status=400)
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return Response({
                'success': False,
                'error': 'Please enter a valid email address'
            }, status=400)
        
        # Send email notification to admin
        try:
            email_body = f"""
            New School Registration Request
            
            School Name: {school_name}
            Admin Name: {admin_name}
            Email: {email}
            Phone: {phone}
            Location: {location}
            Teachers: {teacher_count if teacher_count else 'Not specified'}
            Students: {student_count if student_count else 'Not specified'}
            
            Please follow up with this school to complete onboarding.
            
            ---
            This is an automated message from the School Library System.
            """
            
            send_mail(
                subject=f'New School Registration: {school_name}',
                message=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=settings.ADMIN_EMAILS,
                fail_silently=False,
            )
            print(f"Email sent to {settings.ADMIN_EMAILS}")
        except Exception as e:
            print(f"Email error: {e}")
        
        return Response({
            'success': True,
            'message': 'School registration request received! We will contact you soon.',
            'data': {
                'school_name': school_name,
                'admin_name': admin_name,
                'email': email
            }
        })
        
    except Exception as e:
        print(f"Registration error: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


@api_view(['GET'])
def central_stats(request):
    """Simple stats for the central dashboard"""
    from tenants.models import School
    from django.core.cache import cache
    from django.utils import timezone
    
    cache_key = 'central_simple_stats'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return Response(cached_data)
    
    try:
        schools = School.objects.all()
        total_schools = schools.count()
        
        stats = {
            'total_schools': total_schools,
            'status': 'active',
            'timestamp': timezone.now().isoformat()
        }
        
        cache.set(cache_key, stats, 300)
        return Response(stats)
        
    except Exception as e:
        return Response({
            'total_schools': 0,
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=200)


@api_view(['GET'])
def get_schools_list(request):
    """Get list of all registered schools (tenants)"""
    from tenants.models import School
    
    try:
        schools = School.objects.all().values('id', 'name', 'schema_name', 'created_on')
        return Response(list(schools))
    except Exception as e:
        return Response({
            'error': str(e),
            'schools': []
        }, status=200)


@api_view(['GET'])
def get_school_stats(request, school_id):
    """Get statistics for a specific school (tenant)"""
    from tenants.models import School
    from django_tenants.utils import tenant_context
    from django.db.models import Sum
    
    try:
        school = School.objects.get(id=school_id)
        
        with tenant_context(school):
            stats = {
                'school_id': school.id,
                'school_name': school.name,
                'schema_name': school.schema_name,
                'total_resources': Resource.objects.count(),
                'total_teachers': UserProfile.objects.filter(role='teacher', is_approved=True).count(),
                'total_students': Student.objects.filter(is_active=True).count(),
                'total_print_jobs': PrintJob.objects.count(),
                'total_views': Resource.objects.aggregate(total=Sum('views'))['total'] or 0,
                'total_announcements': Announcement.objects.count(),
                'total_fee_payments': FeePayment.objects.count(),
                'total_exams': Exam.objects.count(),
                'total_results': StudentResult.objects.count(),
            }
        
        return Response(stats)
    except School.DoesNotExist:
        return Response({'error': 'School not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)


# ============================================================
# FEES MANAGEMENT VIEWS
# ============================================================

@login_required
def fees_dashboard(request):
    """Main fees dashboard with statistics - Accessible by Admin, Principal, and Bursar"""
    from decimal import Decimal
    
    # Role-based access control
    user_role = request.user.profile.role
    if user_role not in ['admin', 'principal', 'bursar']:
        messages.error(request, f"Access Denied. {user_role.capitalize()}s cannot access the fees dashboard.")
        return redirect('digitallibrary:home')
    
    current_year = request.GET.get('year', str(timezone.now().year))
    current_term = request.GET.get('term', '1')  # Changed default to 1
    
    try:
        current_term = int(current_term)
    except ValueError:
        current_term = 1
    
    # Get all students with their classes
    students = Student.objects.filter(is_active=True).select_related('current_class')
    total_students = students.count()
    
    # Get all fee structures for the selected period
    fee_structures = FeeStructure.objects.filter(
        academic_year=current_year,
        term=current_term
    ).select_related('student_class')
    
    # Create a mapping of class_id -> total fees for that class
    class_fee_map = {}
    for fs in fee_structures:
        if fs.student_class:
            class_fee_map[fs.student_class.id] = Decimal(str(fs.total_fees))
    
    # Calculate total expected: sum of expected fees per student
    total_expected_all = Decimal('0')
    students_with_fee_structure = 0
    students_without_fee_structure = 0
    
    for student in students:
        if student.current_class:
            class_id = student.current_class.id
            if class_id in class_fee_map:
                total_expected_all += class_fee_map[class_id]
                students_with_fee_structure += 1
            else:
                students_without_fee_structure += 1
        else:
            students_without_fee_structure += 1
    
    # Get total paid from payments
    total_paid_all = FeePayment.objects.filter(
        academic_year=current_year,
        term=current_term
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    if not isinstance(total_paid_all, Decimal):
        total_paid_all = Decimal(str(total_paid_all))
    
    # Calculate balance
    total_balance_all = total_expected_all - total_paid_all
    
    # Get fee balances
    balances = FeeBalance.objects.filter(
        academic_year=current_year,
        term=current_term
    ).select_related('student')
    
    # Count by status
    paid_count = balances.filter(status='PAID').count()
    partial_count = balances.filter(status='PARTIAL').count()
    defaulting_count = balances.filter(status='DEFAULTING').count()
    overpaid_count = balances.filter(status='OVERPAID').count()
    
    # If no balances exist, count all students as defaulting
    if balances.count() == 0 and total_students > 0:
        defaulting_count = total_students
        paid_count = 0
        partial_count = 0
    
    # Calculate collection percentage
    if total_expected_all > 0:
        collection_percentage = float(total_paid_all / total_expected_all * 100)
    else:
        collection_percentage = 0
    
    # Recent payments
    recent_payments = FeePayment.objects.filter(
        academic_year=current_year,
        term=current_term
    ).order_by('-payment_date')[:10]
    
    # Defaulters list
    defaulters = []
    for balance in balances.filter(balance__gt=0).exclude(status='OVERPAID'):
        defaulters.append({
            'student': balance.student,
            'balance': balance.balance,
            'total_expected': balance.total_expected,
            'total_paid': balance.total_paid,
            'status': balance.status
        })
    
    # Add students with no balance record
    students_with_balance = balances.values('student').distinct().count()
    if students_with_balance < total_students:
        for student in students:
            if not balances.filter(student=student).exists():
                expected = Decimal('0')
                if student.current_class and student.current_class.id in class_fee_map:
                    expected = class_fee_map[student.current_class.id]
                if expected > 0:
                    defaulters.append({
                        'student': student,
                        'balance': expected,
                        'total_expected': expected,
                        'total_paid': Decimal('0'),
                        'status': 'DEFAULTING'
                    })
    
    # Remove duplicates
    seen = set()
    unique_defaulters = []
    for d in defaulters:
        if d['student'].id not in seen:
            seen.add(d['student'].id)
            unique_defaulters.append(d)
    unique_defaulters.sort(key=lambda x: x['balance'], reverse=True)
    defaulters = unique_defaulters[:20]
    
    # Class-wise breakdown
    class_breakdown = []
    for class_obj in Class.objects.all().order_by('name'):
        student_count = students.filter(current_class=class_obj).count()
        if student_count > 0:
            if class_obj.id in class_fee_map:
                fee_amount = class_fee_map[class_obj.id]
                total_expected_for_class = student_count * fee_amount
                total_paid_for_class = FeePayment.objects.filter(
                    academic_year=current_year,
                    term=current_term,
                    student__current_class=class_obj
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
                
                if not isinstance(total_paid_for_class, Decimal):
                    total_paid_for_class = Decimal(str(total_paid_for_class))
                
                if total_expected_for_class > 0:
                    collection_pct = float(total_paid_for_class / total_expected_for_class * 100)
                else:
                    collection_pct = 0
                
                class_breakdown.append({
                    'name': class_obj.name,
                    'students': student_count,
                    'fee_per_student': float(fee_amount),
                    'total_expected': float(total_expected_for_class),
                    'total_paid': float(total_paid_for_class),
                    'balance': float(total_expected_for_class - total_paid_for_class),
                    'collection_percentage': round(collection_pct, 1)
                })
            else:
                class_breakdown.append({
                    'name': class_obj.name,
                    'students': student_count,
                    'fee_per_student': 0,
                    'total_expected': 0,
                    'total_paid': 0,
                    'balance': 0,
                    'collection_percentage': 0,
                    'no_fee_structure': True
                })
    
    # Available years
    available_years = FeeStructure.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    if not available_years:
        available_years = [current_year]
    
    # Get school settings for template
    school = SchoolSetting.objects.first()
    
    context = {
        'current_year': current_year,
        'current_term': current_term,
        'total_expected': float(total_expected_all),
        'total_paid': float(total_paid_all),
        'total_balance': float(total_balance_all),
        'collection_percentage': round(collection_percentage, 1),
        'paid_count': paid_count,
        'partial_count': partial_count,
        'defaulting_count': defaulting_count,
        'overpaid_count': overpaid_count,
        'recent_payments': recent_payments,
        'defaulters': defaulters,
        'available_years': available_years,
        'class_breakdown': class_breakdown,
        'total_students': total_students,
        'school': school,
        'school_name': school.name if school else 'School Name',
        'school_logo': school.logo.url if school and school.logo else None,
    }
    return render(request, 'fees/dashboard.html', context)
@login_required
def get_subject_students(request, exam_id):
    """AJAX endpoint to get students for a specific subject under an exam"""
    exam = get_object_or_404(Exam, id=exam_id)
    subject_id = request.GET.get('subject_id')
    
    if not subject_id:
        return JsonResponse({'success': False, 'error': 'No subject selected'})
    
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Get students based on exam's class selection
    if exam.student_class:
        students = exam.student_class.students.all()
    else:
        students = Student.objects.all()
    
    # Get existing results for this exam and subject
    existing_results = ExamResult.objects.filter(
        exam=exam, 
        subject=subject,
        student__in=students
    ).select_related('student')
    
    results_dict = {result.student_id: result for result in existing_results}
    
    # Prepare data for frontend
    students_data = []
    for student in students:
        result = results_dict.get(student.id)
        students_data.append({
            'id': student.id,
            'admission_number': student.admission_number,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'score': result.score if result else None,
            'grade': result.grade if result else None
        })
    
    return JsonResponse({
        'success': True,
        'subject': {
            'id': subject.id,
            'name': subject.name
        },
        'students': students_data,
        'max_score': exam.max_score,
        'existing_count': len(existing_results),
        'total_count': students.count()
    })
@tenant_app_view
def enter_results_form(request):
    """
    Streamlined results entry page - select exam first, then subject, then enter scores.
    Auto-loads students and supports keyboard shortcuts for rapid data entry.
    """
    from .models import Exam, Subject, Student, Class
    
    # Try to import the correct Result model
    Result = None
    result_model_names = ['Result', 'ExamResult', 'StudentResult', 'AcademicResult', 'PerformanceResult']
    
    for model_name in result_model_names:
        try:
            Result = getattr(__import__('digitallibrary.models', fromlist=[model_name]), model_name)
            if Result:
                print(f"Successfully imported {model_name}")
                break
        except (ImportError, AttributeError):
            continue
    
    # Get all exams and subjects (tenant middleware will filter by schema)
    exams = Exam.objects.all().order_by('-academic_year', '-created_at')
    subjects = Subject.objects.all().order_by('name')
    
    # Get selected exam and subject from GET or POST
    selected_exam_id = request.GET.get('exam') or request.POST.get('exam_id')
    selected_subject_id = request.GET.get('subject') or request.POST.get('subject_id')
    
    selected_exam = None
    selected_subject = None
    students = []
    existing_results = {}
    
    if selected_exam_id:
        try:
            selected_exam = exams.get(id=selected_exam_id)
            
            # Get students based on exam's class or all active students
            if selected_exam.student_class:
                students = list(selected_exam.student_class.students.filter(is_active=True))
            else:
                # If no specific class, get all active students
                students = list(Student.objects.filter(is_active=True))
            
            # Order students for consistent display
            students.sort(key=lambda x: (x.first_name, x.last_name))
            
            # If Result model exists and subject is selected, get existing results
            if Result and selected_subject_id:
                try:
                    selected_subject = subjects.get(id=selected_subject_id)
                    
                    # Build filter - no school field since it's handled by tenant schema
                    results = Result.objects.filter(
                        exam=selected_exam,
                        subject=selected_subject,
                        student__in=students
                    )
                    existing_results = {r.student_id: r for r in results}
                    
                except Subject.DoesNotExist:
                    pass
                except Exception as e:
                    print(f"Error fetching results: {e}")
                    
        except Exam.DoesNotExist:
            messages.error(request, 'Selected exam not found')
            selected_exam = None
    
    # Handle POST request - save results
    if request.method == 'POST':
        exam_id = request.POST.get('exam_id')
        subject_id = request.POST.get('subject_id')
        
        if not exam_id or not subject_id:
            messages.error(request, 'Missing exam or subject selection')
        elif not Result:
            messages.error(request, 'Result model not found. Please contact administrator.')
        else:
            try:
                exam = Exam.objects.get(id=exam_id)
                subject = Subject.objects.get(id=subject_id)
                
                saved_count = 0
                error_count = 0
                
                for key, value in request.POST.items():
                    if key.startswith('score_') and value.strip():
                        student_id = key.replace('score_', '')
                        try:
                            score = float(value)
                            
                            # Validate score range
                            if score < 0:
                                error_count += 1
                                continue
                            if score > exam.max_score:
                                error_count += 1
                                continue
                            
                            # Get the student
                            student = Student.objects.get(id=student_id)
                            
                            # Create or update the result
                            result, created = Result.objects.update_or_create(
                                exam=exam,
                                subject=subject,
                                student=student,
                                defaults={'score': score}
                            )
                            saved_count += 1
                            
                        except (ValueError, TypeError) as e:
                            error_count += 1
                            print(f"Value error for student {student_id}: {e}")
                        except Student.DoesNotExist:
                            error_count += 1
                            print(f"Student not found: {student_id}")
                        except Exception as e:
                            error_count += 1
                            print(f"Unexpected error: {e}")
                
                if saved_count > 0:
                    messages.success(request, f'Successfully saved {saved_count} results for {subject.name}')
                    if error_count > 0:
                        messages.warning(request, f'Failed to save {error_count} records. Please check score values.')
                else:
                    messages.warning(request, 'No results were saved. Please check your input.')
                
                # Redirect to refresh the page with saved data
                return redirect(f'{request.path}?exam={exam_id}&subject={subject_id}')
                
            except Exam.DoesNotExist:
                messages.error(request, 'Invalid exam selected')
            except Subject.DoesNotExist:
                messages.error(request, 'Invalid subject selected')
            except Exception as e:
                messages.error(request, f'Error saving results: {str(e)}')
    
    # Prepare context data for template - FIXED: use len() instead of .count()
    context = {
        'exams': exams,
        'subjects': subjects,
        'selected_exam': selected_exam,
        'selected_subject': selected_subject,
        'students': students,
        'existing_results': existing_results,
        'has_result_model': Result is not None,
        'total_students': len(students),  # FIXED: changed from students.count()
        'saved_count': len(existing_results),
    }
    
    return render(request, 'performance/enter_results_form.html', context)
def check_result_model(request):
    """
    Debug view to check what Result models are available
    """
    from django.apps import apps
    
    result_models = []
    for model in apps.get_models():
        model_name = model.__name__.lower()
        if 'result' in model_name:
            result_models.append({
                'name': model.__name__,
                'fields': [f.name for f in model._meta.fields],
                'app': model._meta.app_label
            })
    
    context = {
        'result_models': result_models,
        'total_models': len(result_models)
    }
    
    return render(request, 'debug/models_check.html', context)
def download_fee_structure(request, fee_structure_id):
    """Download fee structure as a professional PDF with school details"""
    from datetime import datetime
    
    fee_structure = get_object_or_404(FeeStructure, pk=fee_structure_id)
    components = fee_structure.custom_fees.all()
    total = sum(c.amount for c in components)
    school = SchoolSetting.objects.first()
    
    # Create PDF response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Fee_Structure_{fee_structure.student_class.name}_Term{fee_structure.term}_{fee_structure.academic_year}.pdf"'
    
    # Create PDF document
    doc = SimpleDocTemplate(
        response, 
        pagesize=A4,
        topMargin=0.7*inch,
        bottomMargin=0.7*inch,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch
    )
    styles = getSampleStyleSheet()
    elements = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#1a4d8c'),
        alignment=TA_CENTER,
        spaceAfter=5,
        fontName='Helvetica-Bold'
    )
    
    motto_style = ParagraphStyle(
        'MottoStyle',
        parent=styles['Italic'],
        fontSize=10,
        textColor=colors.HexColor('#888888'),
        alignment=TA_CENTER,
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )
    
    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#1a4d8c'),
        spaceAfter=10,
        spaceBefore=15,
        fontName='Helvetica-Bold'
    )
    
    # Header Section
    school_name = school.name if school else "OUR SCHOOL"
    elements.append(Paragraph(school_name.upper(), title_style))
    
    if school and school.motto:
        elements.append(Paragraph(school.motto, motto_style))
    else:
        elements.append(Paragraph("Excellence in Education", motto_style))
    
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("FEE STRUCTURE", subtitle_style))
    
    class_term_text = f"{fee_structure.student_class.name} | Term {fee_structure.term} | {fee_structure.academic_year}"
    elements.append(Paragraph(class_term_text, subtitle_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # School Details Table
    elements.append(Paragraph("SCHOOL INFORMATION", section_style))
    
    school_data = []
    school_data.append(["📍 Address:", school.address if school and school.address else "Not specified"])
    school_data.append(["📞 Phone:", school.phone if school and school.phone else "Not specified"])
    school_data.append(["✉️ Email:", school.email if school and school.email else "Not specified"])
    if school and school.principal_name:
        school_data.append(["👨‍🎓 Principal:", school.principal_name])
    
    school_table = Table(school_data, colWidths=[1.5*inch, 4.5*inch])
    school_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1a4d8c')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(school_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Fee Breakdown Table
    elements.append(Paragraph("FEE BREAKDOWN", section_style))
    
    table_data = [['#', 'Fee Component', 'Amount (KES)']]
    for idx, component in enumerate(components, 1):
        table_data.append([str(idx), component.name, f"{component.amount:,.2f}"])
    table_data.append(['', '', ''])
    table_data.append(['', 'TOTAL FEES', f"KES {total:,.2f}"])
    
    table = Table(table_data, colWidths=[0.6*inch, 4*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a4d8c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f0fe')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#1a4d8c')),
        ('GRID', (0, 0), (-1, -3), 0.5, colors.HexColor('#dddddd')),
        ('LINEABOVE', (0, -2), (-1, -2), 1, colors.HexColor('#1a4d8c')),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Payment Terms
    if fee_structure.payment_terms:
        elements.append(Paragraph("PAYMENT TERMS & CONDITIONS", section_style))
        terms_style = ParagraphStyle('TermsStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#555555'), leftIndent=10)
        elements.append(Paragraph(fee_structure.payment_terms, terms_style))
    
    # Important Notes
    if fee_structure.notes:
        elements.append(Paragraph("IMPORTANT NOTES", section_style))
        notes_style = ParagraphStyle('NotesStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#555555'), leftIndent=10)
        elements.append(Paragraph(fee_structure.notes, notes_style))
    
    # Signature Section
    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("DECLARATION", section_style))
    
    declaration_text = '<para fontSize="10" textColor="#333333" alignment="CENTER">I acknowledge receipt of this fee structure and agree to pay the fees as per the schedule above.</para>'
    elements.append(Paragraph(declaration_text, styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    signature_data = [
        ["Student's Signature:", "", "", "Parent/Guardian Signature:", ""],
        ["Date:", "", "", "Date:", ""],
    ]
    
    signature_table = Table(signature_data, colWidths=[1.8*inch, 0.3*inch, 0.5*inch, 1.8*inch, 0.3*inch])
    signature_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LINEBELOW', (0, 0), (0, 0), 0.5, colors.HexColor('#999999')),
        ('LINEBELOW', (3, 0), (3, 0), 0.5, colors.HexColor('#999999')),
        ('LINEBELOW', (0, 1), (0, 1), 0.5, colors.HexColor('#999999')),
        ('LINEBELOW', (3, 1), (3, 1), 0.5, colors.HexColor('#999999')),
    ]))
    elements.append(signature_table)
    
    # Footer
    stamp_text = f'<para alignment="CENTER" fontSize="8" textColor="#999999">This is an official document issued by {school_name}.<br/>Generated on {datetime.now().strftime("%d %B, %Y at %I:%M %p")}</para>'
    elements.append(Paragraph(stamp_text, styles['Normal']))
    
    doc.build(elements)
    return response


@staff_member_required
def export_fees_csv(request):
    """Export fee data to CSV"""
    current_year = request.GET.get('year', str(timezone.now().year))
    current_term = request.GET.get('term', '1')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="fee_report_{current_year}_term{current_term}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Admission Number', 'Student Name', 'Class', 'Total Expected', 'Total Paid', 'Balance', 'Status'])
    
    balances = FeeBalance.objects.filter(
        academic_year=current_year,
        term=current_term
    ).select_related('student')
    
    for balance in balances:
        writer.writerow([
            balance.student.admission_number,
            balance.student.get_full_name(),
            balance.student.current_class.name if balance.student.current_class else 'N/A',
            f"KES {balance.total_expected:,.2f}",
            f"KES {balance.total_paid:,.2f}",
            f"KES {balance.balance:,.2f}",
            balance.status
        ])
    
    return response


@tenant_app_view
def fee_structure_list(request):
    """List all fee structures"""
    fee_structures = FeeStructure.objects.all().select_related('student_class').order_by('-academic_year', 'student_class__name')
    
    year = request.GET.get('year')
    if year:
        fee_structures = fee_structures.filter(academic_year=year)
    
    term = request.GET.get('term')
    if term:
        try:
            fee_structures = fee_structures.filter(term=int(term))
        except ValueError:
            pass
    
    # Refresh totals
    for fs in fee_structures:
        if fs.pk:
            current_total = fs.calculate_total()
            if fs.total_fees != current_total:
                fs.total_fees = current_total
                fs.save(update_fields=['total_fees'])
    
    available_years = FeeStructure.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    
    context = {
        'fee_structures': fee_structures,
        'current_year': request.GET.get('year', str(timezone.now().year)),
        'current_term': request.GET.get('term', ''),
        'available_years': available_years,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'fees/fee_structure_list.html', context)


def fee_structure_create(request):
    """Create new fee structure with dynamic components"""
    from .models import Class as ClassModel  # Add this import inside the function
    
    if request.method == 'POST':
        form = FeeStructureForm(request.POST)
        if form.is_valid():
            fee_structure = form.save()
            
            # Process fee components
            for key, value in request.POST.items():
                if key.startswith('new_component_name_'):
                    index = key.replace('new_component_name_', '')
                    name = value.strip()
                    amount = request.POST.get(f'new_component_amount_{index}', '')
                    is_optional = request.POST.get(f'new_component_optional_{index}') == 'on'
                    description = request.POST.get(f'new_component_description_{index}', '')
                    
                    if name and amount:
                        try:
                            FeeComponent.objects.create(
                                fee_structure=fee_structure,
                                name=name,
                                amount=float(amount),
                                is_optional=is_optional,
                                description=description
                            )
                        except ValueError:
                            pass
            
            total = fee_structure.calculate_total()
            fee_structure.total_fees = total
            fee_structure.save(update_fields=['total_fees'])
            
            messages.success(request, f'Fee structure created successfully! Total: KES {total:,.2f}')
            return redirect('digitallibrary:fee_structure_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = FeeStructureForm()
    
    # Get all classes for the dropdown
    try:
        from .models import Class as ClassModel
        classes = ClassModel.objects.filter(is_active=True).order_by('name')
    except:
        classes = []
    
    context = {
        'form': form,
        'title': 'Create Fee Structure',
        'is_edit': False,
        'classes': classes,
    }
    return render(request, 'fees/fee_structure_form.html', context)

def fee_structure_edit(request, pk):
    """Edit fee structure with dynamic components"""
    from .models import Class as ClassModel  # Add import
    
    fee_structure = get_object_or_404(FeeStructure, pk=pk)
    fee_components = fee_structure.custom_fees.all()
    
    if request.method == 'POST':
        form = FeeStructureForm(request.POST, instance=fee_structure)
        if form.is_valid():
            fee_structure = form.save()
            
            kept_component_ids = []
            
            # Process existing components
            for key, value in request.POST.items():
                if key.startswith('component_id_'):
                    component_id = int(value)
                    kept_component_ids.append(component_id)
                    
                    name = request.POST.get(f'component_name_{component_id}', '')
                    amount = request.POST.get(f'component_amount_{component_id}', '')
                    is_optional = request.POST.get(f'component_optional_{component_id}') == 'on'
                    description = request.POST.get(f'component_description_{component_id}', '')
                    
                    if name and amount:
                        try:
                            FeeComponent.objects.update_or_create(
                                id=component_id,
                                defaults={
                                    'fee_structure': fee_structure,
                                    'name': name,
                                    'amount': float(amount),
                                    'is_optional': is_optional,
                                    'description': description
                                }
                            )
                        except ValueError:
                            FeeComponent.objects.filter(id=component_id).delete()
                    else:
                        FeeComponent.objects.filter(id=component_id).delete()
            
            # Delete removed components
            fee_structure.custom_fees.exclude(id__in=kept_component_ids).delete()
            
            # Add new components
            for key, value in request.POST.items():
                if key.startswith('new_component_name_'):
                    index = key.replace('new_component_name_', '')
                    name = value.strip()
                    amount = request.POST.get(f'new_component_amount_{index}', '')
                    is_optional = request.POST.get(f'new_component_optional_{index}') == 'on'
                    description = request.POST.get(f'new_component_description_{index}', '')
                    
                    if name and amount:
                        try:
                            FeeComponent.objects.create(
                                fee_structure=fee_structure,
                                name=name,
                                amount=float(amount),
                                is_optional=is_optional,
                                description=description
                            )
                        except ValueError:
                            pass
            
            total = fee_structure.calculate_total()
            fee_structure.total_fees = total
            fee_structure.save(update_fields=['total_fees'])
            
            messages.success(request, f'Fee structure updated successfully! Total: KES {total:,.2f}')
            return redirect('digitallibrary:fee_structure_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = FeeStructureForm(instance=fee_structure)
    
    components_data = []
    for component in fee_components:
        components_data.append({
            'id': component.id,
            'name': component.name,
            'amount': str(component.amount),
            'is_optional': component.is_optional,
            'description': component.description or '',
        })
    
    # Get all classes for the dropdown
    try:
        classes = ClassModel.objects.filter(is_active=True).order_by('name')
    except:
        classes = []
    
    context = {
        'form': form,
        'title': f'Edit Fee Structure - {fee_structure.student_class.name if fee_structure.student_class else "N/A"}',
        'fee_structure': fee_structure,
        'fee_components': components_data,
        'is_edit': True,
        'classes': classes,
    }
    return render(request, 'fees/fee_structure_form.html', context)


def fee_structure_delete(request, pk):
    """Delete a fee structure"""
    fee_structure = get_object_or_404(FeeStructure, pk=pk)
    
    if request.method == 'POST':
        class_name = fee_structure.student_class.name if fee_structure.student_class else 'N/A'
        term = fee_structure.term
        year = fee_structure.academic_year
        fee_structure.delete()
        messages.success(request, f'Fee structure for {class_name} - Term {term} {year} deleted successfully!')
        return redirect('digitallibrary:fee_structure_list')
    
    context = {
        'fee_structure': fee_structure,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'fees/fee_structure_confirm_delete.html', context)


def fee_structure_delete_component(request, pk):
    """Delete a fee component via AJAX"""
    if request.method == 'POST':
        try:
            component = get_object_or_404(FeeComponent, pk=pk)
            component.delete()
            return JsonResponse({'success': True, 'message': 'Component deleted successfully'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@tenant_app_view
def student_list(request):
    """List all students"""
    students = Student.objects.filter(is_active=True).select_related('current_class')
    
    search_form = StudentSearchForm(request.GET)
    if search_form.is_valid():
        query = search_form.cleaned_data.get('query')
        class_filter = search_form.cleaned_data.get('class_filter')
        gender_filter = search_form.cleaned_data.get('gender_filter')
        status_filter = search_form.cleaned_data.get('status_filter')
        
        if query:
            students = students.filter(
                Q(admission_number__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(parent_phone__icontains=query) |
                Q(upi_number__icontains=query)
            )
        
        if class_filter:
            students = students.filter(current_class=class_filter)
        
        if gender_filter:
            students = students.filter(gender=gender_filter)
        
        if status_filter == 'active':
            students = students.filter(is_active=True)
        elif status_filter == 'inactive':
            students = students.filter(is_active=False)
    
    paginator = Paginator(students, 20)
    page_number = request.GET.get('page')
    students_page = paginator.get_page(page_number)
    
    classes = Class.objects.all().order_by('name')
    students_with_phone = Student.objects.filter(is_active=True, parent_phone__isnull=False).exclude(parent_phone='').count()
    
    male_count = Student.objects.filter(is_active=True, gender='M').count()
    female_count = Student.objects.filter(is_active=True, gender='F').count()
    other_count = Student.objects.filter(is_active=True, gender='O').count()
    total_students = Student.objects.filter(is_active=True).count()
    active_students = students.count()
    
    context = {
        'students': students_page,
        'search_form': search_form,
        'classes': classes,
        'students_with_phone': students_with_phone,
        'male_count': male_count,
        'female_count': female_count,
        'other_count': other_count,
        'total_students': total_students,
        'active_students': active_students,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'fees/student_list.html', context)


def student_detail(request, pk):
    """View student details with fee information"""
    from django.db.models import Sum
    
    student = get_object_or_404(Student, pk=pk)
    current_year = request.GET.get('year', str(timezone.now().year))
    current_term = int(request.GET.get('term', '1'))
    
    fee_balances = FeeBalance.objects.filter(
        student=student,
        academic_year=current_year
    ).order_by('term')
    
    payments = FeePayment.objects.filter(student=student).order_by('-payment_date')
    total_paid = payments.aggregate(total=Sum('amount'))['total'] or 0
    
    # Safely get the class ID to avoid query errors
    class_id = student.current_class.id if student.current_class else None
    
    total_expected = FeeStructure.objects.filter(
        academic_year=current_year,
        term=current_term,
        student_class_id=class_id
    ).aggregate(total=Sum('total_fees'))['total'] or 0
    
    current_balance = total_expected - total_paid
    classes = Class.objects.all().order_by('name')
    
    available_years = FeePayment.objects.filter(student=student).values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    if not available_years:
        available_years = [current_year]
    
    context = {
        'student': student,
        'fee_balances': fee_balances,
        'payments': payments,
        'total_paid': total_paid,
        'total_expected': total_expected,
        'current_balance': current_balance,
        'current_year': current_year,
        'current_term': current_term,
        'classes': classes,
        'available_years': available_years,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'fees/student_detail.html', context)

import pandas as pd
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.core.validators import ValidationError
from .forms import BulkStudentUploadForm
from .models import Student, Class

def student_bulk_upload(request):
    """Bulk upload students via Excel/CSV"""
    if request.method == 'POST':
        form = BulkStudentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            
            # Read file based on extension
            ext = excel_file.name.split('.')[-1].lower()
            try:
                if ext == 'csv':
                    df = pd.read_csv(excel_file)
                else:
                    df = pd.read_excel(excel_file)
            except Exception as e:
                messages.error(request, f'Error reading file: {str(e)}')
                return redirect('digitallibrary:student_bulk_upload')
            
            # Normalize columns (remove spaces, convert to lowercase)
            df.columns = df.columns.str.strip().str.lower()
            
            # Check for required columns
            required_fields = ['first name', 'last name', 'admission number']
            missing_fields = [f for f in required_fields if f not in df.columns]
            if missing_fields:
                messages.error(request, f'Missing required columns: {", ".join(missing_fields)}')
                return redirect('digitallibrary:student_bulk_upload')
            
            # Statistics
            success_count = 0
            error_count = 0
            errors = []
            new_classes_created = set()
            
            for index, row in df.iterrows():
                try:
                    # Skip empty rows
                    if pd.isna(row.get('first name', '')) and pd.isna(row.get('last name', '')):
                        continue
                    
                    # Get or create class
                    class_obj = None
                    class_name = row.get('class name', '')
                    if pd.notna(class_name) and str(class_name).strip():
                        class_name = str(class_name).strip()
                        class_obj, created = Class.objects.get_or_create(
                            name__iexact=class_name,
                            defaults={'name': class_name}
                        )
                        if created:
                            new_classes_created.add(class_name)
                    
                    # Get gender value
                    gender_map = {'MALE': 'M', 'M': 'M', 'FEMALE': 'F', 'F': 'F', 
                                  'OTHER': 'O', 'O': 'O'}
                    gender_raw = str(row.get('gender', 'N')).upper().strip()
                    gender = gender_map.get(gender_raw, 'N')
                    
                    # Get admission year - FIXED: handle non-numeric values
                    admission_year = 2026  # default
                    year_value = row.get('admission year', '')
                    if pd.notna(year_value):
                        try:
                            # Convert to string first, then try to extract year
                            year_str = str(year_value).strip()
                            # Try to convert to int
                            admission_year = int(float(year_str)) if year_str else 2026
                        except (ValueError, TypeError):
                            # If not a number, keep default
                            admission_year = 2026
                    
                    # Check if student already exists
                    admission_number = str(row.get('admission number', '')).strip()
                    if not admission_number:
                        errors.append(f'Row {index + 2}: Admission number is required')
                        error_count += 1
                        continue
                        
                    if Student.objects.filter(admission_number=admission_number).exists():
                        errors.append(f'Row {index + 2}: Student with admission number {admission_number} already exists')
                        error_count += 1
                        continue
                    
                    # Get first and last name
                    first_name = str(row.get('first name', '')).strip()
                    last_name = str(row.get('last name', '')).strip()
                    
                    if not first_name or not last_name:
                        errors.append(f'Row {index + 2}: First name and last name are required')
                        error_count += 1
                        continue
                    
                    # Create student
                    student = Student(
                        first_name=first_name,
                        last_name=last_name,
                        admission_number=admission_number,
                        upi_number=str(row.get('upi number', '')).strip() if pd.notna(row.get('upi number', '')) else '',
                        middle_name=str(row.get('middle name', '')).strip() if pd.notna(row.get('middle name', '')) else '',
                        gender=gender,
                        admission_year=admission_year,
                        current_class=class_obj,
                        parent_name=str(row.get('parent name', '')).strip() if pd.notna(row.get('parent name', '')) else '',
                        parent_email=str(row.get('parent email', '')).strip() if pd.notna(row.get('parent email', '')) else '',
                        parent_phone=str(row.get('parent phone', '')).strip() if pd.notna(row.get('parent phone', '')) else '',
                        parent_alternative_phone=str(row.get('alternative phone', '')).strip() if pd.notna(row.get('alternative phone', '')) else '',
                        physical_address=str(row.get('physical address', '')).strip() if pd.notna(row.get('physical address', '')) else '',
                        is_active=str(row.get('active', 'TRUE')).upper() in ['TRUE', 'YES', '1', 'ACTIVE', 'Y']
                    )
                    
                    # Validate and save
                    try:
                        student.full_clean()
                        student.save()
                        success_count += 1
                    except ValidationError as e:
                        error_msg = ', '.join(e.messages)
                        errors.append(f'Row {index + 2}: {error_msg}')
                        error_count += 1
                        
                except Exception as e:
                    # FIXED: Convert error to string properly
                    error_text = str(e)
                    errors.append(f'Row {index + 2}: {error_text}')
                    error_count += 1
            
            # Summary message
            summary = f'Successfully imported {success_count} students. Failed: {error_count}'
            if new_classes_created:
                summary += f' | Created classes: {", ".join(new_classes_created)}'
            
            if success_count > 0:
                messages.success(request, summary)
            if errors:
                # Show first 5 errors
                error_preview = errors[:5]
                for error in error_preview:
                    messages.warning(request, error)
                if len(errors) > 5:
                    messages.info(request, f'And {len(errors) - 5} more errors...')
            
            return redirect('digitallibrary:student_list')
    else:
        form = BulkStudentUploadForm()
    
    return render(request, 'digitallibrary/student_bulk_upload.html', {
        'form': form,
        'title': 'Bulk Upload Students'
    })
@staff_member_required
def student_create(request):
    """Create new student"""
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            current_year = str(timezone.now().year)
            current_term = 1
            
            # Fix: Make sure we're working with a ClassLevel object, not a string
            if student.current_class and isinstance(student.current_class, ClassLevel):
                try:
                    fee_structure = FeeStructure.objects.get(
                        academic_year=current_year,
                        term=current_term,
                        student_class=student.current_class
                    )
                    FeeBalance.objects.create(
                        student=student,
                        term=current_term,
                        academic_year=current_year,
                        total_expected=fee_structure.total_fees,
                        total_paid=0,
                        balance=fee_structure.total_fees,
                        status='DEFAULTING'
                    )
                    messages.info(request, f'Initial fee balance of KES {fee_structure.total_fees:,.2f} created for {student.get_full_name()}')
                except FeeStructure.DoesNotExist:
                    messages.warning(request, f'Student created but no fee structure found for {student.current_class.name}. Please create a fee structure first.')
            else:
                messages.info(request, f'Student {student.get_full_name()} created without a class assignment. No fee balance created.')
            
            messages.success(request, f'Student {student.get_full_name()} created successfully!')
            return redirect('digitallibrary:student_detail', pk=student.pk)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = StudentForm()
    
    classes = Class.objects.all().order_by('name')
    
    return render(request, 'fees/student_form.html', {
        'form': form, 
        'title': 'Add Student',
        'classes': classes,
        'school': SchoolSetting.objects.first(),
    })

@staff_member_required
def student_edit(request, pk):
    """Edit student"""
    student = get_object_or_404(Student, pk=pk)
    
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            student = form.save()
            messages.success(request, f'Student {student.get_full_name()} updated successfully!')
            return redirect('digitallibrary:student_detail', pk=student.pk)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = StudentForm(instance=student)
    
    classes = Class.objects.all().order_by('name')
    
    return render(request, 'fees/student_form.html', {
        'form': form, 
        'title': 'Edit Student',
        'classes': classes,
        'student': student,
        'school': SchoolSetting.objects.first(),
    })


def student_delete(request, pk):
    """Delete a student (soft delete by setting inactive)"""
    student = get_object_or_404(Student, pk=pk)
    
    if request.method == 'POST':
        student_name = student.get_full_name()
        student.is_active = False
        student.save()
        messages.success(request, f'Student {student_name} has been deactivated.')
        return redirect('digitallibrary:student_list')
    
    context = {
        'student': student,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'fees/student_confirm_delete.html', context)


@tenant_app_view
def payment_record(request):
    """Record a new payment"""
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        if student_id:
            post_data = request.POST.copy()
            post_data['student'] = student_id
            form = FeePaymentForm(post_data, request.FILES)
        else:
            form = FeePaymentForm(request.POST, request.FILES)
            
        if form.is_valid():
            payment = form.save(commit=False)
            payment.recorded_by = request.user
            
            if not payment.receipt_number:
                payment.receipt_number = generate_receipt_number()
            
            payment.save()
            update_fee_balance_after_payment(payment)
            
            messages.success(
                request, 
                f'Payment of KES {payment.amount:,.2f} recorded for {payment.student.get_full_name()}. '
                f'Receipt: {payment.receipt_number}'
            )
            return redirect('digitallibrary:student_detail', pk=payment.student.pk)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = FeePaymentForm()
    
    recent_payments = FeePayment.objects.all().order_by('-payment_date')[:10]
    all_students = Student.objects.filter(is_active=True).select_related('current_class').order_by('first_name', 'last_name')
    
    context = {
        'form': form,
        'recent_payments': recent_payments,
        'all_students': all_students,
        'title': 'Record Payment',
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'fees/payment_record.html', context)


def payment_receipt(request, pk):
    """View and print receipt for a payment"""
    payment = get_object_or_404(FeePayment, pk=pk)
    school = SchoolSetting.objects.first()
    
    if request.user.profile.role not in ['admin', 'principal'] and payment.recorded_by != request.user:
        messages.error(request, "Access Denied.")
        return redirect('digitallibrary:home')
    
    context = {
        'payment': payment,
        'school': school,
        'title': 'Payment Receipt',
    }
    return render(request, 'fees/payment_receipt.html', context)


@tenant_app_view
def defaulter_list(request):
    """List all students with outstanding balances"""
    current_year = request.GET.get('year', '2026')
    current_term = request.GET.get('term', '1')
    
    balances = FeeBalance.objects.filter(
        academic_year=current_year,
        term=current_term,
        balance__gt=0
    ).exclude(status='OVERPAID').select_related('student')
    
    class_filter = request.GET.get('class')
    if class_filter:
        balances = balances.filter(student__current_class_id=class_filter)
    
    balances = balances.order_by('-balance')
    total_due = balances.aggregate(total=models.Sum('balance'))['total'] or 0
    
    context = {
        'balances': balances,
        'total_due': total_due,
        'current_year': current_year,
        'current_term': current_term,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'fees/defaulter_list.html', context)


def export_defaulters_csv(request):
    """Export defaulters list to CSV"""
    current_year = request.GET.get('year', '2026')
    current_term = request.GET.get('term', '1')
    
    balances = FeeBalance.objects.filter(
        academic_year=current_year,
        term=current_term,
        balance__gt=0
    ).exclude(status='OVERPAID').select_related('student')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="defaulters_{current_year}_term{current_term}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Admission No', 'Student Name', 'Class', 'Parent Name', 'Parent Phone', 'Balance'])
    
    for balance in balances:
        writer.writerow([
            balance.student.admission_number,
            balance.student.get_full_name(),
            balance.student.current_class.name if balance.student.current_class else 'N/A',
            balance.student.parent_name,
            balance.student.parent_phone,
            f"KES {balance.balance:,.2f}"
        ])
    
    return response


def collection_report(request):
    """Collection report by date range"""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    payments = FeePayment.objects.all()
    
    if start_date:
        payments = payments.filter(payment_date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__lte=end_date)
    
    payments = payments.order_by('-payment_date')
    total_collected = payments.aggregate(total=models.Sum('amount'))['total'] or 0
    
    by_method = {}
    for method, label in FeePayment.PAYMENT_METHODS:
        total = payments.filter(payment_method=method).aggregate(total=models.Sum('amount'))['total'] or 0
        by_method[label] = total
    
    context = {
        'payments': payments,
        'total_collected': total_collected,
        'by_method': by_method,
        'start_date': start_date,
        'end_date': end_date,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'fees/collection_report.html', context)


# ============================================================
# PERFORMANCE ANALYSIS PORTAL VIEWS
# ============================================================
@tenant_app_view
def performance_dashboard(request):

    """Performance dashboard with actual data"""
    from .models import Exam, Student, Subject, Class, SchoolSetting
    from django.db.models import Avg, Count
    
    # Try to import the correct result model
    Result = None
    try:
        from .models import StudentResult as Result
    except ImportError:
        try:
            from .models import Result
        except ImportError:
            pass  # No result model exists yet
    
    # Get filter parameters
    current_year = request.GET.get('year', '')
    current_term = request.GET.get('term', '')
    selected_class = request.GET.get('class', '')
    selected_subject = request.GET.get('subject', '')
    
    # Base queryset for exams
    exams_qs = Exam.objects.all()
    if current_year:
        exams_qs = exams_qs.filter(academic_year=current_year)
    if current_term:
        exams_qs = exams_qs.filter(term=current_term)
    if selected_class:
        exams_qs = exams_qs.filter(student_class_id=selected_class)
    
    exams = exams_qs
    
    # Get all students
    students_qs = Student.objects.filter(is_active=True)
    if selected_class:
        students_qs = students_qs.filter(current_class_id=selected_class)
    total_students = students_qs.count()
    
    # Initialize empty values
    avg_score = 0
    pass_rate = 0
    grade_distribution = {}
    top_students = []
    subject_performance = []
    total_results = 0
    
    # If Result model exists, get performance data
    if Result:
        # Get results based on filters
        results_qs = Result.objects.all()
        if current_year:
            results_qs = results_qs.filter(exam__academic_year=current_year)
        if current_term:
            results_qs = results_qs.filter(exam__term=current_term)
        if selected_class:
            results_qs = results_qs.filter(student__current_class_id=selected_class)
        if selected_subject:
            results_qs = results_qs.filter(subject_id=selected_subject)
        
        total_results = results_qs.count()
        
        # Calculate average score
        avg_score_data = results_qs.aggregate(avg=Avg('score'))
        avg_score = avg_score_data['avg'] or 0
        
        # Calculate pass rate (score >= 50%)
        passed_results = results_qs.filter(score__gte=50).count()
        pass_rate = (passed_results / total_results * 100) if total_results > 0 else 0
        
        # Grade distribution
        grade_distribution = {
            'A (80-100)': results_qs.filter(score__gte=80).count(),
            'B (70-79)': results_qs.filter(score__gte=70, score__lt=80).count(),
            'C (60-69)': results_qs.filter(score__gte=60, score__lt=70).count(),
            'D (50-59)': results_qs.filter(score__gte=50, score__lt=60).count(),
            'E (0-49)': results_qs.filter(score__lt=50).count(),
        }
        
        # Top performing students
        top_students_data = results_qs.values('student').annotate(
            avg=Avg('score')
        ).order_by('-avg')[:10]
        
        for ts in top_students_data:
            student = Student.objects.filter(id=ts['student']).first()
            if student:
                avg = ts['avg']
                if avg >= 80:
                    grade = 'A'
                elif avg >= 75:
                    grade = 'A-'
                elif avg >= 70:
                    grade = 'B+'
                elif avg >= 65:
                    grade = 'B'
                elif avg >= 60:
                    grade = 'B-'
                elif avg >= 55:
                    grade = 'C+'
                elif avg >= 50:
                    grade = 'C'
                elif avg >= 45:
                    grade = 'C-'
                elif avg >= 40:
                    grade = 'D+'
                else:
                    grade = 'E'
                top_students.append({
                    'student': student,
                    'average': avg,
                    'grade': grade,
                })
        
        # Subject performance
        subjects = Subject.objects.all()
        for subject in subjects:
            subject_results = results_qs.filter(subject=subject)
            if subject_results.exists():
                avg = subject_results.aggregate(avg=Avg('score'))['avg'] or 0
                if avg >= 80:
                    grade = 'A'
                elif avg >= 75:
                    grade = 'A-'
                elif avg >= 70:
                    grade = 'B+'
                elif avg >= 65:
                    grade = 'B'
                elif avg >= 60:
                    grade = 'B-'
                elif avg >= 55:
                    grade = 'C+'
                elif avg >= 50:
                    grade = 'C'
                elif avg >= 45:
                    grade = 'C-'
                elif avg >= 40:
                    grade = 'D+'
                else:
                    grade = 'E'
                subject_performance.append({
                    'name': subject.name,
                    'students': subject_results.values('student').distinct().count(),
                    'average': avg,
                    'grade': grade,
                })
    
    # Available years for filter
    available_years = Exam.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    
    # Classes for filter
    classes = Class.objects.all().order_by('name')
    
    # Subjects for filter
    subjects = Subject.objects.all().order_by('name')
    
    # ============================================================
    # GET SCHOOL SETTINGS FOR LOGO AND NAME
    # ============================================================
    school = SchoolSetting.objects.first()
    
    context = {
        'total_students': total_students,
        'total_exams': exams.count(),
        'avg_score': avg_score,
        'pass_rate': pass_rate,
        'grade_distribution': grade_distribution,
        'top_students': top_students,
        'subject_performance': subject_performance,
        'available_years': available_years,
        'current_year': current_year,
        'current_term': current_term,
        'selected_class': selected_class,
        'selected_subject': selected_subject,
        'classes': classes,
        'subjects': subjects,
        'total_results': total_results,
        # School settings for logo display - ONLY fields that exist
        'school': school,
        'school_name': school.name if school else 'Performance Dashboard',
        'school_logo': school.logo.url if school and school.logo else None,
        'school_motto': school.motto if school else '',
        # REMOVED: address, phone, email, website - fields don't exist
    }
    
    return render(request, 'performance/dashboard.html', context)
def exam_performance_detail(request, exam_id):
    """View detailed performance for a specific exam"""
    from .models import Exam, Subject, Student, StudentResult
    from django.db.models import Avg, Sum
    
    exam = Exam.objects.get(id=exam_id)
    
    # Get students for this exam
    if exam.student_class:
        students = exam.student_class.students.filter(is_active=True)
    else:
        students = Student.objects.filter(is_active=True)
    
    total_students = students.count()
    
    # Get all subjects
    subjects = Subject.objects.all()
    total_subjects = subjects.count()
    
    # Get results for this exam - using StudentResult model
    results = StudentResult.objects.filter(exam=exam)
    
    # Calculate class average
    class_avg_data = results.aggregate(avg=Avg('score'))
    class_average = class_avg_data['avg'] or 0
    
    # Calculate pass rate
    total_results = results.values('student').distinct().count()
    passed_results = results.filter(score__gte=50).values('student').distinct().count()
    pass_rate = (passed_results / total_results * 100) if total_results > 0 else 0
    
    # Get top student
    top_student_data = results.values('student').annotate(total=Sum('score')).order_by('-total').first()
    top_student = None
    if top_student_data:
        top_student = Student.objects.filter(id=top_student_data['student']).first()
    
    # Subject performance
    subjects_performance = []
    for subject in subjects:
        subject_results = results.filter(subject=subject)
        if subject_results.exists():
            avg = subject_results.aggregate(avg=Avg('score'))['avg'] or 0
            highest = subject_results.aggregate(max=Avg('score'))['max'] or 0
            lowest = subject_results.aggregate(min=Avg('score'))['min'] or 0
            passed = subject_results.filter(score__gte=50).count()
            
            # Calculate grade
            if avg >= 80:
                grade = 'A'
            elif avg >= 70:
                grade = 'B'
            elif avg >= 60:
                grade = 'C'
            elif avg >= 50:
                grade = 'D'
            else:
                grade = 'E'
            
            subjects_performance.append({
                'id': subject.id,
                'name': subject.name,
                'average': avg,
                'highest': highest,
                'lowest': lowest,
                'passed': passed,
                'total_students': total_students,
                'grade': grade,
            })
    
    # Student rankings
    rankings = []
    for student in students:
        student_results = results.filter(student=student)
        if student_results.exists():
            subject_scores = []
            for subject in subjects:
                subject_result = student_results.filter(subject=subject).first()
                subject_scores.append(subject_result.score if subject_result else None)
            
            total = sum([r.score for r in student_results if r.score])
            average = total / student_results.count()
            
            # Calculate grade
            if average >= 80:
                grade = 'A'
            elif average >= 75:
                grade = 'A-'
            elif average >= 70:
                grade = 'B+'
            elif average >= 65:
                grade = 'B'
            elif average >= 60:
                grade = 'B-'
            elif average >= 55:
                grade = 'C+'
            elif average >= 50:
                grade = 'C'
            elif average >= 45:
                grade = 'C-'
            elif average >= 40:
                grade = 'D+'
            else:
                grade = 'E'
            
            rankings.append({
                'student': student,
                'subject_scores': subject_scores,
                'total': total,
                'average': average,
                'grade': grade,
            })
    
    # Sort by average
    rankings.sort(key=lambda x: x['average'], reverse=True)
    
    context = {
        'exam': exam,
        'total_students': total_students,
        'total_subjects': total_subjects,
        'class_average': class_average,
        'pass_rate': pass_rate,
        'top_student': top_student,
        'subjects_performance': subjects_performance,
        'subjects_list': subjects,
        'rankings': rankings,
    }
    
    return render(request, 'performance/exam_performance_detail.html', context)

def export_exam_performance(request, exam_id):
    """Export exam performance to CSV"""
    import csv
    from django.http import HttpResponse
    from .models import Exam, Subject, Student, StudentResult
    
    exam = Exam.objects.get(id=exam_id)
    
    if exam.student_class:
        students = exam.student_class.students.filter(is_active=True)
    else:
        students = Student.objects.filter(is_active=True)
    
    subjects = Subject.objects.all()
    results = StudentResult.objects.filter(exam=exam)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{exam.name}_performance.csv"'
    
    writer = csv.writer(response)
    
    header = ['Rank', 'Admission Number', 'Student Name']
    for subject in subjects:
        header.append(subject.name)
    header.extend(['Total Score', 'Average Score', 'Grade', 'Status'])
    writer.writerow(header)
    
    rankings = []
    for student in students:
        student_results = results.filter(student=student)
        if student_results.exists():
            scores = []
            for subject in subjects:
                subject_result = student_results.filter(subject=subject).first()
                scores.append(subject_result.score if subject_result else '')
            
            total = sum([r.score for r in student_results])
            average = total / student_results.count()
            
            grade = 'A' if average >= 80 else 'B' if average >= 70 else 'C' if average >= 60 else 'D' if average >= 50 else 'E'
            status = 'Pass' if average >= 50 else 'Fail'
            
            rankings.append({
                'student': student,
                'scores': scores,
                'total': total,
                'average': average,
                'grade': grade,
                'status': status,
            })
    
    rankings.sort(key=lambda x: x['average'], reverse=True)
    
    for idx, ranking in enumerate(rankings, 1):
        row = [idx, ranking['student'].admission_number, f"{ranking['student'].first_name} {ranking['student'].last_name}"]
        row.extend(ranking['scores'])
        row.extend([ranking['total'], f"{ranking['average']:.1f}", ranking['grade'], ranking['status']])
        writer.writerow(row)
    
    return response

def subject_exam_performance_detail(request, subject_id, exam_id):
    """View performance for a specific subject in a specific exam"""
    from .models import Subject, Exam, Student, StudentResult
    from django.db.models import Avg
    
    subject = Subject.objects.get(id=subject_id)
    exam = Exam.objects.get(id=exam_id)
    
    # Get results for this subject and exam
    results = StudentResult.objects.filter(subject=subject, exam=exam).select_related('student')
    
    # Calculate statistics
    total_students = results.count()
    avg_score = results.aggregate(avg=Avg('score'))['avg'] or 0
    highest = results.aggregate(max=Avg('score'))['max'] or 0
    lowest = results.aggregate(min=Avg('score'))['min'] or 0
    passed = results.filter(score__gte=50).count()
    pass_rate = (passed / total_students * 100) if total_students > 0 else 0
    
    # Grade distribution for this subject
    grade_distribution = {
        'A': results.filter(score__gte=80).count(),
        'B': results.filter(score__gte=70, score__lt=80).count(),
        'C': results.filter(score__gte=60, score__lt=70).count(),
        'D': results.filter(score__gte=50, score__lt=60).count(),
        'E': results.filter(score__lt=50).count(),
    }
    
    context = {
        'subject': subject,
        'exam': exam,
        'results': results.order_by('-score'),
        'total_students': total_students,
        'avg_score': avg_score,
        'highest': highest,
        'lowest': lowest,
        'passed': passed,
        'pass_rate': pass_rate,
        'grade_distribution': grade_distribution,
    }
    
    return render(request, 'performance/subject_exam_performance_detail.html', context)


def exam_performance_detail(request, exam_id):
    """View detailed performance for a specific exam"""
    from .models import Exam, Subject, Student, StudentResult
    from django.db.models import Avg, Sum
    
    exam = Exam.objects.get(id=exam_id)
    
    # Get students for this exam
    if exam.student_class:
        students = exam.student_class.students.filter(is_active=True)
    else:
        students = Student.objects.filter(is_active=True)
    
    total_students = students.count()
    
    # Get all subjects
    subjects = Subject.objects.all()
    total_subjects = subjects.count()
    
    # Get results for this exam
    results = StudentResult.objects.filter(exam=exam)
    
    # Calculate class average
    class_avg_data = results.aggregate(avg=Avg('score'))
    class_average = class_avg_data['avg'] or 0
    
    # Calculate pass rate
    total_results = results.values('student').distinct().count()
    passed_results = results.filter(score__gte=50).values('student').distinct().count()
    pass_rate = (passed_results / total_results * 100) if total_results > 0 else 0
    
    # Get top student
    top_student_data = results.values('student').annotate(total=Sum('score')).order_by('-total').first()
    top_student = None
    if top_student_data:
        top_student = Student.objects.filter(id=top_student_data['student']).first()
    
    # Subject performance
    subjects_performance = []
    for subject in subjects:
        subject_results = results.filter(subject=subject)
        if subject_results.exists():
            avg = subject_results.aggregate(avg=Avg('score'))['avg'] or 0
            highest = subject_results.aggregate(max=Avg('score'))['max'] or 0
            lowest = subject_results.aggregate(min=Avg('score'))['min'] or 0
            passed = subject_results.filter(score__gte=50).count()
            
            if avg >= 80:
                grade = 'A'
            elif avg >= 70:
                grade = 'B'
            elif avg >= 60:
                grade = 'C'
            elif avg >= 50:
                grade = 'D'
            else:
                grade = 'E'
            
            subjects_performance.append({
                'id': subject.id,
                'name': subject.name,
                'average': avg,
                'highest': highest,
                'lowest': lowest,
                'passed': passed,
                'total_students': total_students,
                'grade': grade,
            })
    
    # Student rankings
    rankings = []
    for student in students:
        student_results = results.filter(student=student)
        if student_results.exists():
            subject_scores = []
            for subject in subjects:
                subject_result = student_results.filter(subject=subject).first()
                subject_scores.append(subject_result.score if subject_result else None)
            
            total = sum([r.score for r in student_results if r.score])
            average = total / student_results.count() if student_results.count() > 0 else 0
            
            if average >= 80:
                grade = 'A'
            elif average >= 75:
                grade = 'A-'
            elif average >= 70:
                grade = 'B+'
            elif average >= 65:
                grade = 'B'
            elif average >= 60:
                grade = 'B-'
            elif average >= 55:
                grade = 'C+'
            elif average >= 50:
                grade = 'C'
            elif average >= 45:
                grade = 'C-'
            elif average >= 40:
                grade = 'D+'
            else:
                grade = 'E'
            
            rankings.append({
                'student': student,
                'subject_scores': subject_scores,
                'total': total,
                'average': average,
                'grade': grade,
            })
    
    rankings.sort(key=lambda x: x['average'], reverse=True)
    
    context = {
        'exam': exam,
        'total_students': total_students,
        'total_subjects': total_subjects,
        'class_average': class_average,
        'pass_rate': pass_rate,
        'top_student': top_student,
        'subjects_performance': subjects_performance,
        'subjects_list': subjects,
        'rankings': rankings,
    }
    
    return render(request, 'performance/exam_performance_detail.html', context)


def export_exam_performance(request, exam_id):
    """Export exam performance to CSV"""
    import csv
    from django.http import HttpResponse
    from .models import Exam, Subject, Student, StudentResult
    
    exam = Exam.objects.get(id=exam_id)
    
    if exam.student_class:
        students = exam.student_class.students.filter(is_active=True)
    else:
        students = Student.objects.filter(is_active=True)
    
    subjects = Subject.objects.all()
    results = StudentResult.objects.filter(exam=exam)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{exam.name}_performance.csv"'
    
    writer = csv.writer(response)
    
    header = ['Rank', 'Admission Number', 'Student Name']
    for subject in subjects:
        header.append(subject.name)
    header.extend(['Total Score', 'Average Score', 'Grade', 'Status'])
    writer.writerow(header)
    
    rankings = []
    for student in students:
        student_results = results.filter(student=student)
        if student_results.exists():
            scores = []
            for subject in subjects:
                subject_result = student_results.filter(subject=subject).first()
                scores.append(subject_result.score if subject_result else '')
            
            total = sum([r.score for r in student_results])
            average = total / student_results.count()
            
            grade = 'A' if average >= 80 else 'B' if average >= 70 else 'C' if average >= 60 else 'D' if average >= 50 else 'E'
            status = 'Pass' if average >= 50 else 'Fail'
            
            rankings.append({
                'student': student,
                'scores': scores,
                'total': total,
                'average': average,
                'grade': grade,
                'status': status,
            })
    
    rankings.sort(key=lambda x: x['average'], reverse=True)
    
    for idx, ranking in enumerate(rankings, 1):
        row = [idx, ranking['student'].admission_number, f"{ranking['student'].first_name} {ranking['student'].last_name}"]
        row.extend(ranking['scores'])
        row.extend([ranking['total'], f"{ranking['average']:.1f}", ranking['grade'], ranking['status']])
        writer.writerow(row)
    
    return response

def get_teacher_comment(subject_name, percentage):
    """Generate teacher comment based on performance"""
    if percentage >= 80:
        return f"Excellent performance in {subject_name}. Keep up the great work!"
    elif percentage >= 70:
        return f"Very good in {subject_name}. Continue with the same momentum."
    elif percentage >= 60:
        return f"Good effort in {subject_name}. Can improve further with more practice."
    elif percentage >= 50:
        return f"Satisfactory in {subject_name}. Needs more focus in this subject."
    elif percentage >= 40:
        return f"Below average in {subject_name}. Requires extra attention and revision."
    else:
        return f"Poor performance in {subject_name}. Needs serious improvement. Please consult the teacher."


def get_class_teacher_comment(average):
    """Generate class teacher's overall comment"""
    if average >= 80:
        return "Outstanding performance! You have excelled in this examination. Maintain this high standard. Keep working hard and aiming for excellence. Your dedication is commendable."
    elif average >= 70:
        return "Very good performance! You have done well. With consistent effort, you can achieve even better results. Focus on your weaker areas to improve further."
    elif average >= 60:
        return "Good performance! You have passed comfortably. However, there is room for improvement. Put more effort into your studies to reach higher grades."
    elif average >= 50:
        return "Satisfactory performance. You have managed to pass but need to work harder. Identify your weak subjects and seek help from teachers."
    elif average >= 40:
        return "Below average performance. You need to put in more effort. Please attend extra classes and complete all assignments on time."
    else:
        return "Unsatisfactory performance. Immediate intervention required. Parents are requested to meet with the class teacher to discuss improvement strategies."


def get_principal_comment(average):
    """Generate principal's remarks"""
    if average >= 70:
        return "Approved. Good performance. Keep soaring high. The school is proud of your achievement."
    elif average >= 50:
        return "Approved. Satisfactory results. Aim higher in the next examination."
    else:
        return "Noted. Performance below expectation. Parents are advised to support the student."
def subject_exam_performance_detail(request, subject_id, exam_id):
    """View performance for a specific subject in a specific exam"""
    from .models import Subject, Exam, Student, StudentResult
    from django.db.models import Avg
    
    subject = Subject.objects.get(id=subject_id)
    exam = Exam.objects.get(id=exam_id)
    
    # Get results for this subject and exam - using StudentResult
    results = StudentResult.objects.filter(subject=subject, exam=exam).select_related('student')
    
    # Calculate statistics
    total_students = results.count()
    avg_score = results.aggregate(avg=Avg('score'))['avg'] or 0
    highest = results.aggregate(max=Avg('score'))['max'] or 0
    lowest = results.aggregate(min=Avg('score'))['min'] or 0
    passed = results.filter(score__gte=50).count()
    pass_rate = (passed / total_students * 100) if total_students > 0 else 0
    
    # Grade distribution for this subject
    grade_distribution = {
        'A (80-100)': results.filter(score__gte=80).count(),
        'B (70-79)': results.filter(score__gte=70, score__lt=80).count(),
        'C (60-69)': results.filter(score__gte=60, score__lt=70).count(),
        'D (50-59)': results.filter(score__gte=50, score__lt=60).count(),
        'E (0-49)': results.filter(score__lt=50).count(),
    }
    
    context = {
        'subject': subject,
        'exam': exam,
        'results': results.order_by('-score'),
        'total_students': total_students,
        'avg_score': avg_score,
        'highest': highest,
        'lowest': lowest,
        'passed': passed,
        'pass_rate': pass_rate,
        'grade_distribution': grade_distribution,
    }
    
    return render(request, 'performance/subject_exam_performance_detail.html', context)

def exam_performance_detail(request, exam_id):
    """View detailed performance for a specific exam"""
    from .models import Exam, Subject, Student, StudentResult
    from django.db.models import Avg, Sum
    
    exam = Exam.objects.get(id=exam_id)
    
    # Get students for this exam
    if exam.student_class:
        students = exam.student_class.students.filter(is_active=True)
    else:
        students = Student.objects.filter(is_active=True)
    
    total_students = students.count()
    
    # Get all subjects
    subjects = Subject.objects.all()
    total_subjects = subjects.count()
    
    # Get results for this exam - using StudentResult
    results = StudentResult.objects.filter(exam=exam)
    
    # Calculate class average
    class_avg_data = results.aggregate(avg=Avg('score'))
    class_average = class_avg_data['avg'] or 0
    
    # Calculate pass rate
    total_results = results.values('student').distinct().count()
    passed_results = results.filter(score__gte=50).values('student').distinct().count()
    pass_rate = (passed_results / total_results * 100) if total_results > 0 else 0
    
    # Get top student
    top_student_data = results.values('student').annotate(total=Sum('score')).order_by('-total').first()
    top_student = None
    if top_student_data:
        top_student = Student.objects.filter(id=top_student_data['student']).first()
    
    # Subject performance
    subjects_performance = []
    for subject in subjects:
        subject_results = results.filter(subject=subject)
        if subject_results.exists():
            avg = subject_results.aggregate(avg=Avg('score'))['avg'] or 0
            highest = subject_results.aggregate(max=Avg('score'))['max'] or 0
            lowest = subject_results.aggregate(min=Avg('score'))['min'] or 0
            passed = subject_results.filter(score__gte=50).count()
            
            if avg >= 80:
                grade = 'A'
            elif avg >= 70:
                grade = 'B'
            elif avg >= 60:
                grade = 'C'
            elif avg >= 50:
                grade = 'D'
            else:
                grade = 'E'
            
            subjects_performance.append({
                'id': subject.id,
                'name': subject.name,
                'average': avg,
                'highest': highest,
                'lowest': lowest,
                'passed': passed,
                'total_students': total_students,
                'grade': grade,
            })
    
    # Student rankings
    rankings = []
    for student in students:
        student_results = results.filter(student=student)
        if student_results.exists():
            subject_scores = []
            for subject in subjects:
                subject_result = student_results.filter(subject=subject).first()
                subject_scores.append(subject_result.score if subject_result else None)
            
            total = sum([r.score for r in student_results if r.score])
            average = total / student_results.count() if student_results.count() > 0 else 0
            
            if average >= 80:
                grade = 'A'
            elif average >= 75:
                grade = 'A-'
            elif average >= 70:
                grade = 'B+'
            elif average >= 65:
                grade = 'B'
            elif average >= 60:
                grade = 'B-'
            elif average >= 55:
                grade = 'C+'
            elif average >= 50:
                grade = 'C'
            elif average >= 45:
                grade = 'C-'
            elif average >= 40:
                grade = 'D+'
            else:
                grade = 'E'
            
            rankings.append({
                'student': student,
                'subject_scores': subject_scores,
                'total': total,
                'average': average,
                'grade': grade,
            })
    
    rankings.sort(key=lambda x: x['average'], reverse=True)
    
    context = {
        'exam': exam,
        'total_students': total_students,
        'total_subjects': total_subjects,
        'class_average': class_average,
        'pass_rate': pass_rate,
        'top_student': top_student,
        'subjects_performance': subjects_performance,
        'subjects_list': subjects,
        'rankings': rankings,
    }
    
    return render(request, 'performance/exam_performance_detail.html', context)
# ========== PAPER LIBRARY VIEWS ==========

@login_required
def paper_library(request):
    """Browse papers organized by PaperSet"""
    form = PaperSetFilterForm(request.GET)
    papers = PaperSet.objects.filter(is_active=True).select_related('subject').prefetch_related('resources')
    
    if request.GET.get('grade'):
        papers = papers.filter(grade=request.GET['grade'])
    if request.GET.get('subject'):
        papers = papers.filter(subject_id=request.GET['subject'])
    if request.GET.get('year'):
        papers = papers.filter(year=request.GET['year'])
    if request.GET.get('paper_type'):
        papers = papers.filter(paper_type=request.GET['paper_type'])
    
    q = request.GET.get('q')
    if q:
        papers = papers.filter(
            Q(title__icontains=q) | Q(grade__icontains=q) | Q(subject__name__icontains=q)
        )
    
    paginator = Paginator(papers, 20)
    page = request.GET.get('page', 1)
    papers_page = paginator.get_page(page)
    
    context = {
        'papers': papers_page,
        'filter_form': form,
        'total_papers': papers.count(),
        'total_resources': PaperResource.objects.count(),
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'digitallibrary/paper_library.html', context)


@login_required
def paper_detail(request, pk):
    """View a single paper set with all its resources"""
    paper = get_object_or_404(PaperSet.objects.prefetch_related('resources'), pk=pk)
    paper.view_count += 1
    paper.save(update_fields=['view_count'])
    
    resources_by_kind = {kind: None for kind, _ in PaperResource.KIND_CHOICES}
    for resource in paper.resources.all():
        resources_by_kind[resource.kind] = resource
    
    context = {
        'paper': paper,
        'resources_by_kind': resources_by_kind,
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'digitallibrary/paper_detail.html', context)


@login_required
def download_paper_resource(request, resource_id):
    """Download a paper resource with tracking"""
    resource = get_object_or_404(PaperResource, pk=resource_id)
    paper_set = resource.paper_set
    paper_set.download_count += 1
    paper_set.save(update_fields=['download_count'])
    
    ActivityLog.objects.create(
        user=request.user,
        action='download',
        description=f"Downloaded {resource.get_kind_display()} for {paper_set.title}"
    )
    
    if resource.file:
        response = HttpResponse(resource.file, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(resource.file.name)}"'
        return response
    
    messages.error(request, "File not found")
    return redirect('digitallibrary:paper_detail', pk=paper_set.id)


@login_required
def upload_paper_resource(request):
    """Upload a new paper resource (teacher/admin only)"""
    if not can_upload(request.user):
        messages.error(request, "Access Denied. Only teachers and administrators can upload.")
        return redirect('digitallibrary:paper_library')
    
    if request.method == 'POST':
        form = PaperResourceForm(request.POST, request.FILES)
        if form.is_valid():
            resource = form.save()
            messages.success(request, f"Resource '{resource.title}' uploaded successfully!")
            return redirect('digitallibrary:paper_detail', pk=resource.paper_set.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        paper_set_id = request.GET.get('paper_set')
        initial = {'paper_set': paper_set_id} if paper_set_id else {}
        form = PaperResourceForm(initial=initial)
    
    context = {
        'form': form,
        'title': 'Upload Paper Resource',
        'school': SchoolSetting.objects.first(),
    }
    return render(request, 'digitallibrary/upload_paper_resource.html', context)


@staff_member_required
def create_paper_set(request):
    """Create a new paper set (admin only)"""
    if request.method == 'POST':
        grade = request.POST.get('grade')
        subject_id = request.POST.get('subject')
        year = request.POST.get('year')
        term = request.POST.get('term')
        paper_type = request.POST.get('paper_type')
        exam_type = request.POST.get('exam_type')
        is_featured = request.POST.get('is_featured') == 'on'
        
        if not all([grade, year, paper_type]):
            messages.error(request, "Grade, Year, and Paper Type are required.")
        else:
            paper_set, created = PaperSet.objects.get_or_create(
                grade=grade,
                subject_id=subject_id if subject_id else None,
                year=year,
                term=term if term else None,
                paper_type=paper_type,
                defaults={'exam_type': exam_type, 'is_featured': is_featured, 'is_active': True}
            )
            if created:
                messages.success(request, f"Paper set '{paper_set.title}' created successfully!")
            else:
                messages.info(request, f"Paper set '{paper_set.title}' already exists.")
            return redirect('digitallibrary:paper_detail', pk=paper_set.id)
    
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    years = range(2000, 2027)
    
    context = {
        'subjects': subjects,
        'years': years,
        'paper_types': PaperSet.PAPER_TYPES,
        'exam_types': PaperSet.EXAM_TYPES,
        'school': SchoolSetting.objects.first(),
        'title': 'Create Paper Set',
    }
    return render(request, 'digitallibrary/create_paper_set.html', context)
from django_tenants.utils import get_tenant

def payment_receipt(request, pk):
    """View and print receipt for a payment"""
    payment = get_object_or_404(FeePayment, pk=pk)
    school = SchoolSetting.objects.first()
    
    # Get the fee structure for this payment
    fee_structure = FeeStructure.objects.filter(
        student_class=payment.student.current_class,
        academic_year=payment.academic_year,
        term=payment.term
    ).first()
    
    # Get or create balance
    balance, created = FeeBalance.objects.get_or_create(
        student=payment.student,
        term=payment.term,
        academic_year=payment.academic_year
    )
    
    context = {
        'payment': payment,
        'school': school,
        'fee_structure': fee_structure,
        'balance': balance,
        'title': 'Payment Receipt',
    }
    return render(request, 'fees/fee_receipt.html', context)


@fees_access  # Changed from @staff_member_required to allow admin, principal, and bursar
def print_fee_structure(request, fee_structure_id):
    """Print fee structure details"""
    fee_structure = get_object_or_404(FeeStructure, id=fee_structure_id)
    school = SchoolSetting.objects.first()
    
    # Also need to get fee components for the template
    from .models import FeeComponent
    fee_components = FeeComponent.objects.filter(fee_structure=fee_structure)
    
    context = {
        'fee_structure': fee_structure,
        'fee_components': fee_components,  # Add this for the template
        'school': school,
        'school_name': school.name if school else 'School Name',
        'school_logo': school.logo.url if school and school.logo else None,
        'school_motto': school.motto if school else 'Excellence in Education',
        'title': 'Print Fee Structure',
        'is_print_view': True,
    }
    return render(request, 'fees/fee_structure_print.html', context)

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def send_feedback_notification(feedback):
    """Send email notification for new feedback"""
    try:
        subject = f"[Feedback] {feedback.school_name or 'Unknown School'} - {feedback.subject}"
        
        message = f"""
        New Feedback Received
        
        {'=' * 50}
        SCHOOL INFORMATION
        {'=' * 50}
        School: {feedback.school_name or 'Unknown'}
        Location: {feedback.school_location or 'Not specified'}
        School ID: {feedback.school_id or 'N/A'}
        Email: {feedback.school_email or 'N/A'}
        Phone: {feedback.school_phone or 'N/A'}
        
        {'=' * 50}
        USER INFORMATION
        {'=' * 50}
        Name: {feedback.user_name or 'Anonymous'}
        Role: {feedback.user_role or 'User'}
        Email: {feedback.user_email or 'Not provided'}
        
        {'=' * 50}
        FEEDBACK DETAILS
        {'=' * 50}
        Type: {feedback.get_feedback_type_display()}
        Priority: {feedback.get_priority_display()}
        Rating: {feedback.rating or 'No rating'}/5
        Subject: {feedback.subject}
        
        Message:
        {feedback.message}
        
        {'=' * 50}
        SUBMITTED
        {'=' * 50}
        Time: {feedback.created_at.strftime('%Y-%m-%d %H:%M:%S')}
        IP Address: {feedback.ip_address or 'Unknown'}
        Browser: {feedback.browser_info or 'Unknown'}
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.ADMIN_EMAIL],
            fail_silently=False,
        )
        print(f"✅ Feedback email sent for {feedback.school_name}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


def submit_feedback(request):
    """Submit feedback with full school info"""
    if request.method != "POST":
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body) if request.body else request.POST
        
        # Get school from tenant or request
        school = None
        if hasattr(request, 'tenant'):
            school = request.tenant
            print(f"Tenant found: {school.name if school else 'None'}")
        
        # Create feedback with all available info
        feedback = Feedback.objects.create(
            # User info
            user=request.user if request.user.is_authenticated else None,
            user_role=data.get('user_role') or (request.user.profile.role if hasattr(request.user, 'profile') else None),
            user_email=data.get('user_email') or (request.user.email if request.user.is_authenticated else None),
            user_name=data.get('user_name') or (request.user.get_full_name() if request.user.is_authenticated else None),
            
            # School info (from tenant or form)
            school_id=data.get('school_id') or (school.school_id if school else None),
            school_name=data.get('school_name') or (school.name if school else None),
            school_location=data.get('school_location') or (school.location if school else None),
            school_email=data.get('school_email') or (school.contact_email if school else None),
            school_phone=data.get('school_phone') or (school.contact_phone if school else None),
            school_domain=data.get('school_domain') or (getattr(school, 'domain', None) if school else None),
            school_subdomain=data.get('school_subdomain') or (request.headers.get('X-Subdomain', None)),
            
            # Feedback content
            feedback_type=data.get('feedback_type', 'general'),
            priority=data.get('priority', 'medium'),
            subject=data.get('subject', '')[:200],
            message=data.get('message', ''),
            rating=int(data.get('rating', 0)) if data.get('rating') else None,
            page_url=data.get('page_url', ''),
            
            # Device info
            browser_info=request.headers.get('User-Agent', '')[:500],
            ip_address=get_client_ip(request),
        )
        
        print(f"✅ Feedback saved - School: {feedback.school_name}, ID: {feedback.school_id}")
        
        # Send notification
        send_feedback_notification(feedback)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Feedback submitted successfully',
            'feedback_id': feedback.id
        })
        
    except json.JSONDecodeError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid JSON: {str(e)}'
        }, status=400)
    except Exception as e:
        print(f"❌ Error in submit_feedback: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
def fee_update_page(request):
    """Page to update student fees"""
    students = Student.objects.select_related('class_obj', 'user').all()
    
    for student in students:
        # Calculate total fees for student
        fee_items = FeeStructure.objects.filter(
            class_name=student.class_obj.name if student.class_obj else None
        )
        student.total_fees = sum(fee.amount for fee in fee_items)
        
        # Calculate total paid
        payments = Payment.objects.filter(student=student)
        student.total_paid = payments.aggregate(total=models.Sum('amount'))['total'] or 0
        
        student.balance = student.total_fees - student.total_paid
    
    return render(request, 'digitallibrary/fee_update_form.html', {
        'students': students
    })


def update_student_fees(request):
    """Process fee updates"""
    if request.method == 'POST':
        student_ids = request.POST.getlist('student_ids')
        action = request.POST.get('action')
        
        if action == 'record_payment':
            # Redirect to payment recording page with selected students
            ids = ','.join(student_ids)
            return redirect(f"{reverse('digitallibrary:payment_record')}?students={ids}")
    
    return redirect('digitallibrary:fee_update_page')
from django.http import HttpResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import io
import zipfile
from datetime import datetime
from decimal import Decimal

@login_required
@require_http_methods(['POST'])
def bulk_download_student_packages(request):
    """Generate ZIP file with individual student reports and fee statements"""
    
    # Get filter parameters
    class_id = request.POST.get('class_id', '')
    exam_id = request.POST.get('exam_id', '')
    term = request.POST.get('term', '')
    year = request.POST.get('year', datetime.now().year)
    include_fee_statement = request.POST.get('include_fee_statement', 'on')
    include_report_card = request.POST.get('include_report_card', 'on')
    
    # Get students based on filters
    students_qs = Student.objects.all()
    if class_id:
        students_qs = students_qs.filter(class_obj_id=class_id)
    
    # Get exam for performance data
    exam = None
    if exam_id:
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            pass
    
    # Get school settings
    school = SchoolSetting.objects.first()
    school_name = school.name if school else "School Name"
    school_logo = school.logo.path if school and school.logo else None
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        
        for student in students_qs:
            student_folder = f"{student.adm_no}_{student.user.get_full_name() if student.user else student.name}".replace(' ', '_')
            
            # Generate Report Card PDF
            if include_report_card:
                report_card_pdf = generate_student_report_card(
                    student, exam, term, year, school_name, school_logo
                )
                zip_file.writestr(
                    f"{student_folder}/Report_Card_{student.adm_no}.pdf",
                    report_card_pdf
                )
            
            # Generate Fee Statement PDF
            if include_fee_statement:
                fee_statement_pdf = generate_fee_statement(
                    student, term, year, school_name, school_logo
                )
                zip_file.writestr(
                    f"{student_folder}/Fee_Statement_{student.adm_no}.pdf",
                    fee_statement_pdf
                )
    
    # Prepare response
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_buffer.seek(0)
    
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="student_packages_{timestamp}.zip"'
    
    return response


def generate_student_report_card(student, exam, term, year, school_name, school_logo_path=None):
    """Generate individual student report card PDF"""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#10b981'),
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    # Header with School Name
    if school_logo_path:
        try:
            logo = Image(school_logo_path, width=0.5*inch, height=0.5*inch)
            story.append(logo)
        except:
            pass
    
    story.append(Paragraph(school_name, title_style))
    story.append(Paragraph(f"Student Report Card - {exam.name if exam else 'Academic Performance'}", header_style))
    story.append(Paragraph(f"Term: {term} | Year: {year}", header_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Student Information Table
    student_data = [
        ['Student Name:', f"{student.user.get_full_name() if student.user else student.name}"],
        ['Admission No:', student.adm_no],
        ['Class:', student.class_obj.name if student.class_obj else 'N/A'],
        ['Gender:', student.gender or 'N/A'],
    ]
    
    student_table = Table(student_data, colWidths=[2*inch, 4*inch])
    student_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#10b981')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(student_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Results Table
    results = StudentResult.objects.filter(student=student)
    if exam:
        results = results.filter(exam=exam)
    if term and year:
        results = results.filter(exam__term=term, exam__academic_year=year)
    
    if results.exists():
        # Table headers
        table_data = [['Subject', 'Score', 'Grade', 'Points', 'Remarks']]
        
        total_points = 0
        total_subjects = 0
        
        for result in results.select_related('subject'):
            grade_char = result.grade or calculate_grade(result.score)
            points = calculate_grade_points(result.score)
            total_points += points
            total_subjects += 1
            
            table_data.append([
                result.subject.name,
                f"{result.score:.2f}%",
                grade_char,
                str(points),
                get_grade_remarks(result.score)
            ])
        
        # Calculate averages
        avg_score = results.aggregate(Avg('score'))['score__avg'] or 0
        avg_points = total_points / total_subjects if total_subjects > 0 else 0
        
        # Add summary row
        table_data.append(['', '', '', '', ''])
        table_data.append(['Total', '', '', '', ''])
        table_data.append(['Average', f"{avg_score:.2f}%", calculate_grade(avg_score), f"{avg_points:.1f}", ''])
        
        results_table = Table(table_data, colWidths=[2*inch, 1*inch, 0.8*inch, 0.8*inch, 1.5*inch])
        results_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -4), colors.beige),
            ('BACKGROUND', (0, -3), (-1, -1), colors.HexColor('#e5e7eb')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(results_table)
    else:
        story.append(Paragraph("No results found for this period.", styles['Normal']))
    
    # Teacher Comments Section
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Teacher's Comments:", styles['Heading4']))
    story.append(Paragraph("_" * 80, styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("_" * 80, styles['Normal']))
    
    # Principal Signature
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"_________________________", styles['Normal']))
    story.append(Paragraph(f"Principal / Head of School", styles['Normal']))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_fee_statement(student, term, year, school_name, school_logo_path=None):
    """Generate student fee statement PDF"""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#10b981'),
        alignment=TA_CENTER,
        spaceAfter=12
    )
    
    # Header
    story.append(Paragraph(school_name, title_style))
    story.append(Paragraph("FEE STATEMENT", title_style))
    story.append(Paragraph(f"Term: {term} | Year: {year}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Student Information
    student_info_data = [
        ['Student Name:', f"{student.user.get_full_name() if student.user else student.name}"],
        ['Admission No:', student.adm_no],
        ['Class:', student.class_obj.name if student.class_obj else 'N/A'],
        ['Parent/Guardian:', student.parent_name or 'N/A'],
        ['Phone:', student.parent_phone or 'N/A'],
    ]
    
    info_table = Table(student_info_data, colWidths=[1.5*inch, 4.5*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#10b981')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Fee Structure
    fee_structure_data = [
        ['Fee Item', 'Amount (KES)', 'Paid (KES)', 'Balance (KES)'],
    ]
    
    # Get fee structure for student's class
    fee_structure_items = FeeStructure.objects.filter(
        class_name=student.class_obj.name if student.class_obj else None,
        academic_year=year
    )
    
    total_fees = 0
    total_paid = 0
    
    for fee in fee_structure_items:
        paid_amount = get_total_paid(student, fee, term, year)
        balance = fee.amount - paid_amount
        total_fees += fee.amount
        total_paid += paid_amount
        
        fee_structure_data.append([
            fee.fee_name,
            f"{fee.amount:,.2f}",
            f"{paid_amount:,.2f}",
            f"{balance:,.2f}"
        ])
    
    # Add totals row
    total_balance = total_fees - total_paid
    fee_structure_data.append(['', '', '', ''])
    fee_structure_data.append(['TOTAL', f"{total_fees:,.2f}", f"{total_paid:,.2f}", f"{total_balance:,.2f}"])
    
    fee_table = Table(fee_structure_data, colWidths=[2.5*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    fee_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -3), 9),
        ('BACKGROUND', (0, -2), (-1, -1), colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0, -2), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(fee_table)
    
    # Payment History
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Payment History", styles['Heading4']))
    
    payments = Payment.objects.filter(
        student=student,
        payment_date__year=year
    )
    if term:
        payments = payments.filter(term=term)
    
    if payments.exists():
        payment_data = [['Date', 'Receipt No', 'Fee Item', 'Amount (KES)', 'Method']]
        for payment in payments:
            payment_data.append([
                payment.payment_date.strftime('%d/%m/%Y'),
                payment.receipt_number,
                payment.fee_item or 'General',
                f"{payment.amount:,.2f}",
                payment.payment_method
            ])
        
        payment_table = Table(payment_data, colWidths=[1*inch, 1.2*inch, 2.2*inch, 1*inch, 1*inch])
        payment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(payment_table)
    else:
        story.append(Paragraph("No payment records found.", styles['Normal']))
    
    # Summary
    story.append(Spacer(1, 0.3*inch))
    summary_style = ParagraphStyle(
        'SummaryStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#dc2626') if total_balance > 0 else colors.HexColor('#10b981'),
        alignment=TA_RIGHT
    )
    
    if total_balance > 0:
        story.append(Paragraph(f"Outstanding Balance: KES {total_balance:,.2f}", summary_style))
    else:
        story.append(Paragraph("Fully Paid - No Outstanding Balance", summary_style))
    
    # Footer
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("_________________________", styles['Normal']))
    story.append(Paragraph("Bursar's Signature", styles['Normal']))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("_________________________", styles['Normal']))
    story.append(Paragraph("Student/Parent Signature", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def calculate_grade(score):
    """Calculate grade based on score"""
    if score >= 80:
        return 'A'
    elif score >= 75:
        return 'A-'
    elif score >= 70:
        return 'B+'
    elif score >= 65:
        return 'B'
    elif score >= 60:
        return 'B-'
    elif score >= 55:
        return 'C+'
    elif score >= 50:
        return 'C'
    elif score >= 45:
        return 'C-'
    elif score >= 40:
        return 'D+'
    elif score >= 35:
        return 'D'
    elif score >= 30:
        return 'D-'
    else:
        return 'E'


def calculate_grade_points(score):
    """Calculate grade points (Kenyan system)"""
    if score >= 80:
        return 12
    elif score >= 75:
        return 11
    elif score >= 70:
        return 10
    elif score >= 65:
        return 9
    elif score >= 60:
        return 8
    elif score >= 55:
        return 7
    elif score >= 50:
        return 6
    elif score >= 45:
        return 5
    elif score >= 40:
        return 4
    elif score >= 35:
        return 3
    elif score >= 30:
        return 2
    else:
        return 1


def get_grade_remarks(score):
    """Get remarks based on score"""
    if score >= 80:
        return 'Excellent'
    elif score >= 70:
        return 'Very Good'
    elif score >= 60:
        return 'Good'
    elif score >= 50:
        return 'Average'
    elif score >= 40:
        return 'Below Average'
    else:
        return 'Needs Improvement'


def get_total_paid(student, fee_item, term, year):
    """Calculate total paid for a specific fee item"""
    from .models import Payment
    payments = Payment.objects.filter(
        student=student,
        fee_item=fee_item.fee_name,
        payment_date__year=year,
        term=term
    )
    total = payments.aggregate(total=models.Sum('amount'))['total'] or 0
    return total


def tenant_selector(request):
    """Page to select which school/tenant to work with"""
    from .models import SchoolSetting
    
    tenants = School.objects.all()
    school = SchoolSetting.objects.first()
    
    context = {
        'tenants': tenants,
        'school': school,
        'title': 'Select School',
    }
    return render(request, 'digitallibrary/tenant_selector.html', context)
def tenant_app_view(view_func):
    """Combined decorator for all tenant app views."""
    return tenant_only_view(
        redirect_to="digitallibrary:home",
        message=None
    )(view_func)
