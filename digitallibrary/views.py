# ==============================
# file: digitallibrary/views.py
# ==============================
from __future__ import annotations
from django.db import models
import re
from django.db.models import Sum
from digitallibrary.decorators import role_required
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required, user_passes_test
import logging
from django.contrib.auth import authenticate, login, logout
from tenants.models import School
from .decorators import parent_session_required
from django.db import models
from .models import ParentOTP
from .forms import ParentLoginForm, ParentOTPForm
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
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import Student, FeePayment, FeeBalance, HistoricalArrears, Term, FeeStructure
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Exam, TeacherGradingPreference, GradingSystem, CBEGradingPathway

from django.http import HttpResponse
from django.template.loader import get_template
from django.template import Context
from xhtml2pdf import pisa
import io
from decimal import Decimal

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
from django.contrib.auth.decorators import login_required, user_passes_test
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
    
    FeeComponent,
    Subject,
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
from . import models as app_models

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
def search_students_for_payment(request, tenant_schema=None):
    """AJAX endpoint to search students for payment selection - tenant-safe version"""

    from django.http import JsonResponse
    from django.db import connection
    from django.db.models import Q
    from django_tenants.utils import schema_context
    from .models import Student

    # Detect tenant schema
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    # Fallback from URL path: /tenant/nyaneje/app/...
    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        schema_name = "nyaneje"

    print("\n" + "=" * 60)
    print("🔎 search_students_for_payment called")
    print(f"   Method: {request.method}")
    print(f"   Path: {request.path}")
    print(f"   Tenant schema detected: {schema_name}")
    print(f"   Query: {request.GET.get('q')}")
    print("=" * 60)

    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({"results": []})

    with schema_context(schema_name):
        students = Student.objects.filter(
            is_active=True
        ).filter(
            Q(admission_number__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(parent_phone__icontains=query) |
            Q(upi_number__icontains=query)
        ).select_related("current_class")[:20]

        results = []

        for student in students:
            class_name = student.current_class.name if student.current_class else "No Class"

            results.append({
                "id": student.id,
                "text": f"{student.admission_number} - {student.first_name} {student.last_name} ({class_name})",
                "admission": student.admission_number,
                "name": f"{student.first_name} {student.last_name}",
                "class": class_name if class_name != "No Class" else "N/A",
                "parent_phone": student.parent_phone,
                "fee_detail_url": f"/tenant/{schema_name}/app/student/{student.id}/fee-detail/",
            })

        return JsonResponse({"results": results})


@login_required
def get_students_by_class(request, tenant_schema=None, class_id=None):
    """API to get students for a specific class - tenant-safe version"""

    from django.http import JsonResponse
    from django.db import connection
    from django_tenants.utils import schema_context
    from .models import Student

    # Detect tenant schema
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    # Fallback from URL path: /tenant/nyaneje/app/...
    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        schema_name = "nyaneje"

    print("\n" + "=" * 60)
    print("👥 get_students_by_class called")
    print(f"   Path: {request.path}")
    print(f"   Tenant schema detected: {schema_name}")
    print(f"   Class ID: {class_id}")
    print("=" * 60)

    with schema_context(schema_name):
        students = Student.objects.filter(
            current_class_id=class_id,
            is_active=True
        ).values(
            "id",
            "admission_number",
            "first_name",
            "last_name"
        )

        return JsonResponse({
            "success": True,
            "students": list(students)
        })


@login_required
def get_all_students(request, tenant_schema=None):
    """API to get all active students - tenant-safe version"""

    from django.http import JsonResponse
    from django.db import connection
    from django_tenants.utils import schema_context
    from .models import Student

    # Detect tenant schema
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    # Fallback from URL path: /tenant/nyaneje/app/...
    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        schema_name = "nyaneje"

    print("\n" + "=" * 60)
    print("👥 get_all_students called")
    print(f"   Path: {request.path}")
    print(f"   Tenant schema detected: {schema_name}")
    print("=" * 60)

    with schema_context(schema_name):
        students = Student.objects.filter(
            is_active=True
        ).values(
            "id",
            "admission_number",
            "first_name",
            "last_name"
        )

        return JsonResponse({
            "success": True,
            "students": list(students)
        })

@login_required
def user_management(request, tenant_schema=None):
    """Manage all users in the system - tenant-safe version"""
    from django.contrib.auth.models import User
    from django.core.paginator import Paginator
    from django.db.models import Q
    from django.db import connection
    from django.contrib import messages
    from django.shortcuts import render, redirect
    from .models import UserProfile, SchoolSetting

    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"
    tenant_dashboard_url = f"{tenant_base_url}/dashboard/"
    tenant_users_url = f"{tenant_base_url}/users/"

    if getattr(connection, "schema_name", None) == "public":
        messages.error(request, "User management is only available inside a school tenant.")
        return redirect(tenant_dashboard_url)

    try:
        user_role = request.user.profile.role
    except Exception:
        user_role = None

    if user_role not in ["admin", "principal"]:
        messages.error(request, "Access Denied. Only administrators can manage users.")
        return redirect(tenant_dashboard_url)

    users = User.objects.all().select_related("profile").order_by("-date_joined")

    role_filter = request.GET.get("role", "")
    if role_filter:
        users = users.filter(profile__role=role_filter)

    search = request.GET.get("search", "")
    if search:
        users = users.filter(
            Q(username__icontains=search)
            | Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )

    paginator = Paginator(users, 20)
    page_number = request.GET.get("page", 1)
    users_page = paginator.get_page(page_number)

    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = User.objects.filter(is_active=False).count()

    role_counts = {}
    for role_code, role_name in UserProfile.ROLE_CHOICES:
        role_counts[role_code] = UserProfile.objects.filter(role=role_code).count()

    context = {
        "users": users_page,
        "role_filter": role_filter,
        "search": search,
        "roles": UserProfile.ROLE_CHOICES,
        "school": SchoolSetting.objects.first(),

        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "role_counts": role_counts,

        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "tenant_dashboard_url": tenant_dashboard_url,
        "tenant_users_url": tenant_users_url,
        "tenant_add_user_url": f"{tenant_base_url}/users/add/",
    }

    return render(request, "digitallibrary/user_management.html", context)


@login_required
@role_required(["admin", "principal"])
def assign_class_teachers(request, tenant_schema=None):
    """Assign class teachers - tenant-safe version"""
    from django.contrib.auth.models import User
    from django.db import connection
    from django.contrib import messages
    from django.shortcuts import render, redirect, get_object_or_404
    from .models import Class

    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"
    tenant_assign_class_teachers_url = f"{tenant_base_url}/teacher/assign-class/"

    classes = Class.objects.all().order_by("name")

    teachers = User.objects.filter(
        profile__role__in=["class_teacher", "teacher", "admin", "principal"],
        profile__is_approved=True,
        is_active=True,
    ).order_by("first_name", "last_name")

    if request.method == "POST":
        class_id = request.POST.get("class_id")
        teacher_id = request.POST.get("teacher_id")

        class_obj = get_object_or_404(Class, id=class_id)

        if teacher_id:
            teacher = get_object_or_404(User, id=teacher_id)
            class_obj.class_teacher = teacher
            class_obj.save()

            if teacher.profile.role == "teacher":
                teacher.profile.role = "class_teacher"
                teacher.profile.save()

            messages.success(request, f"{teacher.get_full_name()} assigned as class teacher for {class_obj.name}")
        else:
            old_teacher = class_obj.class_teacher
            class_obj.class_teacher = None
            class_obj.save()

            if old_teacher:
                other_classes = Class.objects.filter(class_teacher=old_teacher).exclude(id=class_obj.id)

                if not other_classes.exists() and old_teacher.profile.role == "class_teacher":
                    old_teacher.profile.role = "teacher"
                    old_teacher.profile.save()

            messages.success(request, f"Class teacher removed for {class_obj.name}")

        return redirect(tenant_assign_class_teachers_url)

    context = {
        "classes": classes,
        "teachers": teachers,
        "title": "Assign Class Teachers",

        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
    }

    return render(request, "digitallibrary/assign_class_teachers.html", context)


@login_required
@role_required(["admin", "principal", "class_teacher"])
def class_teacher_dashboard(request, tenant_schema=None):
    """Dashboard for class teachers - tenant-safe version"""
    from django.db import connection
    from django.contrib import messages
    from django.shortcuts import render, redirect
    from .models import Class, Student

    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"
    tenant_dashboard_url = f"{tenant_base_url}/dashboard/"

    if request.user.profile.role == "class_teacher":
        assigned_class = Class.objects.filter(class_teacher=request.user).first()

        if assigned_class:
            students = Student.objects.filter(current_class=assigned_class, is_active=True)

            context = {
                "assigned_class": assigned_class,
                "students": students,
                "total_students": students.count(),
                "title": f"Class Teacher Dashboard - {assigned_class.name}",

                "tenant_schema": tenant_schema,
                "current_tenant_schema": tenant_schema,
                "tenant_prefix": tenant_schema,
                "tenant_base_url": tenant_base_url,
            }

            return render(request, "digitallibrary/class_teacher_dashboard.html", context)

        messages.warning(request, "You are not assigned to any class yet.")
        return redirect(tenant_dashboard_url)

    classes = Class.objects.all().order_by("name")

    context = {
        "classes": classes,
        "title": "Class Teacher Overview",

        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
    }

    return render(request, "digitallibrary/class_teacher_overview.html", context)


@login_required
def add_user(request, tenant_schema=None):
    """Add a new user to the system - tenant-safe version"""
    from django.contrib.auth.models import User
    from django.db import connection
    from django.contrib import messages
    from django.shortcuts import render, redirect
    from .models import UserProfile, SchoolSetting

    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"
    tenant_dashboard_url = f"{tenant_base_url}/dashboard/"
    tenant_users_url = f"{tenant_base_url}/users/"

    try:
        user_role = request.user.profile.role
    except Exception:
        user_role = None

    if user_role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect(tenant_dashboard_url)

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        role = request.POST.get("role")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        errors = []

        if User.objects.filter(username=username).exists():
            errors.append(f"Username '{username}' already exists.")

        if email and User.objects.filter(email=email).exists():
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
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )

            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.is_approved = True
            profile.save()

            messages.success(request, f"User '{username}' created successfully! Password: {password}")
            return redirect(tenant_users_url)

    context = {
        "roles": UserProfile.ROLE_CHOICES,
        "title": "Add New User",
        "school": SchoolSetting.objects.first(),

        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "tenant_users_url": tenant_users_url,
    }

    return render(request, "digitallibrary/user_form.html", context)


@login_required
def edit_user(request, user_id, tenant_schema=None):
    """Edit user details - tenant-safe version"""
    from django.contrib.auth.models import User
    from django.db import connection
    from django.contrib import messages
    from django.shortcuts import render, redirect, get_object_or_404
    from .models import UserProfile, SchoolSetting

    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"
    tenant_dashboard_url = f"{tenant_base_url}/dashboard/"
    tenant_users_url = f"{tenant_base_url}/users/"

    try:
        current_user_role = request.user.profile.role
    except Exception:
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        if created:
            profile.role = "admin" if request.user.is_superuser else "staff"
            profile.save()
        current_user_role = profile.role

    if current_user_role not in ["admin", "principal"]:
        messages.error(request, "Access Denied. You do not have permission to edit users.")
        return redirect(tenant_dashboard_url)

    edit_user_obj = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        try:
            edit_user_obj.first_name = request.POST.get("first_name", "")
            edit_user_obj.last_name = request.POST.get("last_name", "")
            edit_user_obj.email = request.POST.get("email", "")
            edit_user_obj.is_active = request.POST.get("is_active") == "on"

            new_role = request.POST.get("role")
            if new_role:
                profile, created = UserProfile.objects.get_or_create(user=edit_user_obj)
                profile.role = new_role
                profile.is_approved = True
                profile.save()

            new_password = request.POST.get("new_password")
            if new_password and len(new_password) >= 6:
                edit_user_obj.set_password(new_password)
                messages.success(request, f"Password for '{edit_user_obj.username}' has been reset successfully!")
            elif new_password and len(new_password) < 6:
                messages.warning(request, "Password not changed. Must be at least 6 characters.")

            edit_user_obj.save()
            messages.success(request, f"User '{edit_user_obj.username}' updated successfully!")
            return redirect(tenant_users_url)

        except Exception as e:
            messages.error(request, f"Error updating user: {str(e)}")
            return redirect(tenant_users_url)

    try:
        user_profile = UserProfile.objects.get(user=edit_user_obj)
        current_role = user_profile.role
    except Exception:
        current_role = "user"

    context = {
        "edit_user": edit_user_obj,
        "roles": UserProfile.ROLE_CHOICES,
        "current_role": current_role,
        "title": f"Edit User - {edit_user_obj.username}",
        "school": SchoolSetting.objects.first(),

        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "tenant_users_url": tenant_users_url,
    }

    return render(request, "digitallibrary/user_form.html", context)


@login_required
def reset_user_password(request, user_id, tenant_schema=None):
    """Reset user password - tenant-safe version"""
    import json
    from django.contrib.auth.models import User
    from django.db import connection
    from django.contrib import messages
    from django.shortcuts import render, redirect, get_object_or_404
    from django.http import JsonResponse
    from django.core.mail import send_mail
    from django.conf import settings

    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"
    tenant_users_url = f"{tenant_base_url}/users/"

    try:
        user_role = request.user.profile.role
    except Exception:
        user_role = None

    if user_role not in ["admin", "principal"]:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

        messages.error(request, "Access Denied.")
        return redirect(tenant_users_url)

    if request.method == "POST":
        try:
            if request.headers.get("Content-Type") == "application/json":
                data = json.loads(request.body)
                new_password = data.get("password")
            else:
                new_password = request.POST.get("new_password")

            user = get_object_or_404(User, id=user_id)

            if not new_password or len(new_password) < 6:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": "Password must be at least 6 characters"})

                messages.error(request, "Password must be at least 6 characters.")
                return redirect(tenant_users_url)

            user.set_password(new_password)
            user.save()

            try:
                if user.email:
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
                        recipient_list=[user.email],
                        fail_silently=True,
                    )
            except Exception:
                pass

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": True, "message": f"Password reset to: {new_password}"})

            messages.success(request, f"Password for '{user.username}' has been reset to: {new_password}")
            return redirect(tenant_users_url)

        except Exception as e:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": str(e)})

            messages.error(request, f"Error: {str(e)}")
            return redirect(tenant_users_url)

    context = {
        "user": get_object_or_404(User, id=user_id),
        "title": "Reset Password",

        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "tenant_users_url": tenant_users_url,
    }

    return render(request, "digitallibrary/reset_password.html", context)


@login_required
def get_user_json(request, user_id, tenant_schema=None):
    """Get user data as JSON for modal forms - tenant-safe version"""
    from django.contrib.auth.models import User
    from django.shortcuts import get_object_or_404
    from django.http import JsonResponse

    try:
        user_role = request.user.profile.role
    except Exception:
        user_role = None

    if user_role not in ["admin", "principal"]:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    user = get_object_or_404(User, id=user_id)

    return JsonResponse({
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.profile.role,
        "is_active": user.is_active,
    })


@login_required
def toggle_user_status(request, user_id, tenant_schema=None):
    """Activate/Deactivate user - tenant-safe version"""
    from django.contrib.auth.models import User
    from django.db import connection
    from django.contrib import messages
    from django.shortcuts import redirect, get_object_or_404

    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_users_url = f"/tenant/{tenant_schema}/app/users/"

    try:
        user_role = request.user.profile.role
    except Exception:
        user_role = None

    if user_role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect(tenant_users_url)

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect(tenant_users_url)

    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()

    status = "activated" if user.is_active else "deactivated"
    messages.success(request, f"User '{user.username}' has been {status}.")

    return redirect(tenant_users_url)


@login_required
def delete_user(request, user_id, tenant_schema=None):
    """Delete user - tenant-safe version"""
    from django.contrib.auth.models import User
    from django.db import connection
    from django.contrib import messages
    from django.shortcuts import redirect, get_object_or_404

    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_users_url = f"/tenant/{tenant_schema}/app/users/"

    try:
        user_role = request.user.profile.role
    except Exception:
        user_role = None

    if user_role != "admin":
        messages.error(request, "Access Denied. Only administrators can delete users.")
        return redirect(tenant_users_url)

    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect(tenant_users_url)

    user = get_object_or_404(User, id=user_id)

    if user.id == request.user.id:
        messages.error(request, "You cannot delete your own account.")
        return redirect(tenant_users_url)

    username = user.username
    user.delete()

    messages.success(request, f"User '{username}' has been deleted.")
    return redirect(tenant_users_url)
# ========== PERFORMANCE VIEWS ==========

from django.shortcuts import render
from django.utils import timezone
from django.db import connection
from django_tenants.utils import schema_context

from .decorators import teacher_required
from .models import (
    Exam,
    StudentResult,
    Class,
    SchoolSetting,
)


@teacher_required
def exam_list(
    request,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """
    List exams with class filtering and results counts.

    Accessible to teachers, principals and administrators within the
    active school tenant.
    """

    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(
            getattr(request, "tenant", None),
            "schema_name",
            None,
        )
        or getattr(connection, "schema_name", None)
    )

    # Recover the tenant from a path such as:
    # /tenant/nyaneje/app/exams/
    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")

        if (
            len(path_parts) >= 2
            and path_parts[0] == "tenant"
        ):
            schema_name = path_parts[1]

    # Do not guess or hard-code a school when tenant context is absent.
    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "School tenant context was not detected.",
        )
        return redirect("/app/")

    tenant_base_url = f"/tenant/{schema_name}/app"

    with schema_context(schema_name):
        exams = (
            Exam.objects.all()
            .select_related("student_class")
            .order_by(
                "-academic_year",
                "-term",
                "name",
            )
        )

        year = request.GET.get("year", "").strip()
        term = request.GET.get("term", "").strip()
        class_id = request.GET.get("class", "").strip()

        if year:
            exams = exams.filter(
                academic_year=year,
            )

        if term:
            exams = exams.filter(
                term=term,
            )

        if class_id:
            exams = exams.filter(
                student_class_id=class_id,
            )

        for exam in exams:
            exam.results_count = (
                StudentResult.objects.filter(
                    exam=exam,
                )
                .values("student")
                .distinct()
                .count()
            )

            exam.total_students = (
                exam.get_students_for_exam().count()
            )

        available_years = (
            Exam.objects.values_list(
                "academic_year",
                flat=True,
            )
            .distinct()
            .order_by("-academic_year")
        )

        context = {
            "exams": exams,
            "current_year": (
                year or str(timezone.now().year)
            ),
            "current_term": term,
            "selected_class": class_id,
            "classes": Class.objects.all().order_by(
                "name"
            ),
            "available_years": available_years,
            "school": SchoolSetting.objects.first(),

            # Tenant-safe context
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_dashboard_url": (
                f"{tenant_base_url}/dashboard/"
            ),
            "tenant_exam_list_url": (
                f"{tenant_base_url}/exams/"
            ),
            "tenant_exam_create_url": (
                f"{tenant_base_url}/exams/create/"
            ),
            "title": "Exams",
        }

        return render(
            request,
            "performance/exam_list.html",
            context,
        )
@staff_member_required
def exam_create(request, tenant_schema=None):
    """Create a new exam - tenant-safe version"""
    from django.db import connection
    from django.contrib import messages
    from django.shortcuts import render, redirect

    # Resolve tenant safely
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    tenant_schema = str(tenant_schema).strip()

    if tenant_schema in ["", "public", "None", "none", "null", "undefined"]:
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"

    exam_list_url = f"{tenant_base_url}/exams/"
    exam_create_url = f"{tenant_base_url}/exams/create/"
    performance_url = f"{tenant_base_url}/performance/"
    dashboard_url = f"{tenant_base_url}/dashboard/"

    if request.method == "POST":
        form = ExamForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Exam created successfully!")

            # Tenant-safe redirect
            return redirect(exam_list_url)

        messages.error(request, "Please correct the errors below.")
    else:
        form = ExamForm()

    context = {
        "form": form,
        "title": "Create Exam",

        # Tenant-safe context
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,

        # Tenant-safe URLs
        "tenant_exam_list_url": exam_list_url,
        "tenant_exam_create_url": exam_create_url,
        "tenant_exams_url": exam_list_url,
        "tenant_performance_url": performance_url,
        "tenant_dashboard_url": dashboard_url,
    }

    return render(request, "performance/exam_form.html", context)
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

from decimal import Decimal

from django.contrib import messages
from django.db import connection, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django_tenants.utils import schema_context

from .decorators import teacher_required
from .models import Class, Exam, Student, StudentResult, Subject


@teacher_required
def bulk_results_entry(
    request,
    exam_id,
    subject_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """
    Enter results for all students in a class for a specific subject.

    Accessible to teachers, principals, and administrators inside
    the active school tenant.
    """

    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        messages.error(request, "School tenant context was not detected.")
        return redirect("/app/")

    tenant_base_url = f"/tenant/{schema_name}/app"
    bulk_select_url = f"{tenant_base_url}/bulk-enter-results/"

    with schema_context(schema_name):
        exam = get_object_or_404(Exam, id=exam_id)
        subject = get_object_or_404(Subject, id=subject_id)

        class_id = (
            request.session.get("bulk_class_id")
            or request.GET.get("class_id")
        )

        if not class_id:
            messages.error(request, "Please select a class first.")
            return redirect(bulk_select_url)

        student_class = get_object_or_404(Class, id=class_id)
        request.session["bulk_class_id"] = student_class.id

        students = Student.objects.filter(
            current_class=student_class,
            is_active=True,
        ).order_by("first_name", "last_name")

        session_grading = request.session.get("active_grading_system_id")
        use_cbe = session_grading == "cbe"

        existing_results = {
            result.student_id: result
            for result in StudentResult.objects.filter(
                exam=exam,
                subject=subject,
                student__in=students,
            ).select_related("student")
        }

        if request.method == "POST":
            saved_count = 0
            error_count = 0

            with transaction.atomic():
                for key, value in request.POST.items():
                    if not key.startswith("score_") or not str(value).strip():
                        continue

                    try:
                        student_id = int(key.replace("score_", ""))
                        score = Decimal(str(value))
                    except (TypeError, ValueError):
                        error_count += 1
                        continue

                    max_score = Decimal(str(exam.max_score or 100))

                    if score < 0 or score > max_score:
                        error_count += 1
                        continue

                    try:
                        student = students.get(id=student_id)
                    except Student.DoesNotExist:
                        error_count += 1
                        continue

                    grade_id = None
                    grade_name = None
                    points = 0

                    if use_cbe:
                        with connection.cursor() as cursor:
                            cursor.execute(
                                """
                                SELECT id, grade, points
                                FROM digitallibrary_kneccbegrade
                                WHERE min_score <= %s
                                  AND max_score >= %s
                                LIMIT 1
                                """,
                                [score, score],
                            )
                            grade_result = cursor.fetchone()

                        if not grade_result:
                            error_count += 1
                            continue

                        grade_id, grade_name, points = grade_result

                    else:
                        percentage = (
                            score / max_score * Decimal("100")
                            if max_score > 0
                            else score
                        )

                        if percentage >= 80:
                            grade_name, points = "A", 12
                        elif percentage >= 75:
                            grade_name, points = "A-", 11
                        elif percentage >= 70:
                            grade_name, points = "B+", 10
                        elif percentage >= 65:
                            grade_name, points = "B", 9
                        elif percentage >= 60:
                            grade_name, points = "B-", 8
                        elif percentage >= 55:
                            grade_name, points = "C+", 7
                        elif percentage >= 50:
                            grade_name, points = "C", 6
                        elif percentage >= 45:
                            grade_name, points = "C-", 5
                        elif percentage >= 40:
                            grade_name, points = "D+", 4
                        elif percentage >= 35:
                            grade_name, points = "D", 3
                        elif percentage >= 30:
                            grade_name, points = "D-", 2
                        else:
                            grade_name, points = "E", 1

                        with connection.cursor() as cursor:
                            cursor.execute(
                                """
                                SELECT id
                                FROM digitallibrary_grade
                                WHERE grade = %s
                                LIMIT 1
                                """,
                                [grade_name],
                            )
                            grade_result = cursor.fetchone()

                        grade_id = grade_result[0] if grade_result else None

                    StudentResult.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        defaults={
                            "score": score,
                            "grade_id": grade_id,
                            "grade": grade_name,
                            "points": points,
                            "entered_by": request.user,
                        },
                    )
                    saved_count += 1

            if saved_count:
                messages.success(
                    request,
                    f"Successfully saved {saved_count} result(s) for {subject.name}.",
                )

            if error_count:
                messages.warning(
                    request,
                    f"{error_count} result(s) could not be saved. Check the scores and try again.",
                )

            return redirect(
                f"{tenant_base_url}/bulk-results/{exam.id}/{subject.id}/"
                f"?class_id={student_class.id}"
            )

        existing_scores = {}
        existing_grades = {}
        existing_points = {}

        for student in students:
            result = existing_results.get(student.id)

            if result:
                existing_scores[student.id] = result.score
                existing_grades[student.id] = result.grade
                existing_points[student.id] = result.points
            else:
                existing_scores[student.id] = ""
                existing_grades[student.id] = "—"
                existing_points[student.id] = "—"

        context = {
            "exam": exam,
            "subject": subject,
            "class": student_class,
            "students": students,
            "existing_scores": existing_scores,
            "existing_grades": existing_grades,
            "existing_points": existing_points,
            "student_count": students.count(),
            "use_cbe": use_cbe,
            "max_score": exam.max_score or 100,
            "title": (
                f"Enter Results - {exam.name} - "
                f"{subject.name} - {student_class.name}"
            ),
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
            "tenant_exam_list_url": f"{tenant_base_url}/exams/",
            "tenant_bulk_select_url": bulk_select_url,
        }

        return render(
            request,
            "digitallibrary/bulk_results_entry.html",
            context,
        )

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
from django.contrib import messages
from django.db import connection
from django.shortcuts import get_object_or_404, redirect, render
from django_tenants.utils import schema_context

from .decorators import teacher_required
from .models import (
    PerformanceSummary,
    SchoolSetting,
    Student,
    StudentResult,
)


@teacher_required
def student_performance(
    request,
    student_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """
    Display an individual student's performance.

    Accessible to teachers, principals, and administrators within
    the active school tenant.
    """

    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(
            getattr(request, "tenant", None),
            "schema_name",
            None,
        )
        or getattr(connection, "schema_name", None)
    )

    # Recover tenant schema from:
    # /tenant/nyaneje/app/...
    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")

        if (
            len(path_parts) >= 2
            and path_parts[0] == "tenant"
        ):
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "School tenant context was not detected.",
        )
        return redirect("/app/")

    tenant_base_url = f"/tenant/{schema_name}/app"

    with schema_context(schema_name):
        student = get_object_or_404(
            Student.objects.select_related(
                "current_class",
            ),
            pk=student_id,
        )

        results = (
            StudentResult.objects.filter(
                student=student,
            )
            .select_related(
                "exam",
                "subject",
            )
            .order_by(
                "-exam__academic_year",
                "-exam__term",
                "subject__name",
            )
        )

        summaries = (
            PerformanceSummary.objects.filter(
                student=student,
            )
            .order_by(
                "-academic_year",
                "-term",
            )
        )

        scores = [
            float(score)
            for score in results.values_list(
                "score",
                flat=True,
            )
            if score is not None
        ]

        overall_avg = (
            sum(scores) / len(scores)
            if scores
            else 0
        )

        context = {
            "student": student,
            "results": results,
            "summaries": summaries,
            "overall_avg": overall_avg,
            "school": SchoolSetting.objects.first(),

            # Tenant-safe context
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_dashboard_url": (
                f"{tenant_base_url}/dashboard/"
            ),
            "tenant_exam_list_url": (
                f"{tenant_base_url}/exams/"
            ),
            "tenant_performance_url": (
                f"{tenant_base_url}/performance/"
            ),
            "title": (
                f"Performance - {student.get_full_name()}"
            ),
        }

        return render(
            request,
            "performance/student_performance.html",
            context,
        )

@staff_member_required
def enter_results(request):
    """
    Legacy results-entry endpoint.

    Redirect staff to the tenant-safe class-filtered results-entry form.
    """
    from django.shortcuts import redirect
    from django.contrib import messages

    exam_id = request.GET.get("exam") or request.session.get("exam_id")
    subject_id = request.GET.get("subject") or request.session.get("subject_id")
    class_id = request.GET.get("class_id") or request.session.get("results_class_id")

    if not exam_id:
        messages.info(request, "Please select an exam first.")
        return redirect("digitallibrary:exam_list")

    params = [f"exam={exam_id}"]

    if class_id:
        params.append(f"class_id={class_id}")

    if subject_id:
        params.append(f"subject={subject_id}")

    return redirect(
        "/enter-results-form/?" + "&".join(params)
    )


@tenant_app_view
def enter_results_form(request, tenant_schema=None):
    """
    Tenant-safe results-entry page.

    Selection order:
    1. Exam
    2. Class
    3. Subject

    For whole-school examinations, teachers can select a class and then
    enter results only for students in that class who take the subject.
    """

    from decimal import Decimal

    from django.contrib import messages
    from django.db import connection, models, transaction
    from django.shortcuts import get_object_or_404, redirect, render
    from django_tenants.utils import schema_context

    from .models import (
        Exam,
        Subject,
        Student,
        GradingSystem,
        SchoolSetting,
        Class,
    )

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def model_has_field(model_class, field_name):
        try:
            model_class._meta.get_field(field_name)
            return True
        except Exception:
            return False

    def get_class_students(selected_class, selected_subject=None):
        """
        Return active students in the selected class.

        Where the project has a subject-enrolment relationship, it is
        applied. Otherwise, all active students in the class are returned.
        """
        if selected_class is None:
            return Student.objects.none()

        if model_has_field(Student, "current_class"):
            queryset = Student.objects.filter(
                current_class=selected_class,
                is_active=True,
            )
        elif hasattr(selected_class, "students"):
            queryset = selected_class.students.filter(is_active=True)
        else:
            queryset = Student.objects.none()

        if selected_subject is None:
            return queryset.distinct()

        # Support common subject-enrolment field names without breaking
        # projects that do not use optional-subject enrolment.
        possible_student_subject_fields = (
            "subjects",
            "selected_subjects",
            "enrolled_subjects",
            "subject_choices",
            "optional_subjects",
        )

        for field_name in possible_student_subject_fields:
            if model_has_field(Student, field_name):
                return queryset.filter(
                    **{field_name: selected_subject}
                ).distinct()

        # If Subject has a reverse student relation, use it.
        possible_subject_student_relations = (
            "students",
            "student_set",
            "enrolled_students",
        )

        for relation_name in possible_subject_student_relations:
            if hasattr(selected_subject, relation_name):
                try:
                    eligible_ids = getattr(
                        selected_subject,
                        relation_name,
                    ).values_list("id", flat=True)

                    return queryset.filter(
                        id__in=eligible_ids
                    ).distinct()
                except Exception:
                    pass

        # No explicit subject-enrolment relation exists. In that case,
        # every active student in the selected class is considered eligible.
        return queryset.distinct()

    def get_subjects_for_class(selected_class):
        """
        Return subjects after a class has been selected.

        This version deliberately avoids guessing class-subject relationship
        names. Once a class is selected, every active subject is available in
        the dropdown. Student rows are still restricted to the selected class
        by get_class_students(), and POST validation still rejects students
        outside that class.
        """
        if selected_class is None:
            return Subject.objects.none()

        return Subject.objects.filter(
            is_active=True
        ).order_by("name")

    # ------------------------------------------------------------
    # Detect tenant schema
    # ------------------------------------------------------------
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(
            getattr(request, "tenant", None),
            "schema_name",
            None,
        )
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "Tenant context was not detected. Open this page from the school dashboard.",
        )
        return redirect("/")

    tenant_base_url = f"/tenant/{schema_name}/app"
    form_url = f"{tenant_base_url}/enter-results-form/"

    print("\n" + "=" * 60)
    print("🔵 enter_results_form called")
    print(f"   Method: {request.method}")
    print(f"   Request path: {request.path}")
    print(f"   Tenant schema: {schema_name}")
    print("=" * 60)

    with schema_context(schema_name):
        exams = Exam.objects.all().order_by(
            "-academic_year",
            "-created_at",
        )

        classes = Class.objects.all().order_by("name")

        all_grading_systems = GradingSystem.objects.filter(
            is_active=True,
            is_archived=False,
        ).order_by("-is_default", "name")

        selected_exam_id = request.GET.get("exam")
        selected_class_id = request.GET.get("class_id")
        selected_subject_id = request.GET.get("subject")

        # ========================================================
        # POST: SAVE RESULTS
        # ========================================================
        if request.method == "POST":
            exam_id = request.POST.get("exam_id")
            class_id = request.POST.get("class_id")
            subject_id = request.POST.get("subject_id")

            if not exam_id or not class_id or not subject_id:
                messages.error(
                    request,
                    "Exam, class, and subject are required.",
                )

                params = []

                if exam_id:
                    params.append(f"exam={exam_id}")

                if class_id:
                    params.append(f"class_id={class_id}")

                if subject_id:
                    params.append(f"subject={subject_id}")

                redirect_url = form_url

                if params:
                    redirect_url += "?" + "&".join(params)

                return redirect(redirect_url)

            exam = get_object_or_404(Exam, id=exam_id)
            selected_class = get_object_or_404(Class, id=class_id)
            subject = get_object_or_404(Subject, id=subject_id)

            # Validate that the selected subject belongs to the class.
            allowed_subject_ids = set(
                get_subjects_for_class(selected_class).values_list(
                    "id",
                    flat=True,
                )
            )

            if subject.id not in allowed_subject_ids:
                messages.error(
                    request,
                    "The selected subject is not available for result entry.",
                )

                return redirect(
                    f"{form_url}?exam={exam.id}&class_id={selected_class.id}"
                )

            # If the exam itself is class-specific, prevent selecting
            # a different class.
            if (
                getattr(exam, "student_class_id", None)
                and exam.student_class_id != selected_class.id
            ):
                messages.error(
                    request,
                    "This exam is restricted to a different class.",
                )

                return redirect(
                    f"{form_url}?exam={exam.id}"
                    f"&class_id={exam.student_class_id}"
                )

            eligible_students = get_class_students(
                selected_class,
                subject,
            )

            eligible_student_ids = set(
                eligible_students.values_list("id", flat=True)
            )

            saved_count = 0
            skipped_count = 0
            active_grading_system_id = request.session.get(
                "active_grading_system_id"
            )

            with transaction.atomic():
                for key, value in request.POST.items():
                    if not key.startswith("score_") or value in ("", None):
                        continue

                    try:
                        student_id = int(
                            key.replace("score_", "")
                        )
                    except (TypeError, ValueError):
                        skipped_count += 1
                        continue

                    # Security: reject students outside the selected class
                    # or outside the selected subject enrolment.
                    if student_id not in eligible_student_ids:
                        print(
                            f"   ⚠️ Student {student_id} is not eligible "
                            f"for class {selected_class.id}, "
                            f"subject {subject.id}"
                        )
                        skipped_count += 1
                        continue

                    try:
                        score = Decimal(str(value))
                    except Exception:
                        skipped_count += 1
                        continue

                    if score < 0:
                        skipped_count += 1
                        continue

                    if (
                        exam.max_score is not None
                        and score > Decimal(str(exam.max_score))
                    ):
                        skipped_count += 1
                        continue

                    grade_id = None
                    points = 0
                    grade_remarks = "Result entered"

                    with connection.cursor() as cursor:
                        # ----------------------------------------
                        # CBE grading
                        # ----------------------------------------
                        if (
                            active_grading_system_id == "cbe"
                            or not active_grading_system_id
                        ):
                            maximum_score = Decimal(
                                str(exam.max_score or 100)
                            )

                            percentage_score = (
                                score / maximum_score * Decimal("100")
                                if maximum_score > 0
                                else score
                            )

                            cursor.execute(
                                """
                                SELECT id, points, level, level_name
                                FROM digitallibrary_kneccbegrade
                                WHERE min_score <= %s
                                  AND max_score >= %s
                                  AND is_active = TRUE
                                ORDER BY min_score DESC
                                LIMIT 1
                                """,
                                [
                                    percentage_score,
                                    percentage_score,
                                ],
                            )

                            grade_row = cursor.fetchone()

                            if not grade_row:
                                skipped_count += 1
                                continue

                            (
                                grade_id,
                                points,
                                grade_level,
                                grade_level_name,
                            ) = grade_row

                            grade_remarks = (
                                f"{grade_level} - "
                                f"{grade_level_name}"
                            )

                        # ----------------------------------------
                        # Traditional grading
                        # ----------------------------------------
                        elif active_grading_system_id in (
                            "traditional",
                            "kcse",
                        ):
                            percentage_score = (
                                score
                                / Decimal(str(exam.max_score or 100))
                                * Decimal("100")
                            )

                            grade_id = None

                            if percentage_score >= 80:
                                points = 12
                                grade_remarks = "A - Excellent"
                            elif percentage_score >= 75:
                                points = 11
                                grade_remarks = "A- - Very Good"
                            elif percentage_score >= 70:
                                points = 10
                                grade_remarks = "B+ - Good"
                            elif percentage_score >= 65:
                                points = 9
                                grade_remarks = "B - Good"
                            elif percentage_score >= 60:
                                points = 8
                                grade_remarks = "B- - Above Average"
                            elif percentage_score >= 55:
                                points = 7
                                grade_remarks = "C+ - Average"
                            elif percentage_score >= 50:
                                points = 6
                                grade_remarks = "C - Average"
                            elif percentage_score >= 45:
                                points = 5
                                grade_remarks = "C- - Below Average"
                            elif percentage_score >= 40:
                                points = 4
                                grade_remarks = "D+ - Weak"
                            elif percentage_score >= 35:
                                points = 3
                                grade_remarks = "D - Weak"
                            elif percentage_score >= 30:
                                points = 2
                                grade_remarks = "D- - Very Weak"
                            else:
                                points = 1
                                grade_remarks = "E - Fail"

                        # ----------------------------------------
                        # Custom grading
                        # ----------------------------------------
                        else:
                            percentage_score = (
                                score
                                / Decimal(str(exam.max_score or 100))
                                * Decimal("100")
                            )

                            cursor.execute(
                                """
                                SELECT id, grade, points, remark
                                FROM digitallibrary_gradescale
                                WHERE grading_system_id = %s
                                  AND min_score <= %s
                                  AND max_score >= %s
                                ORDER BY min_score DESC
                                LIMIT 1
                                """,
                                [
                                    active_grading_system_id,
                                    percentage_score,
                                    percentage_score,
                                ],
                            )

                            grade_row = cursor.fetchone()

                            if not grade_row:
                                skipped_count += 1
                                continue

                            (
                                grade_scale_id,
                                grade_name,
                                points,
                                remark,
                            ) = grade_row

                            grade_id = None
                            grade_remarks = (
                                f"{grade_name} - {remark}"
                                if remark
                                else str(grade_name)
                            )

                        cursor.execute(
                            """
                            INSERT INTO digitallibrary_studentresult
                            (
                                student_id,
                                exam_id,
                                subject_id,
                                score,
                                grade_id,
                                points,
                                remarks,
                                entered_by_id,
                                entered_at,
                                updated_at
                            )
                            VALUES (
                                %s, %s, %s, %s, %s,
                                %s, %s, %s, NOW(), NOW()
                            )
                            ON CONFLICT (
                                student_id,
                                exam_id,
                                subject_id
                            )
                            DO UPDATE SET
                                score = EXCLUDED.score,
                                grade_id = EXCLUDED.grade_id,
                                points = EXCLUDED.points,
                                remarks = EXCLUDED.remarks,
                                entered_by_id = EXCLUDED.entered_by_id,
                                updated_at = NOW()
                            """,
                            [
                                student_id,
                                exam.id,
                                subject.id,
                                score,
                                grade_id,
                                points,
                                grade_remarks,
                                request.user.id,
                            ],
                        )

                    saved_count += 1

            if saved_count:
                messages.success(
                    request,
                    f"Successfully saved {saved_count} result(s).",
                )
            else:
                messages.warning(
                    request,
                    "No results were saved.",
                )

            if skipped_count:
                messages.warning(
                    request,
                    f"{skipped_count} result(s) were skipped because "
                    "the student or score was not valid.",
                )

            return redirect(
                f"{form_url}?exam={exam.id}"
                f"&class_id={selected_class.id}"
                f"&subject={subject.id}"
            )

        # ========================================================
        # GET: LOAD FORM
        # ========================================================
        selected_exam = None
        selected_class = None
        selected_subject = None
        students = []
        existing_results = {}

        if selected_exam_id:
            try:
                selected_exam = Exam.objects.get(
                    id=selected_exam_id
                )

                request.session["exam_id"] = selected_exam.id

            except Exam.DoesNotExist:
                messages.error(
                    request,
                    "Selected exam was not found.",
                )

        # If an exam is class-specific, lock the selected class to it.
        if selected_exam and selected_exam.student_class_id:
            selected_class = selected_exam.student_class
            selected_class_id = str(selected_class.id)

        elif selected_class_id:
            try:
                selected_class = Class.objects.get(
                    id=selected_class_id
                )

                request.session[
                    "results_class_id"
                ] = selected_class.id

            except Class.DoesNotExist:
                messages.error(
                    request,
                    "Selected class was not found.",
                )

        subjects = get_subjects_for_class(selected_class)

        print(
            f"   Selected class: "
            f"{getattr(selected_class, 'name', None)}"
        )
        print(f"   Subjects available: {subjects.count()}")

        if selected_subject_id and selected_class:
            try:
                selected_subject = subjects.get(
                    id=selected_subject_id
                )

                request.session[
                    "subject_id"
                ] = selected_subject.id

            except Subject.DoesNotExist:
                messages.error(
                    request,
                    "The selected subject is not available for result entry.",
                )

        if (
            selected_exam
            and selected_class
            and selected_subject
        ):
            students_queryset = get_class_students(
                selected_class,
                selected_subject,
            ).order_by(
                "first_name",
                "last_name",
                "admission_number",
            )

            students = list(students_queryset)

            student_ids = [student.id for student in students]

            if student_ids:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            result.student_id,
                            result.score,
                            COALESCE(
                                grade.level || ' - ' ||
                                grade.level_name,
                                result.remarks,
                                ''
                            ),
                            result.points
                        FROM digitallibrary_studentresult result
                        LEFT JOIN digitallibrary_kneccbegrade grade
                            ON result.grade_id = grade.id
                        WHERE result.exam_id = %s
                          AND result.subject_id = %s
                          AND result.student_id = ANY(%s)
                        """,
                        [
                            selected_exam.id,
                            selected_subject.id,
                            student_ids,
                        ],
                    )

                    for row in cursor.fetchall():
                        existing_results[row[0]] = {
                            "score": row[1],
                            "grade": row[2],
                            "points": row[3],
                        }

        # --------------------------------------------------------
        # Grading systems for selected subject
        # --------------------------------------------------------
        if selected_subject:
            school_custom_grading_systems = (
                GradingSystem.objects.filter(
                    is_active=True,
                    is_archived=False,
                )
                .filter(
                    models.Q(subject__isnull=True)
                    | models.Q(subject=selected_subject)
                    | models.Q(
                        applicable_subjects=selected_subject
                    )
                )
                .distinct()
                .order_by("-is_default", "name")
            )
        else:
            school_custom_grading_systems = (
                GradingSystem.objects.filter(
                    is_active=True,
                    is_archived=False,
                ).order_by("-is_default", "name")
            )

        results_dict = {
            student.id: existing_results.get(student.id)
            for student in students
        }

        context = {
            "exams": exams,
            "classes": classes,
            "subjects": subjects,
            "selected_exam": selected_exam,
            "selected_class": selected_class,
            "selected_subject": selected_subject,
            "students": students,
            "existing_results": results_dict,
            "all_grading_systems": all_grading_systems,
            "school_custom_grading_systems": (
                school_custom_grading_systems
            ),
            "active_grading_system": request.session.get(
                "active_grading_system_id"
            ),
            "school": SchoolSetting.objects.first(),
            "tenant_schema": schema_name,
        }

        return render(
            request,
            "performance/enter_results_form.html",
            context,
        )

@staff_member_required
def enter_results_grid(request, tenant_schema=None):
    """
    Redirect to the tenant-safe results form while preserving exam,
    class, subject and grading-system selections.
    """
    from django.contrib import messages
    from django.db import connection
    from django.shortcuts import redirect
    from django_tenants.utils import schema_context

    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(
            getattr(request, "tenant", None),
            "schema_name",
            None,
        )
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "Tenant context was not detected.",
        )
        return redirect("/")

    with schema_context(schema_name):
        exam_id = (
            request.GET.get("exam")
            or request.session.get("exam_id")
        )

        class_id = (
            request.GET.get("class_id")
            or request.session.get("results_class_id")
        )

        subject_id = (
            request.GET.get("subject")
            or request.session.get("subject_id")
        )

        if not exam_id:
            messages.error(
                request,
                "Please select an exam first.",
            )
            return redirect(
                f"/tenant/{schema_name}/app/enter-results/"
            )

        params = [f"exam={exam_id}"]

        if class_id:
            params.append(f"class_id={class_id}")

        if subject_id:
            params.append(f"subject={subject_id}")

        redirect_url = (
            f"/tenant/{schema_name}/app/"
            f"enter-results-form/?{'&'.join(params)}"
        )

        return redirect(redirect_url)
# digitallibrary/views.py - Add these views

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import TVDisplay, TVContent, Announcement
from .forms import TVContentForm

# At the top of your views.py file, ensure these imports
from django.contrib.auth.decorators import user_passes_test, login_required
from django_tenants.utils import get_tenant
from django.utils import timezone
from datetime import timedelta
from .models import TVDisplay, TVContent, Announcement, SchoolSetting


def is_admin_or_principal(user):
    """Check if user is admin or principal"""
    if user.is_authenticated and (user.is_superuser or user.is_staff):
        return True
    if hasattr(user, 'profile'):
        return user.profile.role in ['admin', 'principal']
    return False

@login_required
@user_passes_test(is_admin_or_principal)
def tv_display(request, tenant_schema=None):
    """
    Display the school TV interface - Professional news-style layout.
    """

    from django.shortcuts import render
    from django.utils import timezone
    from datetime import timedelta
    from django.db import models, connection
    from django_tenants.utils import schema_context

    from .models import TVDisplay, TVContent, Announcement, SchoolSetting
    from tenants.models import School

    if not tenant_schema:
        tenant_schema = getattr(request, "tenant_schema", None)

    if not tenant_schema and hasattr(request, "tenant"):
        tenant_schema = getattr(request.tenant, "schema_name", None)

    if not tenant_schema:
        tenant_schema = getattr(connection, "schema_name", None)

    if not tenant_schema or tenant_schema == "public":
        tenant_schema = "nyaneje"

    request.tenant_schema = tenant_schema

    if hasattr(request, "session"):
        request.session["tenant_schema"] = tenant_schema
        request.session.modified = True

    school_name = f"{tenant_schema.title()} School"

    try:
        with schema_context("public"):
            public_school = School.objects.filter(schema_name=tenant_schema).first()
            if public_school:
                school_name = getattr(public_school, "name", school_name)
    except Exception as e:
        print(f"⚠️ Could not read public tenant school name: {e}")

    class DisplaySchool:
        id = None
        schema_name = tenant_schema
        name = school_name

    school = DisplaySchool()

    school_settings = SchoolSetting.objects.first()

    tv = TVDisplay.objects.filter(is_active=True).order_by("id").first()

    if tv is None:
        tv = TVDisplay.objects.create(
            name=f"{school_name} TV",
            is_active=True,
            layout="split",
            theme="dark",
            accent_color="#bb1919",
            background_color="#0a0a0a",
            text_color="#ffffff",
            refresh_interval=30,
            display_duration=10,
            show_clock=True,
            show_weather=True,
            show_news_ticker=True,
            show_events=True,
            show_exam_schedule=True,
            show_noticeboard=True,
            footer_text="ShuleHub TV - Keeping You Informed",
        )
        print(f"🎬 New live TV display created: {tv.name}")

    if not tv.school_logo and school_settings and getattr(school_settings, "logo", None):
        tv.school_logo = school_settings.logo
        tv.save(update_fields=["school_logo"])

    school_motto = getattr(school_settings, "motto", None) or "Excellence in Education"

    if not tv.is_active:
        return render(request, "digitallibrary/tv/offline.html", {
            "school": school,
            "tenant_schema": tenant_schema,
        })

    now = timezone.now()
    future_date = now + timedelta(days=30)

    tv_contents = TVContent.objects.filter(
        tv_display=tv,
        is_active=True,
        start_date__lte=future_date,
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
    ).order_by("-priority", "-created_at")

    breaking_news = tv_contents.filter(
        content_type="emergency",
        priority__gte=4,
    ).first()

    if not breaking_news:
        breaking_news = tv_contents.filter(
            priority__gte=4,
            is_featured=True,
        ).first()

    featured = tv_contents.filter(
        is_featured=True,
        priority__gte=2,
    )

    if breaking_news:
        featured = featured.exclude(id=breaking_news.id)

    featured = featured.first()

    if not featured:
        fallback_qs = tv_contents.filter(content_type="announcement")
        if breaking_news:
            fallback_qs = fallback_qs.exclude(id=breaking_news.id)
        featured = fallback_qs.first()

    noticeboard_contents = []

    if tv.show_noticeboard:
        announcement_field_names = {
            field.name for field in Announcement._meta.get_fields()
        }

        noticeboard_qs = Announcement.objects.all()

        if "target_audience" in announcement_field_names:
            noticeboard_qs = noticeboard_qs.filter(
                target_audience__in=["all", "teachers", "students"]
            )

        if "expires_at" in announcement_field_names:
            noticeboard_qs = noticeboard_qs.filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
            )

        elif "end_date" in announcement_field_names:
            noticeboard_qs = noticeboard_qs.filter(
                models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
            )

        noticeboard_contents = noticeboard_qs.order_by("-created_at")[:10]

    announcements = tv_contents.filter(content_type="announcement")[:12]
    events = tv_contents.filter(content_type="event")[:8]
    exams = tv_contents.filter(content_type="exam")[:6]
    achievements = tv_contents.filter(content_type="achievement")[:6]

    ticker_messages = []

    for content in tv_contents[:15]:
        bulletin_text = getattr(content, "bulletin_text", None)

        if bulletin_text and bulletin_text.strip():
            ticker_messages.append(bulletin_text.strip())
        elif content.message and content.message.strip():
            ticker_messages.append(content.message.strip())
        elif content.title and content.title.strip():
            ticker_messages.append(content.title.strip())

    for ann in noticeboard_contents[:5]:
        if ann.title and ann.title.strip():
            ticker_messages.append(ann.title.strip())

    context = {
        "tv": tv,
        "school": school,
        "tenant_schema": tenant_schema,
        "school_settings": school_settings,
        "school_motto": school_motto,

        "layout": getattr(tv, "layout", "split"),
        "accent_color": getattr(tv, "accent_color", "#bb1919"),
        "background_color": getattr(tv, "background_color", "#0a0a0a"),
        "text_color": getattr(tv, "text_color", "#ffffff"),
        "refresh_interval": getattr(tv, "refresh_interval", 30),
        "display_duration": getattr(tv, "display_duration", 10),

        "show_clock": getattr(tv, "show_clock", True),
        "show_weather": getattr(tv, "show_weather", True),
        "show_news_ticker": getattr(tv, "show_news_ticker", True),
        "show_events": getattr(tv, "show_events", True),
        "show_exam_schedule": getattr(tv, "show_exam_schedule", True),
        "show_noticeboard": getattr(tv, "show_noticeboard", True),

        "footer_text": getattr(
            tv,
            "footer_text",
            "ShuleHub TV - Keeping You Informed",
        ),

        "breaking_news": breaking_news,
        "featured_content": featured,
        "announcements": announcements,
        "events": events,
        "exams": exams,
        "achievements": achievements,
        "noticeboard_contents": noticeboard_contents,
        "ticker_messages": ticker_messages,

        "tv_url": f"https://{request.get_host()}/tenant/{tenant_schema}/app/tv/",
    }

    return render(request, "digitallibrary/tv/display.html", context)
@login_required
@user_passes_test(is_admin_or_principal, login_url="/app/login/")
def tv_settings(request, tenant_schema=None):
    """
    Update TV display settings.
    """
    tenant_schema = resolve_tenant_schema(request, tenant_schema)
    school_name = get_public_school_name(tenant_schema)
    school = make_display_school(tenant_schema, school_name)

    tv = get_or_create_default_tv_display(tenant_schema, school_name)

    if request.method == "POST":
        tv.layout = request.POST.get("layout", tv.layout)
        tv.theme = request.POST.get("theme", tv.theme)
        tv.accent_color = request.POST.get("accent_color", tv.accent_color)
        tv.background_color = request.POST.get(
            "background_color",
            tv.background_color,
        )
        tv.text_color = request.POST.get("text_color", tv.text_color)

        try:
            tv.refresh_interval = int(
                request.POST.get("refresh_interval", tv.refresh_interval)
            )
        except (TypeError, ValueError):
            pass

        try:
            tv.display_duration = int(
                request.POST.get("display_duration", tv.display_duration)
            )
        except (TypeError, ValueError):
            pass

        tv.show_clock = request.POST.get("show_clock") == "on"
        tv.show_weather = request.POST.get("show_weather") == "on"
        tv.show_news_ticker = request.POST.get("show_news_ticker") == "on"
        tv.show_events = request.POST.get("show_events") == "on"
        tv.show_exam_schedule = request.POST.get("show_exam_schedule") == "on"
        tv.show_noticeboard = request.POST.get("show_noticeboard") == "on"
        tv.footer_text = request.POST.get("footer_text", tv.footer_text)
        tv.is_active = request.POST.get("is_active") == "on"
        tv.save()

        messages.success(request, "✅ TV settings updated successfully!")

        return redirect(
            "digitallibrary:tv_dashboard",
            tenant_schema=tenant_schema,
        )

    school_settings = SchoolSetting.objects.first()

    context = {
        "tv": tv,
        "school": school,
        "tenant_schema": tenant_schema,
        "school_settings": school_settings,
        "title": "TV Display Settings",
    }

    return render(request, "digitallibrary/tv/settings.html", context)
# Define the permission check function
def is_admin_or_principal(user):
    """Check if user is Administrator or Principal"""
    if not user.is_authenticated:
        return False
    
    # Check by group
    if user.groups.filter(name__in=['Administrator', 'Principal']).exists():
        return True
    
    # Check by role field if your User model has it
    if hasattr(user, 'profile') and user.profile.role in ['administrator', 'principal']:
        return True
    
    # Check if user is superuser (optional - they can access everything)
    if user.is_superuser:
        return True
    
    return False

# Optional: Add a dashboard view for TV management
# ==============================================================================
# DIGITAL LIBRARY - TV/DIGITAL SIGNAGE SYSTEM SECTION
# ==============================================================================
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django_tenants.utils import get_tenant
from django.db.models import Q

from .models import TVDisplay, TVContent, Announcement, SchoolSetting
from .forms import TVContentForm

def is_admin_or_principal(user):
    """Check if user is admin or principal"""
    if user.is_authenticated and (user.is_superuser or user.is_staff):
        return True
    if hasattr(user, 'profile'):
        return user.profile.role in ['admin', 'principal']
    return False


from .decorators import tenant_and_role_required

def tv_dashboard(request, tenant_schema=None):
    """
    Publicly accessible TV Signage Dashboard view.

    Uses tenant schema to identify the school.
    Does not depend on School ID.
    """

    from django.shortcuts import render
    from django.db.models import Q
    from django.utils import timezone
    from django.db import connection
    from django_tenants.utils import schema_context

    from .models import TVDisplay, TVContent, Announcement, SchoolSetting
    from tenants.models import School

    # ------------------------------------------------------------
    # 1. Resolve tenant schema safely
    # ------------------------------------------------------------
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    tenant_schema = str(tenant_schema).strip()

    if tenant_schema in ["", "public", "None", "none", "null", "undefined"]:
        tenant_schema = "nyaneje"

    request.tenant_schema = tenant_schema

    if hasattr(request, "session"):
        request.session["tenant_schema"] = tenant_schema
        request.session.modified = True

    tenant_base_url = f"/tenant/{tenant_schema}/app"
    tenant_tv_dashboard_url = f"{tenant_base_url}/tv/dashboard/"
    tenant_tv_content_add_url = f"{tenant_base_url}/tv/content/add/"

    # ------------------------------------------------------------
    # 2. Get public school name for display only
    # ------------------------------------------------------------
    school_name = f"{tenant_schema.title()} School"

    try:
        with schema_context("public"):
            public_school = School.objects.filter(schema_name=tenant_schema).first()

            if public_school:
                school_name = getattr(public_school, "name", school_name)

    except Exception as e:
        print(f"⚠️ Could not read public tenant school name: {e}")

    class DisplaySchool:
        id = None
        schema_name = tenant_schema
        name = school_name

    school = DisplaySchool()

    # ------------------------------------------------------------
    # 3. Get school settings from current tenant schema
    # ------------------------------------------------------------
    school_settings = SchoolSetting.objects.first()
    school_motto = school_settings.motto if school_settings else ""

    # ------------------------------------------------------------
    # 4. Get or create TV display in current tenant schema
    # Keep this same selection logic as tv_content_add.
    # ------------------------------------------------------------
    tv = TVDisplay.objects.filter(is_active=True).order_by("id").first()

    if tv is None:
        create_kwargs = {
            "name": f"{school_name} TV",
            "is_active": True,
            "layout": "split",
            "theme": "dark",
            "refresh_interval": 30,
            "display_duration": 10,
            "show_clock": True,
            "show_weather": True,
            "show_news_ticker": True,
            "show_noticeboard": True,
            "show_events": True,
            "footer_text": "ShuleHub TV - Keeping You Informed",
            "accent_color": "#3b82f6",
            "background_color": "#0f172a",
            "text_color": "#ffffff",
        }

        tv_field_names = {field.name for field in TVDisplay._meta.get_fields()}

        if "show_exam_schedule" in tv_field_names:
            create_kwargs["show_exam_schedule"] = True

        tv = TVDisplay.objects.create(**create_kwargs)

        print(f"✅ Created TV display for tenant: {tenant_schema}")

    # ------------------------------------------------------------
    # 5. Gather all saved TV content linked to this TV display
    # ------------------------------------------------------------
    now = timezone.now()

    all_tv_contents = TVContent.objects.filter(
        tv_display=tv
    ).order_by("-created_at")

    active_tv_contents = all_tv_contents.filter(
        Q(is_active=True)
        & (Q(start_date__isnull=True) | Q(start_date__lte=now))
        & (Q(end_date__isnull=True) | Q(end_date__gte=now))
    ).order_by("-priority", "-created_at")

    # This is what the TV screen should rotate/display
    tv_contents = active_tv_contents

    # ------------------------------------------------------------
    # 6. Noticeboard contents
    # ------------------------------------------------------------
    noticeboard_contents = Announcement.objects.filter(
        target_audience__in=["all", "teachers", "students"]
    )

    announcement_field_names = {
        field.name for field in Announcement._meta.get_fields()
    }

    if "expires_at" in announcement_field_names:
        noticeboard_contents = noticeboard_contents.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )

    elif "end_date" in announcement_field_names:
        noticeboard_contents = noticeboard_contents.filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )

    if "is_featured" in announcement_field_names:
        noticeboard_contents = noticeboard_contents.order_by(
            "-is_featured",
            "-created_at",
        )
    else:
        noticeboard_contents = noticeboard_contents.order_by("-created_at")

    # ------------------------------------------------------------
    # 7. Featured content and content groups
    # ------------------------------------------------------------
    breaking_news = tv_contents.filter(priority__gte=5).first()

    featured = tv_contents.filter(
        is_featured=True,
        priority__gte=2,
    ).first()

    if not featured:
        featured = tv_contents.filter(content_type="announcement").first()

    announcements = tv_contents.filter(content_type="announcement")[:12]
    events = tv_contents.filter(content_type="event")[:8]
    exams = tv_contents.filter(content_type="exam")[:6]
    achievements = tv_contents.filter(content_type="achievement")[:6]

    # ------------------------------------------------------------
    # 8. Ticker messages
    # ------------------------------------------------------------
    ticker_messages = list(tv_contents.values_list("title", flat=True)[:15])

    for ann in noticeboard_contents[:5]:
        ticker_messages.append(ann.title)

    # ------------------------------------------------------------
    # 9. Render context
    # ------------------------------------------------------------
    context = {
        "tv": tv,
        "school": school,
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,

        "school_settings": school_settings,
        "school_motto": school_motto,

        # Tenant-safe URLs
        "tenant_tv_dashboard_url": tenant_tv_dashboard_url,
        "tenant_tv_content_add_url": tenant_tv_content_add_url,
        "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",

        # Display settings
        "layout": getattr(tv, "layout", "split"),
        "accent_color": getattr(tv, "accent_color", "#3b82f6"),
        "background_color": getattr(tv, "background_color", "#0f172a"),
        "text_color": getattr(tv, "text_color", "#ffffff"),
        "refresh_interval": getattr(tv, "refresh_interval", 30),
        "display_duration": getattr(tv, "display_duration", 10),

        "show_clock": getattr(tv, "show_clock", True),
        "show_weather": getattr(tv, "show_weather", True),
        "show_news_ticker": getattr(tv, "show_news_ticker", True),
        "show_noticeboard": getattr(tv, "show_noticeboard", True),
        "show_events": getattr(tv, "show_events", True),
        "show_exam_schedule": getattr(tv, "show_exam_schedule", True),
        "show_exams": getattr(tv, "show_exam_schedule", True),
        "show_achievements": True,

        "footer_text": getattr(
            tv,
            "footer_text",
            "ShuleHub TV - Keeping You Informed",
        ),

        # Important content variables
        "contents": all_tv_contents,
        "tv_contents": all_tv_contents,
        "recent_contents": all_tv_contents[:20],
        "active_tv_contents": active_tv_contents,

        # Stats cards
        "total_content": all_tv_contents.count(),
        "total_contents": all_tv_contents.count(),
        "active_content": active_tv_contents.count(),
        "active_contents": active_tv_contents.count(),

        # TV screen sections
        "breaking_news": breaking_news,
        "featured_content": featured,
        "announcements": announcements,
        "events": events,
        "exams": exams,
        "achievements": achievements,
        "noticeboard_contents": noticeboard_contents[:10],
        "ticker_messages": ticker_messages,
    }

    return render(request, "digitallibrary/tv/dashboard.html", context)
@tenant_and_role_required(["admin", "principal"])
def tv_content_add(request, tenant_schema=None, *args, **kwargs):
    """Add content to TV display - tenant-safe version"""

    from django.shortcuts import render, redirect
    from django.contrib import messages
    from django.db import connection

    from .models import TVDisplay
    from .forms import TVContentForm

    # ------------------------------------------------------------
    # 1. Resolve tenant schema safely
    # ------------------------------------------------------------
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    tenant_schema = str(tenant_schema).strip()

    if tenant_schema in ["", "public", "None", "none", "null", "undefined"]:
        tenant_schema = "nyaneje"

    request.tenant_schema = tenant_schema

    if hasattr(request, "session"):
        request.session["tenant_schema"] = tenant_schema
        request.session.modified = True

    tenant_base_url = f"/tenant/{tenant_schema}/app"
    tenant_tv_dashboard_url = f"{tenant_base_url}/tv/dashboard/"
    tenant_tv_content_add_url = f"{tenant_base_url}/tv/content/add/"

    # ------------------------------------------------------------
    # 2. Get or create the active TV display
    # IMPORTANT:
    # TVDisplay no longer has a school ForeignKey.
    # Do NOT use TVDisplay.objects.filter(school=school).
    # ------------------------------------------------------------
    tv = TVDisplay.objects.filter(
        is_active=True
    ).order_by("id").first()

    if tv is None:
        tv = TVDisplay.objects.create(
            name=f"{tenant_schema.title()} School TV",
            is_active=True,
            layout="split",
            theme="dark",
            refresh_interval=30,
            display_duration=10,
            show_clock=True,
            show_weather=True,
            show_news_ticker=True,
            show_noticeboard=True,
            show_events=True,
            show_exam_schedule=True,
            footer_text="ShuleHub TV - Keeping You Informed",
            accent_color="#3b82f6",
            background_color="#0f172a",
            text_color="#ffffff",
        )

        print(f"✅ Created TV display for tenant: {tenant_schema}")

    # ------------------------------------------------------------
    # 3. Handle form submission
    # ------------------------------------------------------------
    if request.method == "POST":
        form = TVContentForm(request.POST, request.FILES)

        if form.is_valid():
            content = form.save(commit=False)
            content.tv_display = tv

            if request.user.is_authenticated:
                content.created_by = request.user

            content.save()

            messages.success(
                request,
                f'✅ "{content.title}" added to TV successfully!'
            )

            # IMPORTANT:
            # Do not use:
            # return redirect("digitallibrary:tv_dashboard", tenant_schema=tenant_schema)
            # because your tv_dashboard URL pattern does not accept tenant_schema in reverse.
            return redirect(tenant_tv_dashboard_url)

        messages.error(request, "Please correct the errors below.")

    else:
        form = TVContentForm()

    # ------------------------------------------------------------
    # 4. Render form
    # ------------------------------------------------------------
    context = {
        "form": form,
        "tv": tv,
        "tv_content": None,

        # Tenant-safe context
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,

        # Tenant-safe URLs for template buttons
        "tenant_tv_dashboard_url": tenant_tv_dashboard_url,
        "tenant_tv_content_add_url": tenant_tv_content_add_url,
        "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
    }

    return render(request, "digitallibrary/tv/content_form.html", context)
@tenant_and_role_required(["admin", "principal"])
def tv_content_delete(request, pk, tenant_schema=None, *args, **kwargs):
    """Safely delete a TV content slide item"""
    from django.contrib import messages
    from .models import TVContent
    
    content = get_object_or_404(TVContent, pk=pk)
    
    if request.method == "POST":
        title = content.title
        content.delete()
        messages.success(request, f'✅ "{title}" was successfully deleted from the TV display.')
        tenant_base_url = f"/tenant/{tenant_schema}/app"
        return redirect(f"{tenant_base_url}/tv/dashboard/")
        
    tenant_base_url = f"/tenant/{tenant_schema}/app"

    context = {
        "content": content,
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "tenant_tv_dashboard_url": f"{tenant_base_url}/tv/dashboard/",
        "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
    }
    return render(request, "digitallibrary/tv/content_confirm_delete.html", context)
@tenant_and_role_required(["admin", "principal"])
def tv_content_edit(request, pk, tenant_schema=None, *args, **kwargs):
    """Edit existing TV content slide"""
    from .models import TVContent
    content = get_object_or_404(TVContent, pk=pk)
    
    if request.method == "POST":
        form = TVContentForm(request.POST, request.FILES, instance=content)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ "{content.title}" updated successfully!')
            tenant_base_url = f"/tenant/{tenant_schema}/app"
            return redirect(f"{tenant_base_url}/tv/dashboard/")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = TVContentForm(instance=content)
        
    tenant_base_url = f"/tenant/{tenant_schema}/app"

    context = {
        "form": form,
        "content": content,
        "is_edit": True,
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "tenant_tv_dashboard_url": f"{tenant_base_url}/tv/dashboard/",
        "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
    }
    return render(request, "digitallibrary/tv/content_form.html", context)


@login_required
@user_passes_test(is_admin_or_principal, login_url='/app/login/')
def tv_upload_logo(request):
    """Upload or update school logo explicitly for the TV view"""
    from django.contrib import messages
    from .models import TVDisplay
    
    school = get_tenant(request)
    tv = TVDisplay.objects.filter(school=school).order_by("id").first()
    
    if request.method == 'POST' and request.FILES.get('logo'):
        tv.school_logo = request.FILES['logo']
        tv.save()
        messages.success(request, '✅ School logo uploaded successfully!')
    else:
        messages.error(request, 'Please select a valid image file.')
        
    return redirect('digitallibrary:tv_dashboard')


@login_required
@user_passes_test(is_admin_or_principal, login_url='/app/login/')
def tv_remove_logo(request):
    """Remove school logo assignment from TV display settings"""
    from django.contrib import messages
    from .models import TVDisplay
    
    school = get_tenant(request)
    tv = TVDisplay.objects.get(school=school)
    
    if request.method == 'POST':
        if tv.school_logo:
            tv.school_logo.delete(save=False)
            tv.school_logo = None
            tv.save()
            messages.success(request, '✅ School logo removed from TV view.')
        else:
            messages.info(request, 'No explicit logo configuration found.')
            
    return redirect('digitallibrary:tv_dashboard')

def api_tv_content(request):
    """API endpoint for TV content (for AJAX refresh)"""
    
    from django_tenants.utils import get_tenant
    from django.http import JsonResponse
    
    school = get_tenant(request)
    tv = TVDisplay.objects.get(school=school)
    
    now = timezone.now()
    contents = TVContent.objects.filter(
        tv_display=tv,
        start_date__lte=now,
        is_active=True
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
    ).order_by('-priority', '-created_at')
    
    data = {
        'contents': [
            {
                'id': c.id,
                'title': c.title,
                'message': c.message,
                'content_type': c.content_type,
                'priority': c.priority,
                'image_url': c.image.url if c.image else None,
            } for c in contents[:20]
        ],
        'refresh_interval': tv.refresh_interval,
    }
    
    return JsonResponse(data)


@staff_member_required
def set_grading_preference(request, exam_id):
    """Set the grading system preference for this exam session"""
    from django.shortcuts import redirect
    from django.contrib import messages
    from .models import GradingSystem, TeacherGradingPreference
    
    print(f"\n{'='*60}")
    print(f"🔧 set_grading_preference called")
    print(f"   exam_id: {exam_id}")
    print(f"   Method: {request.method}")
    print(f"   POST params: {dict(request.POST)}")
    print(f"{'='*60}")
    
    if request.method == 'POST':
        grading_system_id = request.POST.get('grading_system_id')
        subject_id = request.GET.get('subject')
        
        print(f"   grading_system_id: '{grading_system_id}'")
        print(f"   subject_id: '{subject_id}'")
        
        # Get or create teacher preference
        preference, created = TeacherGradingPreference.objects.get_or_create(
            teacher=request.user,
            exam_id=exam_id
        )
        
        if grading_system_id == 'cbe':
            # Use CBE grading
            preference.use_cbe_pathways = True
            preference.use_custom_grading = False
            preference.custom_grading_system = None
            request.session['active_grading_system_id'] = 'cbe'
            messages.success(request, '✓ CBE Grading System Activated (EE1, EE2, ME1, ME2, AE2, AE1, BE2, BE1)')
            print(f"   Set session: active_grading_system_id = 'cbe'")
            
        elif grading_system_id == 'traditional':
            # Use traditional grading
            preference.use_cbe_pathways = False
            preference.use_custom_grading = False
            preference.custom_grading_system = None
            request.session['active_grading_system_id'] = None
            messages.success(request, '✓ Traditional Grading System (KCSE) Activated')
            print(f"   Set session: active_grading_system_id = None")
            
        elif grading_system_id:
            try:
                # Try to get custom grading system by ID
                grading_system = GradingSystem.objects.get(id=int(grading_system_id), is_active=True)
                preference.use_cbe_pathways = False
                preference.use_custom_grading = True
                preference.custom_grading_system = grading_system
                request.session['active_grading_system_id'] = grading_system.id
                messages.success(request, f'✓ {grading_system.name} Grading System Activated')
                print(f"   Set session: active_grading_system_id = {grading_system.id}")
            except (GradingSystem.DoesNotExist, ValueError) as e:
                messages.error(request, f'Selected grading system not found')
                print(f"   ERROR: {e}")
        else:
            messages.error(request, 'Please select a grading system')
            print(f"   ERROR: No grading_system_id provided")
        
        preference.save()
        
        # Redirect back to the results entry form
        if subject_id and subject_id != 'None':
            redirect_url = f'/app/enter-results-form/?exam={exam_id}&subject={subject_id}'
        else:
            redirect_url = f'/app/enter-results-form/?exam={exam_id}'
        
        print(f"   Redirecting to: {redirect_url}")
        print(f"{'='*60}\n")
        return redirect(redirect_url)
    
    # For GET requests, just redirect to the form
    subject_id = request.GET.get('subject')
    if subject_id and subject_id != 'None':
        return redirect(f'/app/enter-results-form/?exam={exam_id}&subject={subject_id}')
    return redirect(f'/app/enter-results-form/?exam={exam_id}')
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

def student_report_card(
    request,
    tenant_schema=None,
    student_id=None,
    exam_id=None,
    *args,
    **kwargs,
):
    """Generate a printable tenant-safe report card for a student."""

    tenant_schema = resolve_tenant_schema(request, tenant_schema)

    if student_id is None:
        raise Http404("Student ID is required.")

    student = get_object_or_404(
        Student,
        pk=student_id,
        is_active=True,
    )

    # Support both /report-card/<student_id>/<exam_id>/ and ?exam=<id>
    selected_exam_id = (
        exam_id
        or request.GET.get("exam")
        or request.GET.get("exam_id")
    )

    if selected_exam_id:
        exam = get_object_or_404(
            Exam,
            pk=selected_exam_id,
        )
    else:
        exam = (
            Exam.objects.filter(
                student_class=student.current_class,
                is_active=True,
            )
            .order_by(
                "-academic_year",
                "-term",
                "-id",
            )
            .first()
        )

    if not exam:
        messages.error(
            request,
            "No exam results are available for this student.",
        )

        try:
            performance_path = reverse(
                "digitallibrary:student_performance",
                kwargs={"student_id": student.id},
            )
        except NoReverseMatch:
            performance_path = f"/app/performance/student/{student.id}/"

        if performance_path.startswith("/app/"):
            performance_path = (
                f"/tenant/{tenant_schema}{performance_path}"
            )

        return redirect(performance_path)

    results = (
        StudentResult.objects.filter(
            student=student,
            exam=exam,
        )
        .select_related("subject")
        .order_by("subject__name")
    )

    if not results.exists():
        messages.warning(
            request,
            "No subject results were found for this exam.",
        )

        try:
            performance_path = reverse(
                "digitallibrary:student_performance",
                kwargs={"student_id": student.id},
            )
        except NoReverseMatch:
            performance_path = f"/app/performance/student/{student.id}/"

        if performance_path.startswith("/app/"):
            performance_path = (
                f"/tenant/{tenant_schema}{performance_path}"
            )

        return redirect(performance_path)

    valid_scores = [
        float(result.score)
        for result in results
        if result.score is not None
    ]

    total_marks = sum(valid_scores)
    overall_average = (
        total_marks / len(valid_scores)
        if valid_scores
        else 0
    )

    if overall_average >= 80:
        overall_grade = "A"
        overall_status = "Excellent"
    elif overall_average >= 70:
        overall_grade = "B"
        overall_status = "Very Good"
    elif overall_average >= 60:
        overall_grade = "C"
        overall_status = "Good"
    elif overall_average >= 50:
        overall_grade = "D"
        overall_status = "Pass"
    else:
        overall_grade = "E"
        overall_status = "Needs Improvement"

    tenant = get_tenant(request)

    context = {
        "tenant_schema": tenant_schema,
        "student": student,
        "exam": exam,
        "results": results,
        "total_marks": total_marks,
        "overall_average": overall_average,
        "overall_grade": overall_grade,
        "overall_status": overall_status,
        "tenant": tenant,
        "current_date": timezone.now(),
    }

    return render(
        request,
        "performance/student_report_card.html",
        context,
    )
# ========== BULK RESULTS ENTRY VIEWS ==========



@staff_member_required
def bulk_excel_process(request):
    """Process the uploaded Excel file and save results"""
    from .models import Exam, Subject, Student, StudentResult
    from django.db import connection
    import pandas as pd
    import os
    import tempfile
    
    exam_id = request.session.get('bulk_exam_id')
    subject_id = request.session.get('bulk_subject_id')
    grading_system = request.session.get('bulk_grading_system', 'cbe')
    file_path = request.session.get('bulk_file_path')
    
    if not all([exam_id, subject_id, file_path]):
        messages.error(request, 'Missing required data. Please start over.')
        return redirect('digitallibrary:bulk_enter_results')
    
    try:
        exam = Exam.objects.get(id=exam_id)
        subject = Subject.objects.get(id=subject_id)
        use_cbe = grading_system == 'cbe'
        
        # Read file
        try:
            df = pd.read_excel(file_path)
        except:
            df = pd.read_csv(file_path)
        
        # Clean up temp file
        try:
            os.remove(file_path)
        except:
            pass
        
        # Clear session data
        del request.session['bulk_exam_id']
        del request.session['bulk_subject_id']
        del request.session['bulk_grading_system']
        del request.session['bulk_file_path']
        
        # Normalize columns
        df.columns = df.columns.str.strip().str.lower()
        
        # Find admission column
        admission_col = None
        score_col = None
        
        for col in df.columns:
            if 'admission' in col or 'adm' in col or 'reg' in col:
                admission_col = col
            elif 'score' in col or 'mark' in col or 'result' in col:
                score_col = col
        
        if admission_col is None or score_col is None:
            messages.error(request, 'Excel file must have "Admission Number" and "Score" columns')
            return redirect('digitallibrary:bulk_enter_results')
        
        results_processed = 0
        errors = []
        max_score = float(exam.max_score) if exam.max_score else 100.0
        
        with connection.cursor() as cursor:
            for index, row in df.iterrows():
                admission_number = str(row[admission_col]).strip() if pd.notna(row[admission_col]) else None
                score_value = row[score_col] if pd.notna(row[score_col]) else None
                
                if not admission_number or score_value is None:
                    continue
                
                try:
                    score = float(score_value)
                    
                    if score < 0 or score > max_score:
                        errors.append(f"Row {index + 2}: Score {score} is outside valid range (0-{max_score})")
                        continue
                    
                    # Get student
                    student = Student.objects.filter(admission_number=admission_number, is_active=True).first()
                    if not student:
                        errors.append(f"Row {index + 2}: Student with admission number '{admission_number}' not found")
                        continue
                    
                    if use_cbe:
                        # Get CBE grade
                        cursor.execute("""
                            SELECT id, points FROM digitallibrary_kneccbegrade 
                            WHERE min_score <= %s AND max_score >= %s
                            LIMIT 1
                        """, [score, score])
                        grade = cursor.fetchone()
                        if grade:
                            grade_id, points = grade
                            cursor.execute("""
                                INSERT INTO digitallibrary_studentresult 
                                (student_id, exam_id, subject_id, score, grade_id, points, entered_by_id, entered_at, updated_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                                ON CONFLICT (student_id, exam_id, subject_id) 
                                DO UPDATE SET 
                                    score = EXCLUDED.score,
                                    grade_id = EXCLUDED.grade_id,
                                    points = EXCLUDED.points,
                                    updated_at = NOW()
                            """, [student.id, exam.id, subject.id, score, grade_id, points, request.user.id])
                            results_processed += 1
                    else:
                        # Traditional grading
                        percentage = (score / max_score) * 100
                        if percentage >= 80: grade_name = 'A'; points = 12
                        elif percentage >= 75: grade_name = 'A-'; points = 11
                        elif percentage >= 70: grade_name = 'B+'; points = 10
                        elif percentage >= 65: grade_name = 'B'; points = 9
                        elif percentage >= 60: grade_name = 'B-'; points = 8
                        elif percentage >= 55: grade_name = 'C+'; points = 7
                        elif percentage >= 50: grade_name = 'C'; points = 6
                        elif percentage >= 45: grade_name = 'C-'; points = 5
                        elif percentage >= 40: grade_name = 'D+'; points = 4
                        elif percentage >= 35: grade_name = 'D'; points = 3
                        elif percentage >= 30: grade_name = 'D-'; points = 2
                        else: grade_name = 'E'; points = 1
                        
                        cursor.execute("""
                            SELECT id FROM digitallibrary_grade WHERE grade = %s LIMIT 1
                        """, [grade_name])
                        grade = cursor.fetchone()
                        grade_id = grade[0] if grade else None
                        
                        cursor.execute("""
                            INSERT INTO digitallibrary_studentresult 
                            (student_id, exam_id, subject_id, score, grade_id, points, entered_by_id, entered_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                            ON CONFLICT (student_id, exam_id, subject_id) 
                            DO UPDATE SET 
                                score = EXCLUDED.score,
                                grade_id = EXCLUDED.grade_id,
                                points = EXCLUDED.points,
                                updated_at = NOW()
                        """, [student.id, exam.id, subject.id, score, grade_id, points, request.user.id])
                        results_processed += 1
                        
                except ValueError:
                    errors.append(f"Row {index + 2}: Invalid score value '{score_value}'")
                except Exception as e:
                    errors.append(f"Row {index + 2}: {str(e)}")
        
        if results_processed > 0:
            messages.success(request, f'✅ Successfully processed {results_processed} results for {exam.name} - {subject.name}')
        else:
            messages.warning(request, '⚠️ No valid results were found in the file.')
        
        if errors:
            for error in errors[:10]:
                messages.warning(request, error)
            if len(errors) > 10:
                messages.info(request, f'... and {len(errors) - 10} more errors')
                
        return redirect('digitallibrary:exam_list')
        
    except Exam.DoesNotExist:
        messages.error(request, 'Selected exam not found')
    except Subject.DoesNotExist:
        messages.error(request, 'Selected subject not found')
    except Exception as e:
        messages.error(request, f'Error processing file: {str(e)}')
    
    return redirect('digitallibrary:bulk_enter_results')


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

@teacher_required
def bulk_excel_upload(
    request,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """
    Upload an Excel file containing student results.

    Accessible to teachers, principals, and administrators
    within the active tenant.
    """
    from django.db import connection
    from django.shortcuts import redirect, render
    from django_tenants.utils import schema_context
    from .forms import ExcelResultsUploadForm

    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(
            getattr(request, "tenant", None),
            "schema_name",
            None,
        )
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")

        if (
            len(path_parts) >= 2
            and path_parts[0] == "tenant"
        ):
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "School tenant context was not detected.",
        )
        return redirect("/app/")

    tenant_base_url = f"/tenant/{schema_name}/app"
    upload_url = (
        f"{tenant_base_url}/exams/bulk-excel-upload/"
    )
    exam_list_url = f"{tenant_base_url}/exams/"

    with schema_context(schema_name):
        if request.method == "POST":
            form = ExcelResultsUploadForm(
                request.POST,
                request.FILES,
            )

            if form.is_valid():
                excel_file = request.FILES["excel_file"]
                exam = form.cleaned_data["exam"]
                subject = form.cleaned_data["subject"]

                try:
                    workbook = openpyxl.load_workbook(
                        excel_file,
                        data_only=True,
                    )
                    sheet = workbook.active

                    admission_col = None
                    score_col = None

                    for index, cell in enumerate(
                        sheet[1],
                        1,
                    ):
                        header = (
                            str(cell.value).lower().strip()
                            if cell.value
                            else ""
                        )

                        if any(
                            term in header
                            for term in (
                                "admission",
                                "adm",
                                "reg",
                            )
                        ):
                            admission_col = index

                        elif any(
                            term in header
                            for term in (
                                "score",
                                "mark",
                                "result",
                            )
                        ):
                            score_col = index

                    if (
                        admission_col is None
                        or score_col is None
                    ):
                        messages.error(
                            request,
                            (
                                'Excel file must contain '
                                '"Admission Number" and '
                                '"Score" columns.'
                            ),
                        )
                        return redirect(upload_url)

                    results_processed = 0
                    errors = []

                    for row_number, row in enumerate(
                        sheet.iter_rows(
                            min_row=2,
                            values_only=True,
                        ),
                        start=2,
                    ):
                        if not row:
                            continue

                        admission_value = (
                            row[admission_col - 1]
                            if admission_col - 1 < len(row)
                            else None
                        )
                        score_value = (
                            row[score_col - 1]
                            if score_col - 1 < len(row)
                            else None
                        )

                        admission_number = (
                            str(admission_value).strip()
                            if admission_value is not None
                            else None
                        )

                        if (
                            not admission_number
                            or score_value is None
                        ):
                            continue

                        try:
                            score = float(score_value)
                            max_score = float(
                                exam.max_score or 100
                            )

                            if (
                                score < 0
                                or score > max_score
                            ):
                                errors.append(
                                    (
                                        f"Row {row_number}: "
                                        f"Score {score} is outside "
                                        f"the range 0–{max_score}."
                                    )
                                )
                                continue

                            student = Student.objects.get(
                                admission_number=admission_number,
                                is_active=True,
                            )

                            StudentResult.objects.update_or_create(
                                student=student,
                                exam=exam,
                                subject=subject,
                                defaults={
                                    "score": score,
                                    "entered_by": request.user,
                                },
                            )

                            results_processed += 1

                        except Student.DoesNotExist:
                            errors.append(
                                (
                                    f"Row {row_number}: Student "
                                    f"'{admission_number}' "
                                    "was not found."
                                )
                            )

                        except (TypeError, ValueError):
                            errors.append(
                                (
                                    f"Row {row_number}: Invalid "
                                    f"score '{score_value}'."
                                )
                            )

                        except Exception as error:
                            errors.append(
                                f"Row {row_number}: {error}"
                            )

                    if results_processed:
                        messages.success(
                            request,
                            (
                                f"Successfully processed "
                                f"{results_processed} result(s) "
                                f"for {exam.name} – "
                                f"{subject.name}."
                            ),
                        )

                        return redirect(exam_list_url)

                    for error in errors[:5]:
                        messages.warning(
                            request,
                            error,
                        )

                    if len(errors) > 5:
                        messages.warning(
                            request,
                            (
                                f"...and "
                                f"{len(errors) - 5} more errors."
                            ),
                        )

                    messages.warning(
                        request,
                        "No valid results were found.",
                    )

                except Exception as error:
                    messages.error(
                        request,
                        f"Error processing file: {error}",
                    )
                    return redirect(upload_url)

            else:
                for field, field_errors in form.errors.items():
                    for error in field_errors:
                        messages.error(
                            request,
                            f"{field}: {error}",
                        )

        else:
            form = ExcelResultsUploadForm()

        context = {
            "form": form,
            "title": "Bulk Excel Upload",
            "school": SchoolSetting.objects.first(),
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_exam_list_url": exam_list_url,
            "tenant_upload_url": upload_url,
        }

        return render(
            request,
            "performance/bulk_excel_upload.html",
            context,
        )
# ========== BULK RESULTS ENTRY VIEWS ==========

@teacher_required
def bulk_enter_results(
    request,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """
    Select an exam, subject, grading system, and upload
    an Excel or CSV file containing results.
    """
    import pandas as pd

    from django.db import connection, transaction
    from django.shortcuts import redirect, render
    from django_tenants.utils import schema_context

    from .models import Exam, Subject, SchoolSetting

    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(
            getattr(request, "tenant", None),
            "schema_name",
            None,
        )
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")

        if (
            len(path_parts) >= 2
            and path_parts[0] == "tenant"
        ):
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "School tenant context was not detected.",
        )
        return redirect("/app/")

    tenant_base_url = f"/tenant/{schema_name}/app"
    bulk_enter_url = (
        f"{tenant_base_url}/bulk-enter-results/"
    )
    exam_list_url = f"{tenant_base_url}/exams/"

    with schema_context(schema_name):
        exams = Exam.objects.filter(
            is_active=True,
        ).order_by(
            "-academic_year",
            "-created_at",
        )

        subjects = Subject.objects.filter(
            is_active=True,
        ).order_by("name")

        if request.method == "POST":
            exam_id = request.POST.get("exam")
            subject_id = request.POST.get("subject")
            grading_system = request.POST.get(
                "grading_system",
                "cbe",
            )
            excel_file = request.FILES.get("excel_file")

            if (
                not exam_id
                or not subject_id
                or not excel_file
            ):
                messages.error(
                    request,
                    (
                        "Select an exam and subject, "
                        "then upload a file."
                    ),
                )
                return redirect(bulk_enter_url)

            try:
                exam = Exam.objects.get(id=exam_id)
                subject = Subject.objects.get(
                    id=subject_id
                )
                use_cbe = grading_system == "cbe"

                extension = (
                    excel_file.name.rsplit(".", 1)[-1]
                    .lower()
                )

                try:
                    if extension == "csv":
                        dataframe = pd.read_csv(excel_file)
                    else:
                        dataframe = pd.read_excel(
                            excel_file
                        )

                except Exception as error:
                    messages.error(
                        request,
                        f"Error reading file: {error}",
                    )
                    return redirect(bulk_enter_url)

                dataframe.columns = (
                    dataframe.columns.astype(str)
                    .str.strip()
                    .str.lower()
                )

                admission_col = None
                score_col = None

                for column in dataframe.columns:
                    if any(
                        term in column
                        for term in (
                            "admission",
                            "adm",
                            "reg",
                            "student",
                        )
                    ):
                        admission_col = column

                    elif any(
                        term in column
                        for term in (
                            "score",
                            "mark",
                            "result",
                        )
                    ):
                        score_col = column

                if (
                    admission_col is None
                    or score_col is None
                ):
                    messages.error(
                        request,
                        (
                            'The file must contain '
                            '"Admission Number" and '
                            '"Score" columns.'
                        ),
                    )
                    return redirect(bulk_enter_url)

                results_processed = 0
                errors = []
                max_score = float(
                    exam.max_score or 100
                )

                with transaction.atomic():
                    with connection.cursor() as cursor:
                        for index, row in dataframe.iterrows():
                            admission_number = (
                                str(row[admission_col]).strip()
                                if pd.notna(
                                    row[admission_col]
                                )
                                else None
                            )

                            score_value = (
                                row[score_col]
                                if pd.notna(row[score_col])
                                else None
                            )

                            if (
                                not admission_number
                                or score_value is None
                            ):
                                continue

                            try:
                                score = float(score_value)

                                if (
                                    score < 0
                                    or score > max_score
                                ):
                                    errors.append(
                                        (
                                            f"Row {index + 2}: "
                                            f"Score {score} is outside "
                                            f"the range 0–{max_score}."
                                        )
                                    )
                                    continue

                                student = Student.objects.filter(
                                    admission_number=admission_number,
                                    is_active=True,
                                ).first()

                                if not student:
                                    errors.append(
                                        (
                                            f"Row {index + 2}: "
                                            f"Student "
                                            f"'{admission_number}' "
                                            "was not found."
                                        )
                                    )
                                    continue

                                grade_id = None
                                points = 0

                                if use_cbe:
                                    cursor.execute(
                                        """
                                        SELECT id, points
                                        FROM digitallibrary_kneccbegrade
                                        WHERE min_score <= %s
                                          AND max_score >= %s
                                        LIMIT 1
                                        """,
                                        [score, score],
                                    )
                                    grade = cursor.fetchone()

                                    if not grade:
                                        errors.append(
                                            (
                                                f"Row {index + 2}: "
                                                "No matching CBE grade."
                                            )
                                        )
                                        continue

                                    grade_id, points = grade

                                else:
                                    percentage = (
                                        score / max_score * 100
                                        if max_score > 0
                                        else score
                                    )

                                    if percentage >= 80:
                                        grade_name, points = "A", 12
                                    elif percentage >= 75:
                                        grade_name, points = "A-", 11
                                    elif percentage >= 70:
                                        grade_name, points = "B+", 10
                                    elif percentage >= 65:
                                        grade_name, points = "B", 9
                                    elif percentage >= 60:
                                        grade_name, points = "B-", 8
                                    elif percentage >= 55:
                                        grade_name, points = "C+", 7
                                    elif percentage >= 50:
                                        grade_name, points = "C", 6
                                    elif percentage >= 45:
                                        grade_name, points = "C-", 5
                                    elif percentage >= 40:
                                        grade_name, points = "D+", 4
                                    elif percentage >= 35:
                                        grade_name, points = "D", 3
                                    elif percentage >= 30:
                                        grade_name, points = "D-", 2
                                    else:
                                        grade_name, points = "E", 1

                                    cursor.execute(
                                        """
                                        SELECT id
                                        FROM digitallibrary_grade
                                        WHERE grade = %s
                                        LIMIT 1
                                        """,
                                        [grade_name],
                                    )

                                    grade = cursor.fetchone()
                                    grade_id = (
                                        grade[0]
                                        if grade
                                        else None
                                    )

                                cursor.execute(
                                    """
                                    INSERT INTO digitallibrary_studentresult
                                    (
                                        student_id,
                                        exam_id,
                                        subject_id,
                                        score,
                                        grade_id,
                                        points,
                                        entered_by_id,
                                        entered_at,
                                        updated_at
                                    )
                                    VALUES (
                                        %s, %s, %s, %s,
                                        %s, %s, %s,
                                        NOW(), NOW()
                                    )
                                    ON CONFLICT (
                                        student_id,
                                        exam_id,
                                        subject_id
                                    )
                                    DO UPDATE SET
                                        score = EXCLUDED.score,
                                        grade_id = EXCLUDED.grade_id,
                                        points = EXCLUDED.points,
                                        entered_by_id =
                                            EXCLUDED.entered_by_id,
                                        updated_at = NOW()
                                    """,
                                    [
                                        student.id,
                                        exam.id,
                                        subject.id,
                                        score,
                                        grade_id,
                                        points,
                                        request.user.id,
                                    ],
                                )

                                results_processed += 1

                            except Exception as error:
                                errors.append(
                                    (
                                        f"Row {index + 2}: "
                                        f"{error}"
                                    )
                                )

                if results_processed:
                    messages.success(
                        request,
                        (
                            f"Successfully processed "
                            f"{results_processed} result(s) "
                            f"for {exam.name} – "
                            f"{subject.name}."
                        ),
                    )
                else:
                    messages.warning(
                        request,
                        "No valid results were found.",
                    )

                for error in errors[:5]:
                    messages.warning(
                        request,
                        error,
                    )

                if len(errors) > 5:
                    messages.info(
                        request,
                        (
                            f"...and "
                            f"{len(errors) - 5} more errors."
                        ),
                    )

                return redirect(exam_list_url)

            except Exam.DoesNotExist:
                messages.error(
                    request,
                    "The selected exam was not found.",
                )

            except Subject.DoesNotExist:
                messages.error(
                    request,
                    "The selected subject was not found.",
                )

            except Exception as error:
                messages.error(
                    request,
                    f"Error processing file: {error}",
                )

            return redirect(bulk_enter_url)

        context = {
            "exams": exams,
            "subjects": subjects,
            "title": "Bulk Results Upload",
            "school": SchoolSetting.objects.first(),
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_exam_list_url": exam_list_url,
            "tenant_bulk_enter_url": bulk_enter_url,
        }

        return render(
            request,
            "performance/bulk_excel_upload.html",
            context,
        )
# ========== TEACHER DASHBOARD ==========
def _resolve_required_tenant_schema(request, tenant_schema=None):
    """
    Resolve the active tenant schema and prevent tenant-only views from
    silently running against the public schema.
    """
    from django.db import connection
    from django.core.exceptions import PermissionDenied

    schema_name = resolve_tenant_schema(request, tenant_schema)

    if not schema_name or schema_name == "public":
        schema_name = getattr(connection, "schema_name", None)

    if not schema_name or schema_name == "public":
        raise PermissionDenied(
            "This page must be opened from a school tenant URL."
        )

    return schema_name


def _tenant_context(request, schema_name):
    """Shared tenant-aware context values for teacher-facing templates."""
    return {
        "tenant_schema": schema_name,
        "current_tenant_schema": schema_name,
        "tenant_base_url": f"/tenant/{schema_name}/app",
        "app_prefix": f"/tenant/{schema_name}/app",
    }

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def teacher_required(view_func):
    """Allow only authenticated teacher accounts."""

    @wraps(view_func)
    def wrapper(
        request,
        tenant_schema=None,
        *args,
        **kwargs,
    ):
        schema_name = resolve_tenant_schema(
            request,
            tenant_schema,
        )

        if not request.user.is_authenticated:
            login_url = (
                f"/tenant/{schema_name}/app/login/"
                if schema_name
                and schema_name != "public"
                else "/app/login/"
            )

            return redirect(
                f"{login_url}?next={request.path}"
            )

        profile = getattr(
            request.user,
            "profile",
            None,
        )

        if not profile or profile.role != "teacher":
            messages.error(
                request,
                "Access denied. Only teachers can access this page.",
            )

            if schema_name and schema_name != "public":
                return redirect(
                    f"/tenant/{schema_name}/app/"
                )

            return redirect("/app/")

        return view_func(
            request,
            tenant_schema=tenant_schema,
            *args,
            **kwargs,
        )

    return wrapper
@teacher_required
def teacher_dashboard(request, tenant_schema=None, *args, **kwargs):
    """Teacher dashboard showing class and subject responsibilities."""
    from decimal import Decimal

    from django.contrib import messages
    from django.shortcuts import redirect, render
    from django_tenants.utils import schema_context

    from .models import (
        CBEGradingPathway,
        Class,
        Exam,
        GradingSystem,
        PerformanceSummary,
        StudentResult,
        TeacherGradingPreference,
        TeacherSubject,
    )

    schema_name = _resolve_required_tenant_schema(
        request,
        tenant_schema,
    )

    with schema_context(schema_name):
        profile = getattr(request.user, "profile", None)

        if not profile or profile.role != "teacher":
            messages.error(
                request,
                "Access denied. Only teachers can access this page.",
            )
            return redirect(
                f"/tenant/{schema_name}/app/"
            )

        my_class = (
            Class.objects.filter(class_teacher=request.user)
            .first()
        )

        my_subjects = (
            TeacherSubject.objects.filter(
                teacher=request.user,
            )
            .select_related(
                "subject",
                "class_assigned",
            )
        )

        teacher_preference = (
            TeacherGradingPreference.objects.filter(
                teacher=request.user,
                is_global=True,
            )
            .first()
        )

        if not teacher_preference:
            teacher_preference = (
                TeacherGradingPreference.objects.create(
                    teacher=request.user,
                    grading_choice="traditional",
                    is_global=True,
                )
            )

        subject_ids = list(
            my_subjects.values_list(
                "subject_id",
                flat=True,
            )
        )

        recent_exams = (
            Exam.objects.filter(
                subject__id__in=subject_ids,
            )
            .order_by("-created_at")[:5]
            if subject_ids
            else Exam.objects.none()
        )

        recent_results = (
            StudentResult.objects.filter(
                entered_by=request.user,
            )
            .select_related(
                "student",
                "exam",
                "subject",
            )
            .order_by("-id")[:10]
        )

        student_count = (
            my_class.students.count()
            if my_class
            else 0
        )

        available_grading_systems = (
            GradingSystem.objects.filter(
                is_active=True,
            )[:5]
        )

        available_cbe_pathways = (
            CBEGradingPathway.objects.filter(
                is_active=True,
            )[:5]
        )

        context = {
            **_tenant_context(request, schema_name),
            "my_class": my_class,
            "my_subjects": my_subjects,
            "recent_exams": recent_exams,
            "recent_results": recent_results,
            "has_class": my_class is not None,
            "has_subjects": my_subjects.exists(),
            "has_results": recent_results.exists(),
            "student_count": student_count,
            "teacher_preference": teacher_preference,
            "available_grading_systems": (
                available_grading_systems
            ),
            "available_cbe_pathways": (
                available_cbe_pathways
            ),
            "title": "Teacher Dashboard",
        }

        return render(
            request,
            "digitallibrary/teacher_dashboard.html",
            context,
        )


@teacher_required
def class_teacher_dashboard(
    request,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """Class teacher dashboard."""
    from django.shortcuts import render
    from django_tenants.utils import schema_context

    from .models import Class, Exam, Result, Student

    schema_name = _resolve_required_tenant_schema(
        request,
        tenant_schema,
    )

    with schema_context(schema_name):
        assigned_class = (
            Class.objects.filter(
                class_teacher=request.user,
            )
            .first()
        )

        exams = Exam.objects.all().order_by(
            "-academic_year",
            "-created_at",
        )

        students_queryset = Student.objects.filter(
            is_active=True,
        )

        if assigned_class:
            students_queryset = students_queryset.filter(
                current_class=assigned_class,
            )

        total_students = students_queryset.count()

        exams_data = []

        for exam in exams:
            results_query = Result.objects.filter(
                exam=exam,
                student__in=students_queryset,
            )

            results_count_total = (
                results_query.values("student")
                .distinct()
                .count()
            )

            exams_data.append({
                "id": exam.id,
                "name": exam.name,
                "academic_year": exam.academic_year,
                "term": exam.term,
                "results_count": results_count_total,
                "total_students": total_students,
                "subject_progress": [],
            })

        context = {
            **_tenant_context(request, schema_name),
            "assigned_class": assigned_class,
            "total_exams": exams.count(),
            "completed_exams": 0,
            "in_progress_exams": 0,
            "total_students": total_students,
            "exams": exams_data,
            "top_students": [],
            "title": "Class Teacher Dashboard",
        }

        return render(
            request,
            "performance/class_teacher_dashboard.html",
            context,
        )


@teacher_required
def compile_results_overview(
    request,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """Overview of all exams ready for compilation."""
    from django.shortcuts import render
    from django_tenants.utils import schema_context

    from .models import Exam

    schema_name = _resolve_required_tenant_schema(
        request,
        tenant_schema,
    )

    with schema_context(schema_name):
        exams = Exam.objects.all().order_by(
            "-academic_year",
            "-created_at",
        )

        context = {
            **_tenant_context(request, schema_name),
            "exams": exams,
            "title": "Compile Results",
        }

        return render(
            request,
            "performance/compile_results_overview.html",
            context,
        )


@teacher_required
def exam_compilation(
    request,
    exam_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """Compile results for a specific exam."""
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect, render
    from django_tenants.utils import schema_context

    from .models import (
        Exam,
        ExamResultSummary,
        Result,
        Student,
        Subject,
    )

    schema_name = _resolve_required_tenant_schema(
        request,
        tenant_schema,
    )

    with schema_context(schema_name):
        exam = get_object_or_404(
            Exam,
            id=exam_id,
        )

        students = Student.objects.filter(
            is_active=True,
        )

        total_students = students.count()
        subjects = Subject.objects.all()

        subjects_data = []
        subjects_completed = 0

        for subject in subjects:
            results_count = Result.objects.filter(
                exam=exam,
                subject=subject,
            ).count()

            completion_rate = (
                results_count / total_students * 100
                if total_students > 0
                else 0
            )

            if completion_rate >= 100:
                subjects_completed += 1

            subjects_data.append({
                "subject": subject,
                "results_entered": results_count,
                "completion_rate": completion_rate,
                "teacher": "Not assigned",
            })

        total_subjects = subjects.count()

        completion_percentage = (
            subjects_completed / total_subjects * 100
            if total_subjects > 0
            else 0
        )

        all_subjects_complete = (
            total_subjects > 0
            and subjects_completed == total_subjects
        )

        if (
            request.method == "POST"
            and all_subjects_complete
        ):
            for student in students:
                results = Result.objects.filter(
                    exam=exam,
                    student=student,
                )

                result_count = results.count()

                total_score = sum(
                    result.score
                    for result in results
                )

                avg_score = (
                    total_score / result_count
                    if result_count > 0
                    else 0
                )

                if avg_score >= 80:
                    grade = "A"
                elif avg_score >= 70:
                    grade = "B"
                elif avg_score >= 60:
                    grade = "C"
                elif avg_score >= 50:
                    grade = "D"
                else:
                    grade = "E"

                ExamResultSummary.objects.update_or_create(
                    exam=exam,
                    student=student,
                    defaults={
                        "total_score": total_score,
                        "average_score": avg_score,
                        "overall_grade": grade,
                    },
                )

            summaries = (
                ExamResultSummary.objects.filter(
                    exam=exam,
                )
                .order_by("-average_score")
            )

            for rank, summary in enumerate(
                summaries,
                start=1,
            ):
                summary.rank = rank
                summary.save(update_fields=["rank"])

            messages.success(
                request,
                (
                    "Results compiled successfully "
                    f"for {exam.name}!"
                ),
            )

            ranking_path = reverse(
                "digitallibrary:exam_ranking",
                kwargs={"exam_id": exam.id},
            )

            return redirect(
                f"/tenant/{schema_name}{ranking_path}"
            )

        context = {
            **_tenant_context(request, schema_name),
            "exam": exam,
            "subjects_data": subjects_data,
            "total_subjects": total_subjects,
            "subjects_completed": subjects_completed,
            "completion_percentage": (
                completion_percentage
            ),
            "all_subjects_complete": (
                all_subjects_complete
            ),
            "total_students": total_students,
            "subjects_incomplete": (
                total_subjects
                - subjects_completed
            ),
            "title": f"Compile {exam.name}",
        }

        return render(
            request,
            "performance/exam_compilation.html",
            context,
        )


@teacher_required
def exam_ranking(
    request,
    exam_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """View rankings for a compiled exam."""
    from django.db import models
    from django.shortcuts import get_object_or_404, render
    from django_tenants.utils import schema_context

    from .models import Exam, ExamResultSummary

    schema_name = _resolve_required_tenant_schema(
        request,
        tenant_schema,
    )

    with schema_context(schema_name):
        exam = get_object_or_404(
            Exam,
            id=exam_id,
        )

        rankings = (
            ExamResultSummary.objects.filter(
                exam=exam,
            )
            .select_related("student")
            .order_by("rank")
        )

        class_average = (
            rankings.aggregate(
                avg=models.Avg("average_score"),
            )["avg"]
            or 0
        )

        ranking_count = rankings.count()

        pass_count = rankings.filter(
            average_score__gte=50,
        ).count()

        pass_rate = (
            pass_count / ranking_count * 100
            if ranking_count > 0
            else 0
        )

        top_student_summary = rankings.first()

        context = {
            **_tenant_context(request, schema_name),
            "exam": exam,
            "rankings": rankings,
            "class_average": class_average,
            "pass_rate": pass_rate,
            "top_student": (
                top_student_summary.student
                if top_student_summary
                else None
            ),
            "title": f"{exam.name} Rankings",
        }

        return render(
            request,
            "performance/exam_ranking.html",
            context,
        )


@teacher_required
def class_ranking(
    request,
    class_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """View rankings for a class across all exams."""
    from django.db import models
    from django.shortcuts import get_object_or_404, render
    from django_tenants.utils import schema_context

    from .models import Class, ExamResultSummary, Student

    schema_name = _resolve_required_tenant_schema(
        request,
        tenant_schema,
    )

    with schema_context(schema_name):
        class_obj = get_object_or_404(
            Class,
            id=class_id,
        )

        students = Student.objects.filter(
            current_class=class_obj,
            is_active=True,
        )

        student_summaries = []

        for student in students:
            summaries = ExamResultSummary.objects.filter(
                student=student,
            )

            if summaries.exists():
                avg_overall = (
                    summaries.aggregate(
                        avg=models.Avg(
                            "average_score"
                        ),
                    )["avg"]
                    or 0
                )

                student_summaries.append({
                    "student": student,
                    "average_score": avg_overall,
                    "exams_taken": summaries.count(),
                })

        student_summaries.sort(
            key=lambda item: item["average_score"],
            reverse=True,
        )

        context = {
            **_tenant_context(request, schema_name),
            "class_obj": class_obj,
            "rankings": student_summaries,
            "title": f"{class_obj} Rankings",
        }

        return render(
            request,
            "performance/class_ranking.html",
            context,
        )


@teacher_required
def export_ranking_csv(
    request,
    exam_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """Export exam rankings to CSV."""
    import csv

    from django.http import HttpResponse
    from django.shortcuts import get_object_or_404
    from django_tenants.utils import schema_context

    from .models import Exam, ExamResultSummary

    schema_name = _resolve_required_tenant_schema(
        request,
        tenant_schema,
    )

    with schema_context(schema_name):
        exam = get_object_or_404(
            Exam,
            id=exam_id,
        )

        rankings = (
            ExamResultSummary.objects.filter(
                exam=exam,
            )
            .select_related("student")
            .order_by("rank")
        )

        response = HttpResponse(
            content_type="text/csv",
        )

        response["Content-Disposition"] = (
            f'attachment; filename="{exam.name}_rankings.csv"'
        )

        writer = csv.writer(response)

        writer.writerow([
            "Rank",
            "Admission Number",
            "Student Name",
            "Total Score",
            "Average Score",
            "Grade",
        ])

        for ranking in rankings:
            writer.writerow([
                ranking.rank,
                ranking.student.admission_number,
                (
                    f"{ranking.student.first_name} "
                    f"{ranking.student.last_name}"
                ),
                ranking.total_score,
                ranking.average_score,
                ranking.overall_grade,
            ])

        return response


@teacher_required
def subject_exam_performance(
    request,
    subject_id,
    exam_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """View performance for a specific subject in an exam."""
    from django.db import models
    from django.shortcuts import get_object_or_404, render
    from django_tenants.utils import schema_context

    from .models import Exam, Result, Student, Subject

    schema_name = _resolve_required_tenant_schema(
        request,
        tenant_schema,
    )

    with schema_context(schema_name):
        subject = get_object_or_404(
            Subject,
            id=subject_id,
        )

        exam = get_object_or_404(
            Exam,
            id=exam_id,
        )

        results = (
            Result.objects.filter(
                exam=exam,
                subject=subject,
            )
            .select_related("student")
        )

        total_students = Student.objects.filter(
            is_active=True,
        ).count()

        aggregates = results.aggregate(
            avg=models.Avg("score"),
            maximum=models.Max("score"),
            minimum=models.Min("score"),
        )

        context = {
            **_tenant_context(request, schema_name),
            "subject": subject,
            "exam": exam,
            "results": results,
            "total_students": total_students,
            "avg_score": aggregates["avg"] or 0,
            "top_score": (
                aggregates["maximum"] or 0
            ),
            "lowest_score": (
                aggregates["minimum"] or 0
            ),
            "title": (
                f"{subject} Performance"
            ),
        }

        return render(
            request,
            "performance/subject_exam_performance.html",
            context,
        )


@teacher_required
def view_subject_results(
    request,
    exam_id,
    subject_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """View all results for a subject in an exam."""
    from django.shortcuts import get_object_or_404, render
    from django_tenants.utils import schema_context

    from .models import Exam, Result, Subject

    schema_name = _resolve_required_tenant_schema(
        request,
        tenant_schema,
    )

    with schema_context(schema_name):
        exam = get_object_or_404(
            Exam,
            id=exam_id,
        )

        subject = get_object_or_404(
            Subject,
            id=subject_id,
        )

        results = (
            Result.objects.filter(
                exam=exam,
                subject=subject,
            )
            .select_related("student")
            .order_by("-score")
        )

        context = {
            **_tenant_context(request, schema_name),
            "exam": exam,
            "subject": subject,
            "results": results,
            "title": (
                f"{subject} Results"
            ),
        }

        return render(
            request,
            "performance/view_subject_results.html",
            context,
        )


@teacher_required
def student_performance_tracking(
    request,
    student_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """Track student performance across different exams."""
    from django.shortcuts import get_object_or_404, render
    from django_tenants.utils import schema_context

    from .models import Result, Student

    schema_name = _resolve_required_tenant_schema(
        request,
        tenant_schema,
    )

    with schema_context(schema_name):
        student = get_object_or_404(
            Student,
            id=student_id,
        )

        results = (
            Result.objects.filter(
                student=student,
            )
            .select_related(
                "exam",
                "subject",
            )
            .order_by(
                "-exam__academic_year",
                "-exam__created_at",
            )
        )

        subjects_data = {}

        for result in results:
            subject_name = result.subject.name

            subjects_data.setdefault(
                subject_name,
                [],
            )

            subjects_data[subject_name].append({
                "exam_name": result.exam.name,
                "exam_term": result.exam.term,
                "exam_year": (
                    result.exam.academic_year
                ),
                "score": result.score,
                "grade": getattr(
                    result,
                    "grade",
                    "C",
                ),
            })

        subject_averages = {}

        for subject_name, scores in (
            subjects_data.items()
        ):
            subject_averages[subject_name] = (
                sum(
                    item["score"]
                    for item in scores
                )
                / len(scores)
                if scores
                else 0
            )

        context = {
            **_tenant_context(request, schema_name),
            "student": student,
            "subjects_data": subjects_data,
            "subject_averages": subject_averages,
            "total_exams": (
                results.values("exam")
                .distinct()
                .count()
            ),
            "title": (
                f"{student} Performance"
            ),
        }

        return render(
            request,
            "performance/student_performance_tracking.html",
            context,
        )

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

from django.contrib import messages
from django.db import connection
from django.db.models import Avg, Count, Max, Min
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django_tenants.utils import schema_context

from .decorators import teacher_required
from .models import Class, Exam, PerformanceSummary, SchoolSetting, Student, StudentResult, Subject


def _resolve_tenant_schema(request, tenant_schema=None):
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )
    if not schema_name or schema_name == "public":
        parts = request.path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "tenant":
            schema_name = parts[1]
    return schema_name


@teacher_required
def subject_performance(request, subject_id, tenant_schema=None, *args, **kwargs):
    """View performance for a specific subject."""
    schema_name = _resolve_tenant_schema(request, tenant_schema)
    if not schema_name or schema_name == "public":
        messages.error(request, "School tenant context was not detected.")
        return redirect("/app/")

    tenant_base_url = f"/tenant/{schema_name}/app"

    with schema_context(schema_name):
        subject = get_object_or_404(Subject, pk=subject_id)
        academic_year = request.GET.get("year", str(timezone.now().year))
        term = request.GET.get("term", "1")

        exams = Exam.objects.filter(academic_year=academic_year, term=term)
        results = (
            StudentResult.objects.filter(subject=subject, exam__in=exams)
            .select_related("student", "exam")
            .order_by("-exam__academic_year", "-exam__term", "student__first_name")
        )
        metrics = results.aggregate(
            avg_score=Avg("score"),
            top_score=Max("score"),
            lowest_score=Min("score"),
        )

        context = {
            "subject": subject,
            "exams": exams,
            "results": results,
            "avg_score": metrics["avg_score"] or 0,
            "top_score": metrics["top_score"] or 0,
            "lowest_score": metrics["lowest_score"] or 0,
            "academic_year": academic_year,
            "term": term,
            "school": SchoolSetting.objects.first(),
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
            "tenant_performance_url": f"{tenant_base_url}/performance/",
            "tenant_exam_list_url": f"{tenant_base_url}/exams/",
        }
        return render(request, "performance/subject_performance.html", context)


@teacher_required
def class_performance(request, class_id, tenant_schema=None, *args, **kwargs):
    """View performance for a specific class."""
    schema_name = _resolve_tenant_schema(request, tenant_schema)
    if not schema_name or schema_name == "public":
        messages.error(request, "School tenant context was not detected.")
        return redirect("/app/")

    tenant_base_url = f"/tenant/{schema_name}/app"

    with schema_context(schema_name):
        student_class = get_object_or_404(Class, pk=class_id)
        academic_year = request.GET.get("year", str(timezone.now().year))
        term = request.GET.get("term", "1")

        students = Student.objects.filter(current_class=student_class, is_active=True)
        summaries = (
            PerformanceSummary.objects.filter(
                student__in=students,
                academic_year=academic_year,
                term=term,
            )
            .select_related("student")
            .order_by("rank_in_class", "-average_score")
        )
        avg_class_score = summaries.aggregate(avg=Avg("average_score"))["avg"] or 0

        context = {
            "class": student_class,
            "summaries": summaries,
            "academic_year": academic_year,
            "term": term,
            "avg_class_score": avg_class_score,
            "total_students": students.count(),
            "total_passed": summaries.filter(average_score__gte=50).count(),
            "school": SchoolSetting.objects.first(),
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
            "tenant_performance_url": f"{tenant_base_url}/performance/",
            "tenant_exam_list_url": f"{tenant_base_url}/exams/",
        }
        return render(request, "performance/class_performance.html", context)


@teacher_required
def performance_reports(request, tenant_schema=None, *args, **kwargs):
    """Comprehensive tenant-safe performance reports."""
    schema_name = _resolve_tenant_schema(request, tenant_schema)
    if not schema_name or schema_name == "public":
        messages.error(request, "School tenant context was not detected.")
        return redirect("/app/")

    tenant_base_url = f"/tenant/{schema_name}/app"

    with schema_context(schema_name):
        academic_year = request.GET.get("year", "")
        term = request.GET.get("term", "")
        selected_class = request.GET.get("class", "")
        selected_exam = request.GET.get("exam", "")

        results_qs = StudentResult.objects.all()
        if academic_year:
            results_qs = results_qs.filter(exam__academic_year=academic_year)
        if term:
            results_qs = results_qs.filter(exam__term=term)
        if selected_class:
            results_qs = results_qs.filter(student__current_class_id=selected_class)
        if selected_exam:
            results_qs = results_qs.filter(exam_id=selected_exam)

        students_qs = Student.objects.filter(is_active=True)
        if selected_class:
            students_qs = students_qs.filter(current_class_id=selected_class)

        total_students = students_qs.count()
        avg_score = results_qs.aggregate(avg=Avg("score"))["avg"] or 0
        total_results = results_qs.count()
        passed_results = results_qs.filter(score__gte=50).count()
        pass_rate = (passed_results / total_results * 100) if total_results else 0
        passed_students = results_qs.filter(score__gte=50).values("student").distinct().count()

        grade_ranges = {
            "A": (80, 100), "A-": (75, 79), "B+": (70, 74),
            "B": (65, 69), "B-": (60, 64), "C+": (55, 59),
            "C": (50, 54), "C-": (45, 49), "D+": (40, 44),
            "D": (35, 39), "E": (0, 34),
        }

        overall_grade_distribution = {}
        for grade, (minimum, maximum) in grade_ranges.items():
            count = results_qs.filter(score__gte=minimum, score__lte=maximum).count()
            overall_grade_distribution[grade] = {
                "count": count,
                "percentage": (count / total_results * 100) if total_results else 0,
            }

        exams = Exam.objects.all()
        if academic_year:
            exams = exams.filter(academic_year=academic_year)
        if term:
            exams = exams.filter(term=term)
        if selected_class:
            exams = exams.filter(student_class_id=selected_class)
        if selected_exam:
            exams = exams.filter(id=selected_exam)

        exams_summary = []
        for exam in exams:
            exam_results = results_qs.filter(exam=exam)
            if not exam_results.exists():
                continue
            exam_count = exam_results.count()
            avg = exam_results.aggregate(avg=Avg("score"))["avg"] or 0
            passed = exam_results.filter(score__gte=50).count()
            top_score = exam_results.aggregate(highest=Max("score"))["highest"] or 0
            if top_score >= 80: top_grade = "A"
            elif top_score >= 75: top_grade = "A-"
            elif top_score >= 70: top_grade = "B+"
            elif top_score >= 65: top_grade = "B"
            elif top_score >= 60: top_grade = "B-"
            elif top_score >= 50: top_grade = "C"
            else: top_grade = "E"
            exams_summary.append({
                "id": exam.id,
                "name": exam.name,
                "academic_year": exam.academic_year,
                "term": exam.term,
                "students": exam_results.values("student").distinct().count(),
                "avg_score": avg,
                "pass_rate": (passed / exam_count * 100) if exam_count else 0,
                "top_grade": top_grade,
            })

        exam_grade_distribution = []
        for exam in exams[:10]:
            exam_results = results_qs.filter(exam=exam)
            if not exam_results.exists():
                continue
            distribution = {}
            for grade, (minimum, maximum) in grade_ranges.items():
                count = exam_results.filter(score__gte=minimum, score__lte=maximum).count()
                if count:
                    distribution[grade] = count
            exam_grade_distribution.append({
                "id": exam.id,
                "name": exam.name,
                "academic_year": exam.academic_year,
                "term": exam.term,
                "distribution": distribution,
                "total_results": exam_results.count(),
            })

        top_students_data = (
            results_qs.values("student")
            .annotate(avg=Avg("score"), exams_taken=Count("exam", distinct=True))
            .order_by("-avg")[:20]
        )
        student_map = {
            student.id: student
            for student in Student.objects.filter(
                id__in=[item["student"] for item in top_students_data]
            )
        }
        top_students = []
        for item in top_students_data:
            student = student_map.get(item["student"])
            if not student:
                continue
            average = item["avg"] or 0
            if average >= 80: grade = "A"
            elif average >= 75: grade = "A-"
            elif average >= 70: grade = "B+"
            elif average >= 65: grade = "B"
            elif average >= 60: grade = "B-"
            elif average >= 55: grade = "C+"
            elif average >= 50: grade = "C"
            else: grade = "D"
            top_students.append({
                "student": student,
                "average": average,
                "grade": grade,
                "exams_taken": item["exams_taken"],
            })

        subject_performance_data = []
        for subject in Subject.objects.all():
            subject_results = results_qs.filter(subject=subject)
            if not subject_results.exists():
                continue
            count = subject_results.count()
            average = subject_results.aggregate(avg=Avg("score"))["avg"] or 0
            passed = subject_results.filter(score__gte=50).count()
            if average >= 80: grade = "A"
            elif average >= 70: grade = "B"
            elif average >= 60: grade = "C"
            elif average >= 50: grade = "D"
            else: grade = "E"
            subject_performance_data.append({
                "id": subject.id,
                "name": subject.name,
                "students": subject_results.values("student").distinct().count(),
                "average": average,
                "pass_rate": (passed / count * 100) if count else 0,
                "grade": grade,
            })

        class_performance_data = []
        for class_obj in Class.objects.all():
            class_results = results_qs.filter(student__current_class=class_obj)
            if not class_results.exists():
                continue
            count = class_results.count()
            average = class_results.aggregate(avg=Avg("score"))["avg"] or 0
            passed = class_results.filter(score__gte=50).count()
            if average >= 80: grade = "A"
            elif average >= 70: grade = "B"
            elif average >= 60: grade = "C"
            elif average >= 50: grade = "D"
            else: grade = "E"
            class_performance_data.append({
                "id": class_obj.id,
                "name": class_obj.name,
                "students": class_results.values("student").distinct().count(),
                "average": average,
                "pass_rate": (passed / count * 100) if count else 0,
                "grade": grade,
            })

        year_choices = Exam.objects.values_list("academic_year", flat=True).distinct().order_by("-academic_year")
        classes = Class.objects.all().order_by("name")
        exam_choices = Exam.objects.all().order_by("-academic_year", "-created_at")

        context = {
            "total_students": total_students,
            "avg_score": avg_score,
            "pass_rate": pass_rate,
            "pass_count": passed_students,
            "top_students": top_students,
            "subject_performance": subject_performance_data,
            "class_performance": class_performance_data,
            "year_choices": year_choices,
            "academic_year": academic_year,
            "term": term,
            "selected_class": selected_class,
            "classes": classes,
            "total_exams": exams.count(),
            "total_results_count": total_results,
            "overall_grade_distribution": overall_grade_distribution,
            "exams_summary": exams_summary,
            "exam_grade_distribution": exam_grade_distribution,
            "exam_choices": exam_choices,
            "selected_exam": selected_exam,
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
            "tenant_exam_list_url": f"{tenant_base_url}/exams/",
            "tenant_performance_url": f"{tenant_base_url}/performance/",
        }
        return render(request, "performance/performance_reports.html", context)

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
    from django.db import connection
    from django.core.paginator import Paginator
    from .models import Student, Class, SchoolSetting
    
    # Removed manual role check since decorator handles it
    
    # Get teacher count using SQL (no UserProfile)
    total_teachers = 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_staff = true AND is_superuser = false AND is_active = true")
            result = cursor.fetchone()
            total_teachers = result[0] if result else 0
    except Exception as e:
        print(f"Error counting teachers: {e}")
    
    # Get student counts
    total_students = Student.objects.filter(is_active=True).count()
    students_with_phone = Student.objects.filter(is_active=True, parent_phone__isnull=False).exclude(parent_phone='').count()
    
    # Get paginated students
    all_students = Student.objects.filter(is_active=True).select_related('current_class').order_by('first_name', 'last_name')
    paginator = Paginator(all_students, 20)
    page_number = request.GET.get('page', 1)
    students = paginator.get_page(page_number)
    
    # Get classes
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
    """Submit user feedback with beautiful email template"""
    if request.method == 'POST':
        form = FeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.page_url = request.META.get('HTTP_REFERER', '')
            
            # Get school info from tenant if available
            if hasattr(request, 'tenant') and request.tenant:
                feedback.school_id = request.tenant.schema_name
                feedback.school_name = request.tenant.name
                feedback.school_location = getattr(request.tenant, 'location', 'Kenya')
            else:
                feedback.school_id = getattr(settings, 'SCHOOL_ID', 'unknown')
                feedback.school_name = getattr(settings, 'SCHOOL_NAME', 'ShuleHub')
                feedback.school_location = getattr(settings, 'SCHOOL_LOCATION', 'Kenya')
            
            feedback.save()
            
            # Handle screenshot if uploaded
            if 'screenshot' in request.FILES:
                screenshot = request.FILES['screenshot']
                # You can save screenshot logic here
                pass
            
            # Prepare email context for beautiful template
            from django.template.loader import render_to_string
            from django.core.mail import send_mail
            from django.utils.html import strip_tags
            
            # Get user info
            user_name = feedback.user.get_full_name() or feedback.user.username
            user_email = feedback.user.email
            user_role = feedback.user.profile.role if hasattr(feedback.user, 'profile') else 'User'
            
            # Get admin URL
            admin_url = request.build_absolute_uri('/admin/digitallibrary/feedback/')
            
            # Email context
            context = {
                'school_name': feedback.school_name or 'ShuleHub',
                'school_location': feedback.school_location or 'Kenya',
                'school_id': feedback.school_id or 'N/A',
                'user_name': user_name,
                'user_role': user_role.upper() if user_role else 'USER',
                'user_email': user_email or 'Not provided',
                'feedback_type': feedback.feedback_type,
                'priority': feedback.priority,
                'rating': feedback.rating if feedback.rating else None,
                'subject': feedback.subject,
                'message': feedback.message,
                'admin_url': admin_url,
                'has_rating': feedback.rating is not None,
            }
            
            # Render HTML email
            html_message = render_to_string('emails/feedback_notification.html', context)
            plain_message = strip_tags(html_message)
            
            subject = f"[Feedback] {feedback.school_name} - {feedback.subject}"
            
            try:
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=settings.ADMIN_EMAILS,
                    html_message=html_message,
                    fail_silently=False,
                )
                print(f"✅ Feedback email sent to {settings.ADMIN_EMAILS}")
            except Exception as e:
                print(f"❌ Email error: {e}")
                # Fallback to simple email if HTML fails
                try:
                    simple_message = f"""
                    School: {feedback.school_name}
                    From: {user_name}
                    Email: {user_email}
                    Role: {user_role}
                    Type: {feedback.get_feedback_type_display()}
                    Rating: {feedback.rating or 'No rating'}/5
                    Priority: {feedback.priority}
                    Subject: {feedback.subject}
                    Message: {feedback.message}
                    """
                    send_mail(
                        subject=subject,
                        message=simple_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=settings.ADMIN_EMAILS,
                        fail_silently=False,
                    )
                except Exception as e2:
                    print(f"❌ Fallback email also failed: {e2}")
            
            messages.success(request, 'Thank you for your feedback! Our team has been notified.')
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
        'title': 'Thank You for Your Feedback',
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
    """Enter results for an exam - by subject, filtered by registered student subjects"""
    exam = get_object_or_404(Exam, pk=exam_id)

    # Show all active subjects for selection
    subjects = Subject.objects.filter(is_active=True).order_by('name')

    selected_subject_id = request.GET.get('subject')
    selected_subject = None
    students = []
    existing_results = {}

    if selected_subject_id:
        try:
            selected_subject = Subject.objects.get(pk=selected_subject_id, is_active=True)

            # Get students for this exam
            students_qs = exam.get_students_for_exam()

            # IMPORTANT:
            # Only show students registered for the selected subject
            students = students_qs.filter(
                subjects=selected_subject,
                is_active=True
            ).distinct().order_by('admission_number')

            existing_results_qs = StudentResult.objects.filter(
                exam=exam,
                subject=selected_subject,
                student__in=students
            ).select_related('student')

            existing_results = {
                result.student_id: result
                for result in existing_results_qs
            }

        except Subject.DoesNotExist:
            messages.error(request, "Selected subject does not exist.")

    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')

        if subject_id:
            selected_subject = get_object_or_404(Subject, pk=subject_id, is_active=True)

            students = exam.get_students_for_exam().filter(
                subjects=selected_subject,
                is_active=True
            ).distinct()

            saved_count = 0

            for student in students:
                score_key = f'score_{student.id}'
                if score_key in request.POST:
                    score = request.POST.get(score_key)

                    if score and score.strip():
                        try:
                            score_value = float(score)

                            if 0 <= score_value <= float(exam.max_score):
                                StudentResult.objects.update_or_create(
                                    student=student,
                                    exam=exam,
                                    subject=selected_subject,
                                    defaults={
                                        'score': score_value,
                                        'entered_by': request.user
                                    }
                                )
                                saved_count += 1

                        except ValueError:
                            pass

            if saved_count > 0:
                update_performance_summary_for_exam(exam)
                messages.success(
                    request,
                    f'Results for {exam.name} - {selected_subject.name} saved successfully! '
                    f'{saved_count} records updated.'
                )
            else:
                messages.warning(
                    request,
                    'No results were saved. Confirm that students are registered for this subject.'
                )

            return redirect(f'{request.path}?subject={subject_id}')

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
    redirect_authenticated_user = True

    def get_tenant_schema(self):
        """
        Detect tenant schema from URL like:
        /tenant/nyaneje/app/login/
        """
        tenant_schema = self.kwargs.get("tenant_schema")

        if not tenant_schema:
            match = re.match(r"^/tenant/([^/]+)/", self.request.path or "")
            if match:
                tenant_schema = match.group(1)

        return tenant_schema

    def get_next_url(self):
        tenant_schema = self.get_tenant_schema()

        next_url = (
            self.request.POST.get("next")
            or self.request.GET.get("next")
            or ""
        )

        if next_url:
            return next_url

        if tenant_schema:
            return f"/tenant/{tenant_schema}/app/dashboard/"

        return "/app/dashboard/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        tenant_schema = self.get_tenant_schema()

        try:
            context["school"] = SchoolSetting.objects.first()
        except Exception:
            context["school"] = None

        context["tenant_schema"] = tenant_schema
        context["next"] = self.get_next_url()

        return context

    def post(self, request, *args, **kwargs):
        """
        Custom tenant-aware authentication.

        This avoids authenticating against the public schema when the user is
        logging in through /tenant/<schema>/app/login/.
        """
        from django.contrib.auth import get_user_model, login
        from django.contrib import messages
        from django.shortcuts import redirect
        from django_tenants.utils import schema_context

        tenant_schema = self.get_tenant_schema()
        active_schema = tenant_schema or "public"
        next_url = self.get_next_url()

        username = (
            request.POST.get("username")
            or request.POST.get("email")
            or ""
        ).strip()

        password = request.POST.get("password") or ""

        User = get_user_model()
        user = None

        try:
            with schema_context(active_schema):
                user = (
                    User.objects.filter(username=username).first()
                    or User.objects.filter(email=username).first()
                )

                if user:
                    if not user.is_active:
                        user = None
                    elif not user.check_password(password):
                        user = None

        except Exception as e:
            print(f"❌ Tenant login error in schema {active_schema}: {e}")
            user = None

        if user is not None:
            user.backend = "django.contrib.auth.backends.ModelBackend"

            login(request, user)

            if tenant_schema:
                request.session["tenant_schema"] = tenant_schema

            request.session.modified = True
            

            print(f"✅ LOGIN SUCCESS for {username} in schema {active_schema}")
            return redirect(next_url)

        print(f"❌ LOGIN FAILED for {username} in schema {active_schema}")

        messages.error(
            request,
            "Please enter a correct username and password. Note that both fields may be case-sensitive."
        )

        return self.render_to_response(self.get_context_data())


def home(request, tenant_schema=None):
    """
    Home page - Shows landing page for public schema, dashboard for tenants
    """
    from django.db import connection
    from django.shortcuts import render, redirect
    from .models import Resource, Announcement, SchoolSetting, Student
    from django.utils import timezone
    from django.db.models import Q, Sum
    import logging

    logger = logging.getLogger(__name__)

    # Get current schema name and host
    current_schema = connection.schema_name
    host = request.get_host().split(':')[0]

    print(f"Initial schema: {current_schema}")
    print(f"Tenant schema argument: {tenant_schema}")
    print(f"Tenant exists: {hasattr(request, 'tenant')}")

    # Temporary fallback for Render path-based tenancy
    if current_schema == "public" and tenant_schema:
        try:
            from tenants.models import School

            tenant = School.objects.filter(
                schema_name=tenant_schema
            ).first()

            if tenant:
                print(f"🔄 Switching to tenant {tenant_schema}")

                connection.set_tenant(tenant)
                request.tenant = tenant

                current_schema = connection.schema_name

                print(f"✅ Schema switched to {current_schema}")

        except Exception as e:
            print(f"❌ Tenant switch failed: {e}")

    print(f"\n{'='*60}")
    print(f"HOME VIEW - Schema: {current_schema}")
    print(f"Host: {host}")
    print(f"Path: {request.path}")
    print(f"User authenticated: {request.user.is_authenticated}")

    if request.user.is_authenticated:
        print(f"Username: {request.user.username}")

    print(f"{'='*60}\n")

    # PUBLIC LANDING PAGE
    if current_schema == "public" and not tenant_schema:

        print("📌 Showing PUBLIC landing page")            
        
        # ========== PUBLIC LANDING PAGE ==========
        print("📌 Showing PUBLIC landing page")
        
        # Get platform metrics - SAFE VERSION without UserProfile
        from tenants.models import School
        from django.core.cache import cache
        from django_tenants.utils import tenant_context
        from django.db import connection as db_connection
        
        metrics = cache.get('platform_metrics')
        if not metrics:
            all_schools = School.objects.filter(is_active=True)
            total_schools = all_schools.count()
            
            total_teachers = 0
            total_students = 0
            total_resources = 0
            total_views = 0
            
            for school_tenant in all_schools:
                try:
                    with tenant_context(school_tenant):
                        # Use direct SQL instead of UserProfile to avoid errors
                        with db_connection.cursor() as cursor:
                            # Count teachers (staff users)
                            cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_staff = true AND is_superuser = false AND is_active = true")
                            result = cursor.fetchone()
                            total_teachers += result[0] if result else 0
                            
                            # Count students (non-staff users)
                            cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_staff = false AND is_active = true")
                            result = cursor.fetchone()
                            total_students += result[0] if result else 0
                        
                        # Count resources
                        total_resources += Resource.objects.count()
                        
                        # Count views
                        total_views += Resource.objects.aggregate(Sum('views'))['views__sum'] or 0
                except Exception as e:
                    logger.error(f"Error processing tenant {school_tenant.schema_name}: {e}")
            
            metrics = {
                'total_schools': total_schools,
                'total_teachers': total_teachers,
                'total_students': total_students,
                'total_resources': total_resources,
                'total_views': total_views,
            }
            cache.set('platform_metrics', metrics, 3600)
        
        # Get public announcements
        announcements = Announcement.objects.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
            target_audience='all'
        ).order_by('-is_featured', '-created_at')[:5]
        
        # Return landing page template
        return render(request, "digitallibrary/landing_page.html", {
            "is_public_schema": True,
            "metrics": metrics,
            "school": None,
            "school_name": "ShuleHub",
            "latest": [],
            "announcements": announcements,
            "total_resources": metrics['total_resources'],
            "total_teachers": metrics['total_teachers'],
            "user_role": "Guest",
            "unread_count": 0,
            "notification_unread_count": 0,
            "children": [],
        })
    
    # ========== TENANT DASHBOARD ==========
    print(f"Current schema after checks: {current_schema}")
    print(f"Tenant schema: {tenant_schema}")
    print("📌 Showing TENANT dashboard")
    
    # Get school setting
    school = SchoolSetting.objects.first()
    school_name = school.name if school else "ShuleHub"
    
    if school:
        print(f"✅ School: {school_name}")
    else:
        print(f"⚠️ No SchoolSetting found in {current_schema}")
    
    # Get latest resources (public)
    latest = list(Resource.objects.all().order_by("-created_at")[:8])
    total_resources = Resource.objects.count()
    
    # Get teacher count using SQL (no UserProfile)
    total_teachers = 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_staff = true AND is_superuser = false AND is_active = true")
            result = cursor.fetchone()
            total_teachers = result[0] if result else 0
    except Exception as e:
        print(f"Error counting teachers: {e}")
    
    print(f"📚 Resources: {total_resources}, Teachers: {total_teachers}")
    
    # Get announcements (public)
    announcements = list(Announcement.objects.filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).order_by("-is_featured", "-created_at")[:5])
    
    print(f"📢 Announcements: {len(announcements)}")
    
    # User role - only show if authenticated
    user_role = "Guest"
    children = []
    unread_count = 0
    notification_unread_count = 0
    show_admin_panel = False
    
    if request.user.is_authenticated:
        try:
            # Try to get role from profile if it exists
            if hasattr(request.user, 'profile') and request.user.profile:
                user_role = request.user.profile.role
                print(f"👤 User role from profile: {user_role}")
            else:
                # Create profile for user if missing
                from .models import UserProfile
                profile, created = UserProfile.objects.get_or_create(
                    user=request.user,
                    defaults={'role': 'admin' if request.user.is_staff else 'user', 'is_approved': True}
                )
                user_role = profile.role
                print(f"👤 Created new profile for user {request.user.username}, role: {user_role}")
            
            print(f"👤 User role: {user_role}")
            show_admin_panel = user_role in ['admin', 'principal', 'teacher', 'bursar', 'secretary']
            
            if user_role == 'parent':
                phone = None
                if hasattr(request.user, 'profile') and request.user.profile:
                    phone = request.user.profile.phone_number
                if phone:
                    children = Student.objects.filter(
                        Q(parent_phone=phone) | Q(parent_alternative_phone=phone),
                        is_active=True
                    )
                    print(f"👶 Children: {children.count()}")
            
            # Get unread counts for authenticated users (safe try-except)
            try:
                from .models import AnnouncementRead, Notification
                unread_count = AnnouncementRead.objects.filter(user=request.user, read=False).count()
                notification_unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
            except Exception as e:
                print(f"Error getting unread counts: {e}")
                unread_count = 0
                notification_unread_count = 0
                
        except Exception as e:
            print(f"Error getting user data: {e}")
            import traceback
            traceback.print_exc()
    
    context = {
        "is_public_schema": False,
        "school": school,
        "school_name": school_name,
        "latest": latest,
        "announcements": announcements,
        "total_resources": total_resources,
        "total_teachers": total_teachers,
        "user_role": user_role.capitalize() if user_role != "Guest" else "Guest",
        "unread_count": unread_count,
        "notification_unread_count": notification_unread_count,
        "children": children,
        "show_admin_panel": show_admin_panel,
        "is_authenticated": request.user.is_authenticated,
    }
    
    print(f"\n✅ Returning tenant dashboard with {len(announcements)} announcements")
    return render(request, "digitallibrary/home.html", context)
def logout_view(request, tenant_schema=None, *args, **kwargs):
    """Custom tenant-safe logout view with Super Admin redirect support"""

    from django.contrib.auth import logout
    from django.shortcuts import redirect
    from django.contrib import messages
    from django.db import connection
    from django.utils.http import url_has_allowed_host_and_scheme

    # ------------------------------------------------------------
    # 1. Resolve tenant schema safely
    # ------------------------------------------------------------
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "public"
    )

    tenant_schema = str(tenant_schema).strip()

    if tenant_schema in ["", "None", "none", "null", "undefined"]:
        tenant_schema = "public"

    # Optional redirect target, useful for Super Admin logout
    requested_next = request.POST.get("next") or request.GET.get("next")

    # ------------------------------------------------------------
    # 2. Log activity before logout
    # ------------------------------------------------------------
    try:
        if request.user.is_authenticated:
            ActivityLog.objects.create(
                user=request.user,
                action="logout",
                description=f"User logged out from tenant {tenant_schema}",
            )
    except Exception:
        pass

    # ------------------------------------------------------------
    # 3. Logout
    # ------------------------------------------------------------
    logout(request)

    messages.success(request, "You have been successfully logged out.")

    # ------------------------------------------------------------
    # 4. Respect safe next redirect if provided
    # ------------------------------------------------------------
    if requested_next and url_has_allowed_host_and_scheme(
        requested_next,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(requested_next)

    # ------------------------------------------------------------
    # 5. Super Admin / public logout
    # ------------------------------------------------------------
    if tenant_schema in ["public", "super-admin"]:
        return redirect("/admin/login/?next=/tenants/super-admin/")

    # ------------------------------------------------------------
    # 6. Normal tenant logout
    # ------------------------------------------------------------
    return redirect(f"/tenant/{tenant_schema}/app/login/")
# digitallibrary/views.py

from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q, Count
from .models import Resource, Subject, Category, SchoolSetting
from .forms import ResourceFilterForm

def library_list(request, tenant_schema=None):
    """Display list of library resources with filtering"""
    
    # Start with all resources (not just active - depends on your model)
    # If you have an is_active field, uncomment the filter below
    resources = Resource.objects.all().order_by('-created_at')
    # resources = Resource.objects.filter(is_active=True).order_by('-created_at')
    
    # Get filter parameters from request
    subject_id = request.GET.get('subject')
    grade = request.GET.get('grade')
    year = request.GET.get('year')
    search_query = request.GET.get('q')
    category_id = request.GET.get('category')
    resource_type = request.GET.get('type')
    paper_type = request.GET.get('paper_type')
    
    # Apply filters
    if subject_id and subject_id.isdigit():
        resources = resources.filter(subject_id=int(subject_id))
    
    if grade and grade.strip():
        resources = resources.filter(grade=grade)
    
    if year and year.strip() and year != 'None':
        resources = resources.filter(year=year)
    
    if category_id and category_id.isdigit():
        resources = resources.filter(category_id=int(category_id))
    
    if resource_type and resource_type.strip():
        resources = resources.filter(resource_type=resource_type)
    
    if paper_type and paper_type.strip():
        resources = resources.filter(paper_type=paper_type)
    
    if search_query and search_query.strip():
        resources = resources.filter(
            Q(title__icontains=search_query) |
            Q(author__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(subject__name__icontains=search_query) |
            Q(year__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(resources, 24)
    page = request.GET.get('page', 1)
    resources_page = paginator.get_page(page)
    
    # Get filter options for dropdowns
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    # Get unique grades (clean and deduplicated)
    grades_raw = Resource.objects.exclude(grade__isnull=True).exclude(grade='').values_list('grade', flat=True).distinct()
    
    # Clean and standardize grades
    grade_mapping = {
        'form1': 'Form 1', 'form 1': 'Form 1', 'Form1': 'Form 1',
        'form2': 'Form 2', 'form 2': 'Form 2', 'Form2': 'Form 2',
        'form3': 'Form 3', 'form 3': 'Form 3', 'Form3': 'Form 3',
        'form4': 'Form 4', 'form 4': 'Form 4', 'Form4': 'Form 4',
        'grade1': 'Grade 1', 'grade 1': 'Grade 1', 'Grade1': 'Grade 1',
        'grade2': 'Grade 2', 'grade 2': 'Grade 2', 'Grade2': 'Grade 2',
        'grade3': 'Grade 3', 'grade 3': 'Grade 3', 'Grade3': 'Grade 3',
        'grade4': 'Grade 4', 'grade 4': 'Grade 4', 'Grade4': 'Grade 4',
        'grade5': 'Grade 5', 'grade 5': 'Grade 5', 'Grade5': 'Grade 5',
        'grade6': 'Grade 6', 'grade 6': 'Grade 6', 'Grade6': 'Grade 6',
        'grade7': 'Grade 7', 'grade 7': 'Grade 7', 'Grade7': 'Grade 7',
        'grade8': 'Grade 8', 'grade 8': 'Grade 8', 'Grade8': 'Grade 8',
        'general': 'General', 'General': 'General', 'GENERAL': 'General',
        'all': 'General', 'All': 'General',
    }
    
    cleaned_grades = set()
    for g in grades_raw:
        grade_lower = str(g).lower().strip()
        if grade_lower in grade_mapping:
            cleaned_grades.add(grade_mapping[grade_lower])
        elif g:
            cleaned_grades.add(str(g).strip())
    
    # Sort grades: Form/Grade 1-4/8 first, then alphabetical
    def grade_sort_key(g):
        order = {
            'Form 1': 1, 'Grade 1': 1,
            'Form 2': 2, 'Grade 2': 2,
            'Form 3': 3, 'Grade 3': 3,
            'Form 4': 4, 'Grade 4': 4,
            'Grade 5': 5, 'Grade 6': 6, 'Grade 7': 7, 'Grade 8': 8,
            'General': 99
        }
        return order.get(g, 100)
    
    grades = sorted(list(cleaned_grades), key=grade_sort_key)
    
    # Get unique years (deduplicated and sorted descending)
    years_raw = Resource.objects.exclude(year__isnull=True).exclude(year='').exclude(year='N/A').values_list('year', flat=True).distinct()
    
    valid_years = set()
    for y in years_raw:
        try:
            year_int = int(y)
            if 2000 <= year_int <= 2030:
                valid_years.add(year_int)
        except (ValueError, TypeError):
            pass
    
    years = sorted(list(valid_years), reverse=True)
    
    # Get unique paper types
    paper_types = Resource.objects.exclude(paper_type__isnull=True).exclude(paper_type='').values_list('paper_type', flat=True).distinct().order_by('paper_type')
    
    # Get resource types
    resource_types = Resource.objects.exclude(resource_type__isnull=True).exclude(resource_type='').values_list('resource_type', flat=True).distinct()
    
    # Get selected subject name for display
    selected_subject_name = None
    if subject_id and subject_id.isdigit():
        try:
            selected_subject = Subject.objects.get(id=int(subject_id))
            selected_subject_name = selected_subject.name
        except Subject.DoesNotExist:
            pass
    
    school = SchoolSetting.objects.first()
    
    context = {
        'resources': resources_page,
        'subjects': subjects,
        'categories': categories,
        'grades': grades,
        'years': years,
        'paper_types': paper_types,
        'resource_types': resource_types,
        'selected_subject': subject_id,
        'selected_grade': grade,
        'selected_year': year,
        'selected_category': category_id,
        'selected_type': resource_type,
        'selected_paper_type': paper_type,
        'selected_subject_name': selected_subject_name,
        'search_query': search_query,
        'total_count': resources.count(),
        'school': school,
    }
    
    return render(request, 'digitallibrary/library_list.html', context)


@login_required
def resource_detail(request, tenant_schema=None, pk=None):
    """Display resource details - tenant-safe version"""
    from django.db import connection
    from django.shortcuts import get_object_or_404, render

    resource = get_object_or_404(Resource, pk=pk)

    # Resolve tenant schema safely
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"

    # Increment view count safely
    try:
        if hasattr(resource, "increment_views"):
            resource.increment_views()
        else:
            resource.views = (resource.views or 0) + 1
            resource.save(update_fields=["views"])
    except Exception:
        pass

    school = SchoolSetting.objects.first()

    return render(request, "digitallibrary/resource_detail.html", {
        "resource": resource,
        "r": resource,
        "school": school,

        # Tenant-safe context
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "tenant_library_url": f"{tenant_base_url}/library/",
        "tenant_resource_detail_url": f"{tenant_base_url}/resource/{resource.pk}/",
    })
# ========== RESOURCE UPLOAD AND MANAGEMENT VIEWS ==========

def can_upload(user):
    """Check if user can upload resources"""
    try:
        profile = user.profile
        return profile.role in ["admin", "teacher", "principal"]
    except Exception:
        return False


@login_required
def upload_resource(request, tenant_schema=None):
    """Upload a new resource"""
    from django.db import connection
    from .forms import ResourceForm
    from .models import Subject, Category, SchoolSetting
    
    if not can_upload(request.user):
        messages.error(request, "Access Denied: Only teachers and administrators can upload resources.")
        return redirect("digitallibrary:library_list")

    if connection.schema_name == 'public':
        return redirect("digitallibrary:home")
    
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
                    description=f"Uploaded resource: {resource.title}",
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
def my_uploads(request, tenant_schema=None):
    """Display resources uploaded by the logged-in user."""

    from datetime import timedelta

    from django.contrib import messages
    from django.core.paginator import Paginator
    from django.db import connection
    from django.db.models import Sum
    from django.shortcuts import redirect, render
    from django.utils import timezone
    from django_tenants.utils import schema_context

    from .models import Resource, SchoolSetting

    # ------------------------------------------------------------
    # Detect tenant schema
    # ------------------------------------------------------------
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(
            getattr(request, "tenant", None),
            "schema_name",
            None,
        )
        or getattr(connection, "schema_name", None)
    )

    # Fallback for URLs such as:
    # /tenant/nyaneje/app/my-uploads/
    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "The school tenant could not be identified.",
        )
        return redirect("/")

    tenant_base_url = f"/tenant/{schema_name}/app"

    # ------------------------------------------------------------
    # Run school-specific queries in the tenant schema
    # ------------------------------------------------------------
    with schema_context(schema_name):

        if not can_upload(request.user):
            messages.error(request, "Access Denied.")

            return redirect(
                f"{tenant_base_url}/"
            )

        school = SchoolSetting.objects.first()

        all_resources = Resource.objects.filter(
            uploaded_by=request.user
        ).order_by("-created_at")

        total_uploads = all_resources.count()

        seven_days_ago = timezone.now() - timedelta(days=7)

        recent_uploads = all_resources.filter(
            created_at__gte=seven_days_ago
        ).count()

        total_views = (
            all_resources.aggregate(
                total=Sum("views")
            )["total"]
            or 0
        )

        paginator = Paginator(all_resources, 12)

        page_number = request.GET.get("page", 1)

        resources = paginator.get_page(page_number)

        profile = getattr(request.user, "profile", None)

        user_role = getattr(profile, "role", None)

        context = {
            "resources": resources,
            "school": school,
            "total_uploads": total_uploads,
            "recent_uploads": recent_uploads,
            "total_views": total_views,
            "is_teacher": user_role == "teacher",

            # Tenant-safe context
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,

            # Useful URLs
            "tenant_dashboard_url": (
                f"{tenant_base_url}/dashboard/"
            ),
            "tenant_home_url": (
                f"{tenant_base_url}/"
            ),
            "tenant_my_uploads_url": (
                f"{tenant_base_url}/my-uploads/"
            ),
        }

        return render(
            request,
            "digitallibrary/my_uploads.html",
            context,
        )

@login_required
def edit_my_resource(request, tenant_schema=None, pk=None):
    """Edit a resource uploaded by the current user within the active tenant."""
    from django.contrib import messages
    from django.db import connection
    from django.shortcuts import get_object_or_404, redirect, render
    from django_tenants.utils import schema_context

    from .forms import ResourceForm
    from .models import (
        Resource,
        Subject,
        Category,
        SchoolSetting,
        ActivityLog,
    )

    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(
            getattr(request, "tenant", None),
            "schema_name",
            None,
        )
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "The school tenant could not be identified.",
        )
        return redirect("/")

    with schema_context(schema_name):
        resource = get_object_or_404(
            Resource,
            pk=pk,
        )

        profile = getattr(request.user, "profile", None)
        user_role = getattr(profile, "role", None)
        is_admin = user_role == "admin"

        if resource.uploaded_by_id != request.user.id and not is_admin:
            messages.error(
                request,
                "You don't have permission to edit this resource.",
            )
            return redirect(
                "digitallibrary:library_list",
                tenant_schema=schema_name,
            )

        school = SchoolSetting.objects.first()

        if request.method == "POST":
            form = ResourceForm(
                request.POST,
                request.FILES,
                instance=resource,
            )

            if form.is_valid():
                updated_resource = form.save()

                messages.success(
                    request,
                    "Resource updated successfully!",
                )

                try:
                    ActivityLog.objects.create(
                        user=request.user,
                        action="edit",
                        description=(
                            f"Edited resource: "
                            f"{updated_resource.title}"
                        ),
                    )
                except Exception:
                    pass

                if is_admin:
                    return redirect(
                        "digitallibrary:library_admin_resources",
                        tenant_schema=schema_name,
                    )

                return redirect(
                    "digitallibrary:my_uploads",
                    tenant_schema=schema_name,
                )
        else:
            form = ResourceForm(instance=resource)

        subjects = Subject.objects.all().order_by("name")
        categories = Category.objects.all().order_by("name")
        year_choices = get_year_choices()

        context = {
            "form": form,
            "resource": resource,
            "subjects": subjects,
            "categories": categories,
            "year_choices": year_choices,
            "school": school,
            "is_teacher": user_role == "teacher",
            "is_admin": is_admin,
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_base_url": f"/tenant/{schema_name}/app",
        }

        return render(
            request,
            "digitallibrary/edit_resource.html",
            context,
        )


@login_required
@require_POST
def delete_my_resource(request, tenant_schema=None, pk=None):
    """Delete a resource uploaded by the current user within the active tenant."""
    from django.contrib import messages
    from django.db import connection
    from django.shortcuts import get_object_or_404, redirect
    from django_tenants.utils import schema_context

    from .models import Resource, ActivityLog

    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(
            getattr(request, "tenant", None),
            "schema_name",
            None,
        )
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "The school tenant could not be identified.",
        )
        return redirect("/")

    with schema_context(schema_name):
        resource = get_object_or_404(
            Resource,
            pk=pk,
        )

        profile = getattr(request.user, "profile", None)
        user_role = getattr(profile, "role", None)
        is_admin = user_role == "admin"

        if resource.uploaded_by_id != request.user.id and not is_admin:
            messages.error(
                request,
                "You don't have permission to delete this resource.",
            )
            return redirect(
                "digitallibrary:library_list",
                tenant_schema=schema_name,
            )

        title = resource.title
        resource.delete()

        try:
            ActivityLog.objects.create(
                user=request.user,
                action="delete",
                description=f"Deleted resource: {title}",
            )
        except Exception:
            pass

        messages.success(
            request,
            f"Resource '{title}' deleted successfully.",
        )

        if is_admin:
            return redirect(
                "digitallibrary:library_admin_resources",
                tenant_schema=schema_name,
            )

        return redirect(
            "digitallibrary:my_uploads",
            tenant_schema=schema_name,
        )


@login_required
def resource_detail(request, tenant_schema=None, pk=None):
    """Display resource details - tenant-safe version"""
    from django.db import connection
    from django.shortcuts import get_object_or_404, render

    # Resolve tenant schema safely
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"

    resource = get_object_or_404(Resource, pk=pk)

    # Increment view count safely
    try:
        if hasattr(resource, "increment_views"):
            resource.increment_views()
        else:
            resource.views = (resource.views or 0) + 1
            resource.save(update_fields=["views"])
    except Exception:
        pass

    school = SchoolSetting.objects.first()

    return render(request, "digitallibrary/resource_detail.html", {
        "resource": resource,
        "r": resource,
        "school": school,

        # Tenant-safe context
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "tenant_library_url": f"{tenant_base_url}/library/",
        "tenant_resource_detail_url": f"{tenant_base_url}/resource/{resource.pk}/",
    })

def library_list(request, tenant_schema=None):
    """Display list of library resources"""
    from .models import Resource, Subject, Category, SchoolSetting
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    resources = Resource.objects.all().order_by('-created_at')
    
    subject_id = request.GET.get('subject')
    grade = request.GET.get('grade')
    year = request.GET.get('year')
    q = request.GET.get('q')
    category_id = request.GET.get('category')
    resource_type = request.GET.get('type')
    
    if subject_id:
        resources = resources.filter(subject_id=subject_id)
    if grade:
        resources = resources.filter(grade=grade)
    if year:
        resources = resources.filter(year=year)
    if category_id:
        resources = resources.filter(category_id=category_id)
    if resource_type:
        resources = resources.filter(resource_type=resource_type)
    if q:
        resources = resources.filter(
            Q(title__icontains=q) |
            Q(author__icontains=q) |
            Q(description__icontains=q) |
            Q(subject__name__icontains=q)
        )
    
    paginator = Paginator(resources, 24)
    page = request.GET.get('page', 1)
    resources_page = paginator.get_page(page)
    
    subjects = Subject.objects.all().order_by('name')
    categories = Category.objects.all().order_by('name')
    school = SchoolSetting.objects.first()
    grades = Resource.objects.values_list('grade', flat=True).distinct().exclude(grade='').exclude(grade=None)
    years = Resource.objects.values_list('year', flat=True).distinct().exclude(year='').exclude(year=None).order_by('-year')
    
    context = {
        'resources': resources_page,
        'subjects': subjects,
        'categories': categories,
        'grades': grades,
        'years': years,
        'selected_subject': subject_id,
        'selected_grade': grade,
        'selected_year': year,
        'selected_category': category_id,
        'selected_type': resource_type,
        'search_query': q,
        'school': school,
    }
    return render(request, 'digitallibrary/library_list.html', context)


# ========== AI SEARCH VIEW ==========

def ai_search_page(request):
    """AI-powered semantic search page"""
    from django.db import connection
    from .models import SchoolSetting
    
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        # results = search_ai(query, k=8)  # Uncomment when AI is available
        pass
    school = SchoolSetting.objects.first() if connection.schema_name != 'public' else None

    return render(request, "digitallibrary/ai_search.html", {
        "q": query,
        "results": results,
        "school": school,
    })


# ========== PRINTING PORTAL VIEWS ==========

@login_required
@tenant_app_view
def printing_portal(request):
    """Printing portal for teachers"""
    from .models import PrintJob, SchoolSetting, UserProfile
    
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
    """Mark print job as downloaded"""
    from .models import PrintJob, ActivityLog, Notification
    
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
    except Exception as e:
        print(f"Error creating notification: {e}")
    messages.success(request, f"Job '{job.file.name}' marked as downloaded.")
    return redirect("digitallibrary:printing_portal")


@login_required
def mark_as_completed(request, job_id):
    """Mark print job as completed"""
    from .models import PrintJob, ActivityLog, Notification
    
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
    except Exception as e:
        print(f"Error creating notification: {e}")
    messages.success(request, f"Job '{job.file.name}' marked as completed.")
    return redirect("digitallibrary:printing_portal")


@login_required
def download_print_file(request, job_id):
    """Download print job file"""
    from .models import PrintJob, ActivityLog, Notification
    import mimetypes
    import os
    
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
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            response['Content-Length'] = os.path.getsize(file_path)
            return response
    except Exception as e:
        raise Http404(f"Error reading file: {e}")


@login_required
def print_job_detail(request, job_id):
    """View print job details"""
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


# ========== LIBRARY ADMIN VIEWS ==========

@login_required
def library_admin_dashboard(request, tenant_schema=None):
    """Library admin dashboard"""
    from .models import Resource, Announcement, SchoolSetting
    from django.db import connection

    # Resolve safe tenant schema
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_dashboard_url = f"/tenant/{tenant_schema}/app/dashboard/"

    # Prevent public schema access
    if getattr(connection, "schema_name", None) == "public":
        messages.error(request, "Library Admin is only available inside a school tenant.")
        return redirect(tenant_dashboard_url)

    # Safe role check
    try:
        user_role = request.user.profile.role
    except Exception:
        user_role = None

    if user_role not in ["admin", "principal"]:
        messages.error(request, "Access Denied. Library Admin access only.")
        return redirect(tenant_dashboard_url)

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

        # Important tenant context
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": f"/tenant/{tenant_schema}/app",
        "tenant_dashboard_url": tenant_dashboard_url,
    }

    return render(request, "digitallibrary/library_admin/dashboard.html", context)

@login_required
def library_admin_resources(request, tenant_schema=None):
    """Library admin resource management"""
    from .models import Resource, SchoolSetting
    from django.core.paginator import Paginator
    from django.db.models import Q

    tenant_schema = tenant_schema or getattr(request, "tenant_schema", None) or "nyaneje"
    tenant_dashboard_url = f"/tenant/{tenant_schema}/app/dashboard/"

    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect(tenant_dashboard_url)

    resources = Resource.objects.all().order_by("-created_at")
    q = request.GET.get("q", "")

    if q:
        resources = resources.filter(
            Q(title__icontains=q)
            | Q(author__icontains=q)
            | Q(grade__icontains=q)
            | Q(year__icontains=q)
            | Q(subject__name__icontains=q)
        )

    paginator = Paginator(resources, 20)
    page = request.GET.get("page", 1)
    resources = paginator.get_page(page)
    school = SchoolSetting.objects.first()

    return render(request, "digitallibrary/library_admin/resources.html", {
        "resources": resources,
        "q": q,
        "school": school,
        "tenant_schema": tenant_schema,
    })


@login_required
def library_admin_resource_edit(request, pk=None, tenant_schema=None):
    """Edit or add resource in admin panel"""
    from .forms import ResourceForm
    from .models import Resource, Subject, SchoolSetting
    import datetime
    import os

    tenant_schema = tenant_schema or getattr(request, "tenant_schema", None) or "nyaneje"
    tenant_dashboard_url = f"/tenant/{tenant_schema}/app/dashboard/"
    tenant_admin_resources_url = f"/tenant/{tenant_schema}/app/admin-library/resources/"

    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied. Admin access required.")
        return redirect(tenant_dashboard_url)

    if pk:
        resource = get_object_or_404(Resource, id=pk)

        if request.method == "POST":
            form = ResourceForm(request.POST, request.FILES, instance=resource)

            if form.is_valid():
                form.save()
                messages.success(request, "Resource updated successfully!")
                return redirect(tenant_admin_resources_url)

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
            except Exception:
                pass
    else:
        resource = None

        if request.method == "POST":
            form = ResourceForm(request.POST, request.FILES)

            if form.is_valid():
                resource = form.save(commit=False)
                resource.uploaded_by = request.user
                resource.save()
                messages.success(request, "Resource created successfully!")
                return redirect(tenant_admin_resources_url)

            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        else:
            form = ResourceForm()

        current_file_name = None
        current_file_size = None

    current_year = datetime.datetime.now().year
    years = list(range(current_year + 5, 1949, -1))
    subjects = Subject.objects.all().order_by("name")
    school = SchoolSetting.objects.first()

    context = {
        "form": form,
        "resource": resource,
        "years": years,
        "subjects": subjects,
        "title": "Edit Resource" if pk else "Add Resource",
        "school": school,
        "current_file_name": current_file_name,
        "current_file_size": current_file_size,
        "tenant_schema": tenant_schema,
    }

    return render(request, "digitallibrary/library_admin/resource_form.html", context)


@login_required
def library_admin_resource_delete(request, pk, tenant_schema=None):
    """Delete resource from admin panel"""
    from .models import Resource, SchoolSetting

    tenant_schema = tenant_schema or getattr(request, "tenant_schema", None) or "nyaneje"
    tenant_dashboard_url = f"/tenant/{tenant_schema}/app/dashboard/"
    tenant_admin_resources_url = f"/tenant/{tenant_schema}/app/admin-library/resources/"

    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect(tenant_dashboard_url)

    resource = get_object_or_404(Resource, pk=pk)
    school = SchoolSetting.objects.first()

    if request.method == "POST":
        resource.delete()
        messages.success(request, "Resource deleted successfully!")
        return redirect(tenant_admin_resources_url)

    return render(request, "digitallibrary/library_admin/resource_confirm_delete.html", {
        "resource": resource,
        "school": school,
        "tenant_schema": tenant_schema,
    })


# ========== LIBRARY ADMIN ANNOUNCEMENTS VIEWS ==========

from django.db import connection


@login_required
def library_admin_announcements(request, tenant_schema=None):
    """Library admin announcements management"""
    from .models import Announcement, SchoolSetting
    from .forms import AnnouncementFilterForm
    from django.db.models import Q
    from django.utils import timezone

    tenant_schema = tenant_schema or getattr(request, "tenant_schema", None) or "nyaneje"
    tenant_dashboard_url = f"/tenant/{tenant_schema}/app/dashboard/"

    if connection.schema_name == "public":
        messages.error(request, "This feature is only available for school tenants.")
        return redirect(tenant_dashboard_url)

    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect(tenant_dashboard_url)

    filter_form = AnnouncementFilterForm(request.GET)
    announcements = Announcement.objects.all().order_by("-created_at")

    if filter_form.is_valid():
        audience = filter_form.cleaned_data.get("audience")
        status = filter_form.cleaned_data.get("status")
        search = filter_form.cleaned_data.get("search")
        date_from = filter_form.cleaned_data.get("date_from")
        date_to = filter_form.cleaned_data.get("date_to")

        if audience:
            announcements = announcements.filter(target_audience=audience)

        if status == "active":
            announcements = announcements.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
            )
        elif status == "expired":
            announcements = announcements.filter(expires_at__lt=timezone.now())
        elif status == "featured":
            announcements = announcements.filter(is_featured=True)

        if search:
            announcements = announcements.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )

        if date_from:
            announcements = announcements.filter(created_at__date__gte=date_from)

        if date_to:
            announcements = announcements.filter(created_at__date__lte=date_to)

    school = SchoolSetting.objects.first()

    return render(request, "digitallibrary/library_admin/announcements.html", {
        "announcements": announcements,
        "filter_form": filter_form,
        "school": school,
        "tenant_schema": tenant_schema,
    })


@login_required
def library_admin_announcement_add(request, tenant_schema=None):
    """Add new announcement from admin panel"""
    from .models import SchoolSetting
    from .forms import AnnouncementForm

    tenant_schema = tenant_schema or getattr(request, "tenant_schema", None) or "nyaneje"
    tenant_dashboard_url = f"/tenant/{tenant_schema}/app/dashboard/"
    tenant_announcements_url = f"/tenant/{tenant_schema}/app/admin-library/announcements/"

    if connection.schema_name == "public":
        messages.error(request, "This feature is only available for school tenants.")
        return redirect(tenant_dashboard_url)

    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect(tenant_dashboard_url)

    school = SchoolSetting.objects.first()

    if request.method == "POST":
        form = AnnouncementForm(request.POST, request.FILES)

        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.author = request.user
            announcement.save()
            messages.success(request, "Announcement created successfully!")
            return redirect(tenant_announcements_url)
    else:
        form = AnnouncementForm()

    return render(request, "digitallibrary/library_admin/announcement_form.html", {
        "form": form,
        "title": "Add New Announcement",
        "school": school,
        "tenant_schema": tenant_schema,
    })


@login_required
def library_admin_announcement_edit(request, pk, tenant_schema=None):
    """Edit announcement from admin panel"""
    from .models import Announcement, SchoolSetting
    from .forms import AnnouncementForm

    tenant_schema = tenant_schema or getattr(request, "tenant_schema", None) or "nyaneje"
    tenant_dashboard_url = f"/tenant/{tenant_schema}/app/dashboard/"
    tenant_announcements_url = f"/tenant/{tenant_schema}/app/admin-library/announcements/"

    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect(tenant_dashboard_url)

    announcement = get_object_or_404(Announcement, pk=pk)
    school = SchoolSetting.objects.first()

    if request.method == "POST":
        form = AnnouncementForm(request.POST, request.FILES, instance=announcement)

        if form.is_valid():
            form.save()
            messages.success(request, "Announcement updated successfully!")
            return redirect(tenant_announcements_url)
    else:
        form = AnnouncementForm(instance=announcement)

    return render(request, "digitallibrary/library_admin/announcement_form.html", {
        "form": form,
        "title": "Edit Announcement",
        "announcement": announcement,
        "school": school,
        "tenant_schema": tenant_schema,
    })


@login_required
def library_admin_announcement_delete(request, pk, tenant_schema=None):
    """Delete announcement from admin panel"""
    from .models import Announcement, SchoolSetting

    tenant_schema = tenant_schema or getattr(request, "tenant_schema", None) or "nyaneje"
    tenant_dashboard_url = f"/tenant/{tenant_schema}/app/dashboard/"
    tenant_announcements_url = f"/tenant/{tenant_schema}/app/admin-library/announcements/"

    if request.user.profile.role not in ["admin", "principal"]:
        messages.error(request, "Access Denied.")
        return redirect(tenant_dashboard_url)

    announcement = get_object_or_404(Announcement, pk=pk)
    school = SchoolSetting.objects.first()

    if request.method == "POST":
        announcement.delete()
        messages.success(request, "Announcement deleted successfully!")
        return redirect(tenant_announcements_url)

    return render(request, "digitallibrary/library_admin/announcement_confirm_delete.html", {
        "announcement": announcement,
        "school": school,
        "tenant_schema": tenant_schema,
    })

# ========== USER PROFILE AND ACTIVITY VIEWS ==========

@login_required
def user_profile(request, tenant_schema=None):
    """View user profile"""
    from .models import SchoolSetting, Resource, PrintJob, ActivityLog
    from datetime import timedelta
    
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
    """Approve teacher registration"""
    from django.contrib.auth.models import User
    
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
    """View activity logs"""
    from .models import ActivityLog, SchoolSetting
    
    if request.user.profile.role != "admin":
        messages.error(request, "Access Denied.")
        return redirect("digitallibrary:home")
    
    activities = ActivityLog.objects.all()[:100]
    school = SchoolSetting.objects.first()
    return render(request, "digitallibrary/activity_log.html", {
        "activities": activities,
        "school": school
    })


# ========== ANNOUNCEMENT VIEWS ==========

@login_required
def announcement_list(request):
    """List announcements for users"""
    from .models import Announcement, AnnouncementRead, SchoolSetting
    from django.db.models import Q
    from django.utils import timezone
    
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
    """View announcement details"""
    from .models import Announcement, AnnouncementRead, SchoolSetting
    
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
    """Create a new announcement"""
    from .models import SchoolSetting
    from .forms import AnnouncementForm
    
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
    """Edit an announcement"""
    from .models import Announcement, SchoolSetting
    from .forms import AnnouncementForm
    
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
    """Delete an announcement"""
    from .models import Announcement, SchoolSetting
    
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
    """Get announcement read statistics (AJAX)"""
    from .models import Announcement
    
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
# ========== ADMIN DASHBOARD VIEWS ==========

@login_required
def admin_dashboard(request):
    """Main admin dashboard"""
    from .models import Resource, UserProfile, PrintJob, SchoolSetting
    from django.contrib.auth.models import User
    
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
    """Dashboard statistics view"""
    from .models import Resource, PrintJob, ActivityLog, SchoolSetting
    from django.db.models import Count
    
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
    """Manage system users"""
    from .models import UserProfile, SchoolSetting
    from django.contrib.auth.models import User
    
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
    """Change user role"""
    from .models import UserProfile
    
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


# ========== NOTIFICATION VIEWS ==========

@login_required
def notification_list(request, tenant_schema=None):
    """List user notifications - tenant-safe version"""
    from .models import Notification, SchoolSetting
    from django.core.paginator import Paginator
    from django.utils import timezone
    from django.db import connection

    # Resolve tenant schema safely
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"

    # If somehow called from public schema, return empty tenant-safe page
    if getattr(connection, "schema_name", None) == "public":
        notifications_qs = Notification.objects.none()
    else:
        notifications_qs = Notification.objects.filter(
            recipient=request.user,
            is_archived=False
        ).order_by("-created_at")

        unread = notifications_qs.filter(is_read=False)
        unread.update(is_read=True, read_at=timezone.now())

    paginator = Paginator(notifications_qs, 20)
    page = request.GET.get("page", 1)
    notifications = paginator.get_page(page)

    school = SchoolSetting.objects.first()

    context = {
        "notifications": notifications,
        "school": school,

        # Tenant-safe context
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
        "tenant_notifications_url": f"{tenant_base_url}/notifications/",
        "tenant_notifications_api_url": f"{tenant_base_url}/api/notifications/",
    }

    return render(request, "digitallibrary/notifications.html", context)


def api_notifications(request, tenant_schema=None):
    """API endpoint for notifications - tenant-safe version"""
    from django.db import connection
    from django.http import JsonResponse
    from django.utils import timezone
    from datetime import timedelta
    from django.db import ProgrammingError

    # Never process notifications in public schema
    if connection.schema_name == "public":
        return JsonResponse({
            "unread_count": 0,
            "notifications": []
        })

    if not request.user.is_authenticated:
        return JsonResponse({
            "unread_count": 0,
            "notifications": []
        })

    try:
        from digitallibrary.models import Notification

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

        try:
            unread_count = Notification.get_unread_count(request.user)
        except Exception:
            unread_count = Notification.objects.filter(
                recipient=request.user,
                is_archived=False,
                is_read=False
            ).count()

        data = {
            "unread_count": unread_count,
            "notifications": [
                {
                    "id": n.id,
                    "title": n.title,
                    "message": n.message,
                    "link": n.link or "#",
                    "type": n.notification_type,
                    "is_read": n.is_read,
                    "time_ago": get_time_ago(n.created_at),
                    "created_at": n.created_at.isoformat()
                }
                for n in notifications
            ]
        }

        return JsonResponse(data)

    except ProgrammingError as e:
        print(f"Notifications table not ready: {e}")
        return JsonResponse({
            "unread_count": 0,
            "notifications": []
        })

    except Exception as e:
        print(f"Error in api_notifications: {e}")
        return JsonResponse({
            "unread_count": 0,
            "notifications": []
        })


def api_mark_notification_read(request, pk, tenant_schema=None):
    """Mark notification as read - tenant-safe version"""
    from django.db import connection
    from django.http import JsonResponse
    from django.shortcuts import get_object_or_404
    from django.db import ProgrammingError

    if connection.schema_name == "public":
        return JsonResponse({"success": True})

    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "error": "Not authenticated"
        }, status=401)

    try:
        from digitallibrary.models import Notification

        notification = get_object_or_404(
            Notification,
            pk=pk,
            recipient=request.user
        )

        notification.mark_as_read()

        return JsonResponse({"success": True})

    except ProgrammingError as e:
        print(f"Notification table not ready: {e}")
        return JsonResponse({"success": True})

    except Exception as e:
        print(f"Error marking notification read: {e}")
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)


def api_mark_all_read(request, tenant_schema=None):
    """Mark all notifications as read - tenant-safe version"""
    from django.db import connection
    from django.http import JsonResponse
    from django.utils import timezone
    from django.db import ProgrammingError

    if connection.schema_name == "public":
        return JsonResponse({"success": True})

    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "error": "Not authenticated"
        }, status=401)

    try:
        from digitallibrary.models import Notification

        Notification.objects.filter(
            recipient=request.user,
            is_archived=False,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )

        return JsonResponse({"success": True})

    except ProgrammingError as e:
        print(f"Notification table not ready: {e}")
        return JsonResponse({"success": True})

    except Exception as e:
        print(f"Error marking all read: {e}")
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)


def api_archive_notification(request, pk, tenant_schema=None):
    """Archive a notification - tenant-safe version"""
    from django.db import connection
    from django.http import JsonResponse
    from django.shortcuts import get_object_or_404
    from django.db import ProgrammingError

    if connection.schema_name == "public":
        return JsonResponse({"success": True})

    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "error": "Not authenticated"
        }, status=401)

    try:
        from digitallibrary.models import Notification

        notification = get_object_or_404(
            Notification,
            pk=pk,
            recipient=request.user
        )

        notification.is_archived = True
        notification.save()

        return JsonResponse({"success": True})

    except ProgrammingError as e:
        print(f"Notification table not ready: {e}")
        return JsonResponse({"success": True})

    except Exception as e:
        print(f"Error archiving notification: {e}")
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)
# ========== SUBJECT AND CATEGORY MANAGEMENT ==========

@login_required
def get_subjects(request):
    """Get all subjects (AJAX)"""
    from .models import Subject
    
    if request.user.profile.role not in ["admin", "principal"]:
        return JsonResponse({"error": "Unauthorized"}, status=403)
    
    subjects = Subject.objects.all().values("id", "name").order_by("name")
    return JsonResponse(list(subjects), safe=False)


@login_required
@require_POST
def add_subject(request, tenant_schema=None):
    """Add a new subject via AJAX"""
    import json
    from .models import Subject
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        subject_name = request.POST.get('name', '').strip()
        
        if not subject_name:
            return JsonResponse({'status': 'error', 'error': 'Subject name is required'}, status=400)
        
        existing = Subject.objects.filter(name__iexact=subject_name).first()
        if existing:
            return JsonResponse({
                'status': 'success',
                'id': existing.id,
                'name': existing.name,
                'message': 'Subject already exists'
            })
        
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
    """Delete a subject"""
    from .models import Subject
    
    if request.user.profile.role != "admin":
        return JsonResponse({"error": "Unauthorized"}, status=403)
    
    try:
        subject = get_object_or_404(Subject, pk=pk)
        if subject.resources.exists():
            return JsonResponse({
                "error": "Cannot delete subject that is in use", 
                "resources_count": subject.resources.count()
            }, status=400)
        subject.delete()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def get_categories(request):
    """Get all categories (AJAX)"""
    from .models import Category
    
    if request.user.profile.role not in ["admin", "principal"]:
        return JsonResponse({"error": "Unauthorized"}, status=403)
    
    categories = Category.objects.all().values("id", "name").order_by("name")
    return JsonResponse(list(categories), safe=False)


# ========== INCREMENT VIEW COUNT ==========

@login_required
def increment_resource_view(request, pk):
    """Increment resource view count via AJAX"""
    from .models import Resource
    
    resource = get_object_or_404(Resource, pk=pk)
    resource.increment_views()
    return JsonResponse({"success": True, "views": resource.views})
# ========== PUBLIC METRICS API ==========

from rest_framework.decorators import api_view
from rest_framework.response import Response

def test_metrics(request):
    """Test metrics API endpoint - Safe version"""
    from django.http import JsonResponse
    from django.db import connection
    
    try:
        with connection.cursor() as cursor:
            # Get schools count
            cursor.execute("SELECT COUNT(*) FROM tenants_school WHERE is_active = true")
            schools = cursor.fetchone()[0] or 0
            
            # Get teachers count
            cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_staff = true AND is_superuser = false AND is_active = true")
            teachers = cursor.fetchone()[0] or 0
            
            # Get students count
            cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_staff = false AND is_active = true")
            students = cursor.fetchone()[0] or 0
            
            return JsonResponse({
                'success': True,
                'schools': schools,
                'teachers': teachers,
                'students': students,
                'message': 'Metrics retrieved successfully'
            })
    except Exception as e:
        print(f"Error in test_metrics: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'schools': 0,
            'teachers': 0,
            'students': 0
        }, status=500)


# ========== PAPER LIBRARY VIEWS ==========

@login_required
def paper_library(request):
    """Browse papers organized by PaperSet"""
    from .models import PaperSet, Subject, SchoolSetting
    from .forms import PaperSetFilterForm
    from django.core.paginator import Paginator
    from django.db.models import Q
    
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
    school = SchoolSetting.objects.first()
    
    context = {
        'papers': papers_page,
        'filter_form': form,
        'total_papers': papers.count(),
        'total_resources': PaperResource.objects.count(),
        'school': school,
    }
    return render(request, 'digitallibrary/paper_library.html', context)


@login_required
def paper_detail(request, pk):
    """View a single paper set with all its resources"""
    from .models import PaperSet, SchoolSetting
    
    paper = get_object_or_404(PaperSet.objects.prefetch_related('resources'), pk=pk)
    paper.view_count += 1
    paper.save(update_fields=['view_count'])
    
    resources_by_kind = {kind: None for kind, _ in PaperResource.KIND_CHOICES}
    for resource in paper.resources.all():
        resources_by_kind[resource.kind] = resource
    
    school = SchoolSetting.objects.first()
    
    context = {
        'paper': paper,
        'resources_by_kind': resources_by_kind,
        'school': school,
    }
    return render(request, 'digitallibrary/paper_detail.html', context)


@login_required
def download_paper_resource(request, resource_id):
    """Download a paper resource with tracking"""
    from .models import PaperResource, ActivityLog, SchoolSetting
    import os
    from django.http import HttpResponse
    
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
    from .forms import PaperResourceForm
    from .models import SchoolSetting
    
    if not can_upload(request.user):
        messages.error(request, "Access Denied. Only teachers and administrators can upload.")
        return redirect('digitallibrary:paper_library')
    
    school = SchoolSetting.objects.first()
    
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
        'school': school,
    }
    return render(request, 'digitallibrary/upload_paper_resource.html', context)


@staff_member_required
def create_paper_set(request):
    """Create a new paper set (admin only)"""
    from .models import Subject, PaperSet, SchoolSetting
    
    school = SchoolSetting.objects.first()
    
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
        'school': school,
        'title': 'Create Paper Set',
    }
    return render(request, 'digitallibrary/create_paper_set.html', context)


# ========== TENANT SELECTOR ==========

def tenant_selector(request):
    """Page to select which school/tenant to work with"""
    from tenants.models import School
    from .models import SchoolSetting
    
    tenants = School.objects.all()
    school = SchoolSetting.objects.first()
    
    context = {
        'tenants': tenants,
        'school': school,
        'title': 'Select School',
    }
    return render(request, 'digitallibrary/tenant_selector.html', context)


# ========== CHECK RESULT MODEL ==========

def check_result_model(request):
    """Debug view to check what Result models are available"""
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


# ========== BULK DOWNLOAD ==========

@login_required
@require_http_methods(['POST'])
def bulk_download_student_packages(request):
    """Generate ZIP file with individual student reports and fee statements"""
    from .models import Student, Exam, SchoolSetting
    from datetime import datetime
    import io
    import zipfile
    
    class_id = request.POST.get('class_id', '')
    exam_id = request.POST.get('exam_id', '')
    term = request.POST.get('term', '')
    year = request.POST.get('year', datetime.now().year)
    include_fee_statement = request.POST.get('include_fee_statement', 'on')
    include_report_card = request.POST.get('include_report_card', 'on')
    
    students_qs = Student.objects.filter(is_active=True)
    if class_id:
        students_qs = students_qs.filter(current_class_id=class_id)
    
    exam = None
    if exam_id:
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            pass
    
    school = SchoolSetting.objects.first()
    school_name = school.name if school else "School Name"
    school_logo = school.logo.path if school and school.logo else None
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for student in students_qs:
            student_folder = f"{student.admission_number}_{student.first_name}_{student.last_name}".replace(' ', '_')
            
            if include_report_card:
                report_card_pdf = generate_student_report_card(
                    student, exam, term, year, school_name, school_logo
                )
                zip_file.writestr(
                    f"{student_folder}/Report_Card_{student.admission_number}.pdf",
                    report_card_pdf
                )
            
            if include_fee_statement:
                fee_statement_pdf = generate_fee_statement(
                    student, term, year, school_name, school_logo
                )
                zip_file.writestr(
                    f"{student_folder}/Fee_Statement_{student.admission_number}.pdf",
                    fee_statement_pdf
                )
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_buffer.seek(0)
    
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="student_packages_{timestamp}.zip"'
    
    return response
# ========== PUBLIC METRICS API ==========

@api_view(['GET'])
def public_metrics(request):
    """Public API endpoint for central dashboard metrics - REAL DATA from all tenant schools"""
    from tenants.models import School
    from django_tenants.utils import tenant_context
    from django.core.cache import cache
    from django.db.models import Sum, Q
    from django.utils import timezone
    from datetime import timedelta
    from .models import UserProfile, Student, Resource, PrintJob, ActivityLog, Subject
    
    cache_key = 'central_dashboard_metrics'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return Response(cached_data)
    
    try:
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        schools = School.objects.all()
        total_schools = schools.count()
        schools_this_month = schools.filter(created_on__gte=month_start).count()
        
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
        
        for school in schools:
            try:
                with tenant_context(school):
                    teacher_count = UserProfile.objects.filter(role='teacher', is_approved=True).count()
                    total_teachers += teacher_count
                    teachers_new = UserProfile.objects.filter(
                        role='teacher',
                        created_at__gte=month_start
                    ).count()
                    teachers_this_month += teachers_new
                    
                    resources = Resource.objects.all()
                    total_resources += resources.count()
                    total_pdfs += resources.filter(resource_type='PDF').count()
                    total_views += resources.aggregate(total=Sum('views'))['total'] or 0
                    
                    downloads_today += ActivityLog.objects.filter(
                        action='download',
                        timestamp__gte=today_start
                    ).count()
                    views_today += ActivityLog.objects.filter(
                        action='resource_view',
                        timestamp__gte=today_start
                    ).count()
                    
                    for subject in Subject.objects.filter(is_active=True):
                        count = resources.filter(subject=subject).count()
                        if count > 0:
                            subject_name = subject.name
                            resources_by_subject[subject_name] = resources_by_subject.get(subject_name, 0) + count
                    
                    recent = resources.order_by('-created_at')[:5]
                    for r in recent:
                        recent_uploads.append({
                            'title': r.title,
                            'school_name': school.name,
                            'created_at': r.created_at.isoformat()
                        })
                    
                    total_print_jobs += PrintJob.objects.count()
                    prints_today += PrintJob.objects.filter(
                        created_at__gte=today_start
                    ).count()
                    
                    total_students += Student.objects.filter(is_active=True).count()
                    
                    active_users_today += ActivityLog.objects.filter(
                        timestamp__gte=today_start
                    ).values('user').distinct().count()
                    
            except Exception as e:
                print(f"Error processing tenant {school.schema_name}: {e}")
                continue
        
        recent_uploads.sort(key=lambda x: x['created_at'], reverse=True)
        recent_uploads = recent_uploads[:10]
        
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
    import re
    
    try:
        data = request.data
        
        school_name = data.get('school_name')
        admin_name = data.get('admin_name')
        email = data.get('email')
        phone = data.get('phone')
        location = data.get('location')
        teacher_count = data.get('teacher_count')
        student_count = data.get('student_count')
        
        if not all([school_name, admin_name, email, phone, location]):
            return Response({
                'success': False,
                'error': 'Please fill in all required fields: school_name, admin_name, email, phone, location'
            }, status=400)
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return Response({
                'success': False,
                'error': 'Please enter a valid email address'
            }, status=400)
        
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
    from .models import Resource, UserProfile, Student, PrintJob, Announcement, FeePayment, Exam, StudentResult
    
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
# ========== FEES MANAGEMENT VIEWS ==========

from decimal import Decimal

@login_required
def fees_dashboard(request, tenant_schema=None, *args, **kwargs):
    """Main fees dashboard with statistics - Accessible by Admin, Principal, and Bursar"""
    from .models import Student, FeeStructure, FeePayment, FeeBalance, Class, SchoolSetting
    from decimal import Decimal
    from django.db.models import Sum
    
    user_role = request.user.profile.role
    if user_role not in ['admin', 'principal', 'bursar']:
        messages.error(request, f"Access Denied. {user_role.capitalize()}s cannot access the fees dashboard.")
        return redirect('digitallibrary:home')
    
    current_year = request.GET.get('year', str(timezone.now().year))
    current_term = request.GET.get('term', '1')
    
    try:
        current_term = int(current_term)
    except ValueError:
        current_term = 1
    
    students = Student.objects.filter(is_active=True).select_related('current_class')
    total_students = students.count()
    
    fee_structures = FeeStructure.objects.filter(
        academic_year=current_year,
        term=current_term
    ).select_related('student_class')
    
    class_fee_map = {}
    for fs in fee_structures:
        if fs.student_class:
            class_fee_map[fs.student_class.id] = Decimal(str(fs.total_fees))
    
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
    
    total_paid_all = FeePayment.objects.filter(
        academic_year=current_year,
        term=current_term
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    if not isinstance(total_paid_all, Decimal):
        total_paid_all = Decimal(str(total_paid_all))
    
    total_balance_all = total_expected_all - total_paid_all
    
    balances = FeeBalance.objects.filter(
        academic_year=current_year,
        term=current_term
    ).select_related('student')
    
    paid_count = balances.filter(status='PAID').count()
    partial_count = balances.filter(status='PARTIAL').count()
    defaulting_count = balances.filter(status='DEFAULTING').count()
    overpaid_count = balances.filter(status='OVERPAID').count()
    
    if balances.count() == 0 and total_students > 0:
        defaulting_count = total_students
        paid_count = 0
        partial_count = 0
    
    if total_expected_all > 0:
        collection_percentage = float(total_paid_all / total_expected_all * 100)
    else:
        collection_percentage = 0
    
    recent_payments = FeePayment.objects.filter(
        academic_year=current_year,
        term=current_term
    ).order_by('-payment_date')[:10]
    
    defaulters = []
    for balance in balances.filter(balance__gt=0).exclude(status='OVERPAID'):
        defaulters.append({
            'student': balance.student,
            'balance': balance.balance,
            'total_expected': balance.total_expected,
            'total_paid': balance.total_paid,
            'status': balance.status
        })
    
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
    
    seen = set()
    unique_defaulters = []
    for d in defaulters:
        if d['student'].id not in seen:
            seen.add(d['student'].id)
            unique_defaulters.append(d)
    unique_defaulters.sort(key=lambda x: x['balance'], reverse=True)
    defaulters = unique_defaulters[:20]
    
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
    
    available_years = FeeStructure.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    if not available_years:
        available_years = [current_year]
    
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


@tenant_app_view
def fee_structure_list(request):
    """List all fee structures"""
    from .models import FeeStructure, SchoolSetting
    
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
    
    for fs in fee_structures:
        if fs.pk:
            current_total = fs.calculate_total()
            if fs.total_fees != current_total:
                fs.total_fees = current_total
                fs.save(update_fields=['total_fees'])
    
    available_years = FeeStructure.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    school = SchoolSetting.objects.first()
    
    context = {
        'fee_structures': fee_structures,
        'current_year': request.GET.get('year', str(timezone.now().year)),
        'current_term': request.GET.get('term', ''),
        'available_years': available_years,
        'school': school,
    }
    return render(request, 'fees/fee_structure_list.html', context)


@login_required
def get_subject_students(request, exam_id):
    """AJAX endpoint to get students for a specific subject under an exam"""
    from .models import Exam, Subject, Student
    
    exam = get_object_or_404(Exam, id=exam_id)
    subject_id = request.GET.get('subject_id')
    
    if not subject_id:
        return JsonResponse({'success': False, 'error': 'No subject selected'})
    
    subject = get_object_or_404(Subject, id=subject_id)
    
    if exam.student_class:
        students = exam.student_class.students.all()
    else:
        students = Student.objects.all()
    
    existing_results = StudentResult.objects.filter(
        exam=exam, 
        subject=subject,
        student__in=students
    ).select_related('student')
    
    results_dict = {result.student_id: result for result in existing_results}
    
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
def student_list(request, tenant_schema=None):
    """List all students"""
    from .models import Student, Class, SchoolSetting
    from .forms import StudentSearchForm
    from django.core.paginator import Paginator
    from django.db.models import Q
    
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
    school = SchoolSetting.objects.first()
    
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
        'school': school,
    }
    return render(request, 'fees/student_list.html', context)


@login_required
def student_detail(request, tenant_schema=None, pk=None, *args, **kwargs):
    """View student details with fee information - tenant-safe version"""

    from django.shortcuts import render, get_object_or_404
    from django.db import connection
    from django.db.models import Sum
    from django.utils import timezone

    from .models import (
        Student,
        FeeBalance,
        FeePayment,
        FeeStructure,
        Class,
        SchoolSetting,
    )

    # ------------------------------------------------------------
    # 1. Resolve tenant schema safely
    # ------------------------------------------------------------
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    tenant_schema = str(tenant_schema).strip()

    if tenant_schema in ["", "public", "None", "none", "null", "undefined"]:
        tenant_schema = "nyaneje"

    request.tenant_schema = tenant_schema

    if hasattr(request, "session"):
        request.session["tenant_schema"] = tenant_schema
        request.session.modified = True

    tenant_base_url = f"/tenant/{tenant_schema}/app"

    # ------------------------------------------------------------
    # 2. Get student
    # ------------------------------------------------------------
    student = get_object_or_404(Student, pk=pk)

    # ------------------------------------------------------------
    # 3. Fee filters
    # ------------------------------------------------------------
    current_year = request.GET.get("year", str(timezone.now().year))

    try:
        current_term = int(request.GET.get("term", "1"))
    except ValueError:
        current_term = 1

    # ------------------------------------------------------------
    # 4. Fee balances and payments
    # ------------------------------------------------------------
    fee_balances = FeeBalance.objects.filter(
        student=student,
        academic_year=current_year,
    ).order_by("term")

    payments = FeePayment.objects.filter(
        student=student,
    ).order_by("-payment_date")

    total_paid = payments.aggregate(
        total=Sum("amount")
    )["total"] or 0

    class_id = student.current_class.id if student.current_class else None

    total_expected = FeeStructure.objects.filter(
        academic_year=current_year,
        term=current_term,
        student_class_id=class_id,
    ).aggregate(
        total=Sum("total_fees")
    )["total"] or 0

    current_balance = total_expected - total_paid

    classes = Class.objects.all().order_by("name")

    available_years = (
        FeePayment.objects.filter(student=student)
        .values_list("academic_year", flat=True)
        .distinct()
        .order_by("-academic_year")
    )

    if not available_years:
        available_years = [current_year]

    school = SchoolSetting.objects.first()

    # ------------------------------------------------------------
    # 5. Context
    # ------------------------------------------------------------
    context = {
        "student": student,
        "fee_balances": fee_balances,
        "payments": payments,
        "total_paid": total_paid,
        "total_expected": total_expected,
        "current_balance": current_balance,
        "current_year": current_year,
        "current_term": current_term,
        "classes": classes,
        "available_years": available_years,
        "school": school,

        # Tenant-safe context
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "app_prefix": tenant_base_url,

        # Useful URLs for template buttons/links
        "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
        "tenant_student_list_url": f"{tenant_base_url}/fees/students/",
        "tenant_student_edit_url": f"{tenant_base_url}/students/{student.id}/edit/",
        "tenant_payment_record_url": f"{tenant_base_url}/fees/payments/record/?student={student.id}",
    }

    return render(request, "fees/student_detail.html", context)
# ========== FEES MANAGEMENT VIEWS (continued) ==========

@tenant_app_view
def defaulter_list(request):
    """List all students with outstanding balances"""
    from .models import FeeBalance, Class, SchoolSetting
    from django.db import models
    
    current_year = request.GET.get('year', str(timezone.now().year))
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
    school = SchoolSetting.objects.first()
    
    context = {
        'balances': balances,
        'total_due': total_due,
        'current_year': current_year,
        'current_term': current_term,
        'school': school,
    }
    return render(request, 'fees/defaulter_list.html', context)


@tenant_app_view
def collection_report(request):
    """Collection report by date range"""
    from .models import FeePayment, SchoolSetting
    from django.db import models
    
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
    
    school = SchoolSetting.objects.first()
    
    context = {
        'payments': payments,
        'total_collected': total_collected,
        'by_method': by_method,
        'start_date': start_date,
        'end_date': end_date,
        'school': school,
    }
    return render(request, 'fees/collection_report.html', context)


def fee_structure_create(request, tenant_schema=None, *args, **kwargs):
    """Create new fee structure with dynamic components"""
    from .models import FeeStructure, Class as ClassModel, FeeComponent, SchoolSetting
    from .forms import FeeStructureForm
    
    if request.method == 'POST':
        form = FeeStructureForm(request.POST)
        if form.is_valid():
            fee_structure = form.save()
            
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
    
    try:
        classes = ClassModel.objects.filter(is_active=True).order_by('name')
    except:
        classes = []
    
    school = SchoolSetting.objects.first()
    
    context = {
        'form': form,
        'title': 'Create Fee Structure',
        'is_edit': False,
        'classes': classes,
        'school': school,
    }
    return render(request, 'fees/fee_structure_form.html', context)


def fee_structure_edit(
    request,
    tenant_schema=None,
    pk=None,
    *args,
    **kwargs,
):
    """Edit a fee structure with dynamic fee components."""

    from decimal import Decimal, InvalidOperation

    from django.db import transaction
    from django.shortcuts import get_object_or_404, redirect, render
    from django.urls import reverse

    from .forms import FeeStructureForm
    from .models import (
        Class as ClassModel,
        FeeComponent,
        FeeStructure,
        SchoolSetting,
    )

    tenant_schema = resolve_tenant_schema(
        request,
        tenant_schema,
    )

    fee_structure = get_object_or_404(
        FeeStructure,
        pk=pk,
    )

    if request.method == "POST":
        form = FeeStructureForm(
            request.POST,
            instance=fee_structure,
        )

        if form.is_valid():
            try:
                with transaction.atomic():
                    fee_structure = form.save()

                    kept_component_ids = []

                    for key, value in request.POST.items():
                        if not key.startswith("component_id_"):
                            continue

                        try:
                            component_id = int(value)
                        except (TypeError, ValueError):
                            continue

                        component = FeeComponent.objects.filter(
                            id=component_id,
                            fee_structure=fee_structure,
                        ).first()

                        if not component:
                            continue

                        name = request.POST.get(
                            f"component_name_{component_id}",
                            "",
                        ).strip()

                        amount_value = request.POST.get(
                            f"component_amount_{component_id}",
                            "",
                        ).strip()

                        is_optional = (
                            request.POST.get(
                                f"component_optional_{component_id}"
                            )
                            == "on"
                        )

                        description = request.POST.get(
                            f"component_description_{component_id}",
                            "",
                        ).strip()

                        if not name or not amount_value:
                            component.delete()
                            continue

                        try:
                            amount = Decimal(amount_value)
                        except (InvalidOperation, TypeError, ValueError):
                            component.delete()
                            continue

                        if amount < 0:
                            component.delete()
                            continue

                        component.name = name
                        component.amount = amount
                        component.is_optional = is_optional
                        component.description = description
                        component.save(
                            update_fields=[
                                "name",
                                "amount",
                                "is_optional",
                                "description",
                            ]
                        )

                        kept_component_ids.append(component.id)

                    fee_structure.custom_fees.exclude(
                        id__in=kept_component_ids
                    ).delete()

                    for key, value in request.POST.items():
                        if not key.startswith("new_component_name_"):
                            continue

                        index = key.replace(
                            "new_component_name_",
                            "",
                        )

                        name = value.strip()

                        amount_value = request.POST.get(
                            f"new_component_amount_{index}",
                            "",
                        ).strip()

                        is_optional = (
                            request.POST.get(
                                f"new_component_optional_{index}"
                            )
                            == "on"
                        )

                        description = request.POST.get(
                            f"new_component_description_{index}",
                            "",
                        ).strip()

                        if not name or not amount_value:
                            continue

                        try:
                            amount = Decimal(amount_value)
                        except (InvalidOperation, TypeError, ValueError):
                            continue

                        if amount < 0:
                            continue

                        FeeComponent.objects.create(
                            fee_structure=fee_structure,
                            name=name,
                            amount=amount,
                            is_optional=is_optional,
                            description=description,
                        )

                    total = fee_structure.calculate_total()

                    fee_structure.total_fees = total
                    fee_structure.save(
                        update_fields=["total_fees"]
                    )

                messages.success(
                    request,
                    (
                        "Fee structure updated successfully! "
                        f"Total: KES {total:,.2f}"
                    ),
                )

                return redirect(
                    reverse(
                        "digitallibrary:fee_structure_list",
                        kwargs={
                            "tenant_schema": tenant_schema,
                        },
                    )
                )

            except Exception as exc:
                messages.error(
                    request,
                    f"Unable to update fee structure: {exc}",
                )

        else:
            for field, errors in form.errors.items():
                field_label = (
                    form.fields[field].label
                    if field in form.fields
                    else field
                )

                for error in errors:
                    messages.error(
                        request,
                        f"{field_label}: {error}",
                    )

    else:
        form = FeeStructureForm(
            instance=fee_structure,
        )

    fee_components = (
        fee_structure.custom_fees.all()
        .order_by("id")
    )

    components_data = [
        {
            "id": component.id,
            "name": component.name,
            "amount": str(component.amount),
            "is_optional": component.is_optional,
            "description": component.description or "",
        }
        for component in fee_components
    ]

    classes = ClassModel.objects.filter(
        is_active=True,
    ).order_by("name")

    school = SchoolSetting.objects.first()

    context = {
        "tenant_schema": tenant_schema,
        "form": form,
        "title": (
            "Edit Fee Structure - "
            + (
                fee_structure.student_class.name
                if fee_structure.student_class
                else "N/A"
            )
        ),
        "fee_structure": fee_structure,
        "fee_components": components_data,
        "is_edit": True,
        "classes": classes,
        "school": school,
    }

    return render(
        request,
        "fees/fee_structure_form.html",
        context,
    )


def fee_structure_delete(request, pk):
    """Delete a fee structure"""
    from .models import FeeStructure, SchoolSetting
    
    fee_structure = get_object_or_404(FeeStructure, pk=pk)
    school = SchoolSetting.objects.first()
    
    if request.method == 'POST':
        class_name = fee_structure.student_class.name if fee_structure.student_class else 'N/A'
        term = fee_structure.term
        year = fee_structure.academic_year
        fee_structure.delete()
        messages.success(request, f'Fee structure for {class_name} - Term {term} {year} deleted successfully!')
        return redirect('digitallibrary:fee_structure_list')
    
    context = {
        'fee_structure': fee_structure,
        'school': school,
    }
    return render(request, 'fees/fee_structure_confirm_delete.html', context)


def fee_structure_delete_component(request, pk):
    """Delete a fee component via AJAX"""
    from .models import FeeComponent
    
    if request.method == 'POST':
        try:
            component = get_object_or_404(FeeComponent, pk=pk)
            component.delete()
            return JsonResponse({'success': True, 'message': 'Component deleted successfully'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@tenant_app_view
def payment_record(request, tenant_schema=None):
    """Record a new payment - tenant-safe version"""

    from django.shortcuts import render, redirect
    from django.contrib import messages
    from django.db import connection
    from django_tenants.utils import schema_context
    from .models import Student, FeePayment, SchoolSetting
    from .forms import FeePaymentForm

    # ------------------------------------------------------------
    # Detect tenant schema
    # ------------------------------------------------------------
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        schema_name = "nyaneje"

    tenant_base_url = f"/tenant/{schema_name}/app"

    print("\n" + "=" * 60)
    print("💵 payment_record called")
    print(f"   Method: {request.method}")
    print(f"   Path: {request.path}")
    print(f"   Tenant schema detected: {schema_name}")
    if request.method == "POST":
        print(f"   POST keys: {list(request.POST.keys())}")
    print("=" * 60)

    with schema_context(schema_name):

        if request.method == "POST":
            student_id = request.POST.get("student_id")

            if student_id:
                post_data = request.POST.copy()
                post_data["student"] = student_id
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
                    f"Payment of KES {payment.amount:,.2f} recorded for "
                    f"{payment.student.get_full_name()}. Receipt: {payment.receipt_number}"
                )

                # Tenant-safe redirect after payment
                return redirect(
                    f"{tenant_base_url}/student/{payment.student.pk}/fee-detail/"
                )

            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")

        else:
            form = FeePaymentForm()

        recent_payments = FeePayment.objects.all().order_by("-payment_date")[:10]

        all_students = Student.objects.filter(
            is_active=True
        ).select_related(
            "current_class"
        ).order_by(
            "first_name",
            "last_name"
        )

        school = SchoolSetting.objects.first()

        context = {
            "form": form,
            "recent_payments": recent_payments,
            "all_students": all_students,
            "title": "Record Payment",
            "school": school,

            # Tenant-safe context
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,

            # Useful URLs
            "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
            "tenant_fees_url": f"{tenant_base_url}/fees/",
            "tenant_payment_record_url": f"{tenant_base_url}/fees/payments/record/",
        }

        return render(request, "fees/payment_record.html", context)


@login_required
def payment_receipt(request, tenant_schema=None, pk=None):
    """View and print receipt for a payment - tenant-safe version"""

    from django.shortcuts import render, redirect, get_object_or_404
    from django.contrib import messages
    from django.db import connection
    from django_tenants.utils import schema_context
    from .models import FeePayment, SchoolSetting

    # ------------------------------------------------------------
    # Detect tenant schema
    # ------------------------------------------------------------
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        schema_name = "nyaneje"

    tenant_base_url = f"/tenant/{schema_name}/app"

    print("\n" + "=" * 60)
    print("🧾 payment_receipt called")
    print(f"   Method: {request.method}")
    print(f"   Path: {request.path}")
    print(f"   Tenant schema detected: {schema_name}")
    print(f"   Payment ID: {pk}")
    print("=" * 60)

    with schema_context(schema_name):

        payment = get_object_or_404(FeePayment, pk=pk)
        school = SchoolSetting.objects.first()

        user_role = getattr(getattr(request.user, "profile", None), "role", None)

        if user_role not in ["admin", "principal"] and payment.recorded_by != request.user:
            messages.error(request, "Access Denied.")
            return redirect(f"{tenant_base_url}/dashboard/")

        context = {
            "payment": payment,
            "school": school,
            "title": "Payment Receipt",

            # Tenant-safe context
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,

            # Useful URLs
            "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
            "tenant_fees_url": f"{tenant_base_url}/fees/",
            "tenant_payment_record_url": f"{tenant_base_url}/fees/payments/record/",
            "tenant_student_fee_detail_url": f"{tenant_base_url}/student/{payment.student.pk}/fee-detail/",
        }

        return render(request, "fees/payment_receipt.html", context)


@login_required
def export_defaulters_csv(request, tenant_schema=None):
    """Export defaulters list to CSV - tenant-safe version"""

    import csv
    from django.http import HttpResponse
    from django.db import connection
    from django.db.models import Sum
    from django.utils import timezone
    from django_tenants.utils import schema_context
    from .models import FeeBalance

    # ------------------------------------------------------------
    # Detect tenant schema
    # ------------------------------------------------------------
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        schema_name = "nyaneje"

    with schema_context(schema_name):

        current_year = request.GET.get("year", str(timezone.now().year))
        current_term = request.GET.get("term", "1")

        balances = FeeBalance.objects.filter(
            academic_year=current_year,
            term=current_term,
            balance__gt=0
        ).exclude(
            status="OVERPAID"
        ).select_related(
            "student",
            "student__current_class"
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="defaulters_{current_year}_term{current_term}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow([
            "Admission No",
            "Student Name",
            "Class",
            "Parent Name",
            "Parent Phone",
            "Balance"
        ])

        for balance in balances:
            writer.writerow([
                balance.student.admission_number,
                balance.student.get_full_name(),
                balance.student.current_class.name if balance.student.current_class else "N/A",
                balance.student.parent_name,
                balance.student.parent_phone,
                f"KES {balance.balance:,.2f}",
            ])

        return response


@login_required
def export_fees_csv(request, tenant_schema=None):
    """Export fee data to CSV - tenant-safe version"""

    import csv
    from django.http import HttpResponse
    from django.db import connection
    from django.utils import timezone
    from django_tenants.utils import schema_context
    from .models import FeeBalance

    # ------------------------------------------------------------
    # Detect tenant schema
    # ------------------------------------------------------------
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        schema_name = "nyaneje"

    with schema_context(schema_name):

        current_year = request.GET.get("year", str(timezone.now().year))
        current_term = request.GET.get("term", "1")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="fee_report_{current_year}_term{current_term}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow([
            "Admission Number",
            "Student Name",
            "Class",
            "Total Expected",
            "Total Paid",
            "Balance",
            "Status"
        ])

        balances = FeeBalance.objects.filter(
            academic_year=current_year,
            term=current_term
        ).select_related(
            "student",
            "student__current_class"
        )

        for balance in balances:
            writer.writerow([
                balance.student.admission_number,
                balance.student.get_full_name(),
                balance.student.current_class.name if balance.student.current_class else "N/A",
                f"KES {balance.total_expected:,.2f}",
                f"KES {balance.total_paid:,.2f}",
                f"KES {balance.balance:,.2f}",
                balance.status,
            ])

        return response
# ========== STUDENT BULK UPLOAD VIEW ==========

import pandas as pd
from django.core.validators import ValidationError

def student_bulk_upload(request, tenant_schema=None):
    """Bulk upload students via Excel/CSV"""
    from .forms import BulkStudentUploadForm
    from .models import Student, Class
    from django.core.validators import ValidationError
    
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
            
            # Normalize columns
            df.columns = df.columns.str.strip().str.lower()
            
            # Check for required columns
            required_fields = ['first name', 'last name', 'admission number']
            missing_fields = [f for f in required_fields if f not in df.columns]
            if missing_fields:
                messages.error(request, f'Missing required columns: {", ".join(missing_fields)}')
                return redirect('digitallibrary:student_bulk_upload')
            
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
                    
                    # Get admission year
                    admission_year = 2026
                    year_value = row.get('admission year', '')
                    if pd.notna(year_value):
                        try:
                            year_str = str(year_value).strip()
                            admission_year = int(float(year_str)) if year_str else 2026
                        except (ValueError, TypeError):
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
                        is_active=True
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


# ========== STUDENT EDIT VIEW (if missing) ==========

@login_required
@user_passes_test(
    lambda u: (
        u.is_staff
        or getattr(u, "role", None) == "admin"
        or (
            hasattr(u, "profile")
            and getattr(u.profile, "role", None) in ["admin", "principal", "teacher"]
        )
    )
)
def student_edit(request, tenant_schema=None, pk=None, *args, **kwargs):
    """Edit an existing student - tenant-safe version"""

    from django.shortcuts import render, get_object_or_404, redirect
    from django.contrib import messages
    from django.db import connection

    from .forms import StudentForm
    from .models import Student, Class, Subject, SchoolSetting

    # ------------------------------------------------------------
    # 1. Resolve tenant schema safely
    # ------------------------------------------------------------
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    tenant_schema = str(tenant_schema).strip()

    if tenant_schema in ["", "public", "None", "none", "null", "undefined"]:
        tenant_schema = "nyaneje"

    request.tenant_schema = tenant_schema

    if hasattr(request, "session"):
        request.session["tenant_schema"] = tenant_schema
        request.session.modified = True

    tenant_base_url = f"/tenant/{tenant_schema}/app"

    # ------------------------------------------------------------
    # 2. Get student
    # ------------------------------------------------------------
    student = get_object_or_404(Student, pk=pk)

    print("\n" + "=" * 80)
    print("STUDENT EDIT VIEW - START")
    print(f"Tenant schema: {tenant_schema}")
    print(f"Editing student: {student.first_name} {student.last_name} (ID: {student.id})")
    print("=" * 80)

    current_subjects = list(student.subjects.values_list("name", flat=True))

    # ------------------------------------------------------------
    # 3. Handle POST update
    # ------------------------------------------------------------
    if request.method == "POST":
        print("\n📝 REQUEST METHOD: POST")

        elective_subjects = request.POST.getlist("elective_subjects")
        print(f"\n📚 ELECTIVE SUBJECTS FROM POST: {elective_subjects}")

        pathway_value = request.POST.get("pathway", "")
        print(f"   Pathway from POST: {pathway_value}")

        form = StudentForm(request.POST, request.FILES, instance=student)

        if form.is_valid():
            student = form.save(commit=False)

            if pathway_value:
                student.pathway = pathway_value

            # ------------------------------------------------------------
            # 4. Handle class assignment
            # ------------------------------------------------------------
            new_class_name = form.cleaned_data.get("new_class")
            current_class_id = form.cleaned_data.get("current_class")

            if new_class_name:
                class_obj, created = Class.objects.get_or_create(
                    name=new_class_name.title()
                )
                student.current_class = class_obj

            elif current_class_id:
                try:
                    if isinstance(current_class_id, Class):
                        student.current_class = current_class_id
                    else:
                        student.current_class = Class.objects.get(id=current_class_id)

                except (Class.DoesNotExist, ValueError, TypeError):
                    messages.error(request, "Selected class does not exist.")

                    context = {
                        "form": form,
                        "classes": Class.objects.all().order_by("name"),
                        "student": student,
                        "current_subjects": current_subjects,
                        "pathway_value": pathway_value,
                        "title": "Edit Student",
                        "action": "Edit",

                        "tenant_schema": tenant_schema,
                        "current_tenant_schema": tenant_schema,
                        "tenant_base_url": tenant_base_url,
                        "app_prefix": tenant_base_url,
                        "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
                        "tenant_student_list_url": f"{tenant_base_url}/fees/students/",
                        "tenant_student_detail_url": f"{tenant_base_url}/students/{student.id}/",
                    }

                    return render(request, "digitallibrary/student_form.html", context)

            student.save()

            # ------------------------------------------------------------
            # 5. Handle elective subjects
            # ------------------------------------------------------------
            student.subjects.clear()

            for subject_name in elective_subjects:
                if subject_name and subject_name.strip():
                    subject_obj, _ = Subject.objects.get_or_create(
                        name=subject_name.strip(),
                        defaults={"is_active": True},
                    )
                    student.subjects.add(subject_obj)

            # ------------------------------------------------------------
            # 6. Add compulsory subjects based on pathway
            # ------------------------------------------------------------
            if student.pathway:
                compulsory_mapping = {
                    "arts_sports": [
                        "English",
                        "Kiswahili/KSL",
                        "Core Mathematics",
                        "Community Service Learning (CSL)",
                    ],
                    "social_sciences": [
                        "English",
                        "Kiswahili/KSL",
                        "Core Mathematics",
                        "Community Service Learning (CSL)",
                    ],
                    "stem": [
                        "English",
                        "Kiswahili/KSL",
                        "Core Mathematics",
                        "Community Service Learning (CSL)",
                    ],
                }

                for subject_name in compulsory_mapping.get(student.pathway, []):
                    subject_obj, _ = Subject.objects.get_or_create(
                        name=subject_name,
                        defaults={
                            "is_compulsory": True,
                            "category": "compulsory",
                        },
                    )
                    student.subjects.add(subject_obj)

            messages.success(
                request,
                f"Student {student.first_name} {student.last_name} updated successfully!",
            )

            return redirect(
                "digitallibrary:student_detail",
                
                pk=student.pk,
            )

        else:
            messages.error(request, "Please correct the errors below.")

    else:
        form = StudentForm(instance=student)

    # ------------------------------------------------------------
    # 7. Render form
    # ------------------------------------------------------------
    classes = Class.objects.all().order_by("name")
    pathway_value = student.pathway if student.pathway else ""
    school = SchoolSetting.objects.first()

    context = {
        "form": form,
        "classes": classes,
        "student": student,
        "current_subjects": current_subjects,
        "pathway_value": pathway_value,
        "title": "Edit Student",
        "action": "Edit",
        "school": school,

        # Tenant-safe context
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "app_prefix": tenant_base_url,

        # Useful URLs
        "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
        "tenant_student_list_url": f"{tenant_base_url}/fees/students/",
        "tenant_student_detail_url": f"{tenant_base_url}/students/{student.id}/",
    }

    return render(request, "digitallibrary/student_form.html", context)
# ========== STUDENT CREATE VIEW ==========

from django.contrib import messages
from django.shortcuts import redirect, render

from .decorators import tenant_and_role_required

def is_old_curriculum_class(school_class):
    """
    Form 3 and Form 4 students are old curriculum students.
    They should not require a CBE pathway.
    """
    if not school_class:
        return False

    class_name = (
        getattr(school_class, "name", "")
        or str(school_class)
        or ""
    ).lower()

    old_curriculum_keywords = [
        "form 3",
        "form three",
        "form iii",
        "form 4",
        "form four",
        "form iv",
    ]

    return any(
        keyword in class_name
        for keyword in old_curriculum_keywords
    )

@tenant_and_role_required(["admin", "principal"])
def student_create(request, tenant_schema=None):
    """
    Create a new student with class assignment and subjects.

    CBE pathway is optional because some students are still
    in the old system, such as Form 3 and Form 4.
    """
    from .forms import StudentForm
    from .models import Class, Subject

    if request.method == "POST":
        form = StudentForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            student = form.save(commit=False)

            # --------------------------------------------------
            # CBE PATHWAY - OPTIONAL
            # --------------------------------------------------
            pathway_value = request.POST.get("pathway", "").strip()

            if pathway_value:
                student.pathway = pathway_value
            else:
                # Important: old-system students can leave this blank.
                student.pathway = ""

            # --------------------------------------------------
            # CLASS ASSIGNMENT
            # --------------------------------------------------
            new_class_name = form.cleaned_data.get("new_class")
            current_class_id = form.cleaned_data.get("current_class")

            if new_class_name:
                class_obj, created = Class.objects.get_or_create(
                    name=new_class_name.title()
                )

                student.current_class = class_obj

                if created:
                    messages.info(
                        request,
                        f'New class "{new_class_name}" has been created.',
                    )

            elif current_class_id:
                try:
                    if isinstance(current_class_id, Class):
                        student.current_class = current_class_id
                    else:
                        student.current_class = Class.objects.get(
                            id=current_class_id
                        )

                except (
                    Class.DoesNotExist,
                    ValueError,
                    TypeError,
                ):
                    messages.error(
                        request,
                        "Selected class does not exist.",
                    )

                    return render(
                        request,
                        "digitallibrary/student_form.html",
                        {
                            "form": form,
                            "classes": Class.objects.all().order_by("name"),
                            "title": "Create Student",
                            "action": "Create",
                        },
                    )

            # --------------------------------------------------
            # SAVE STUDENT FIRST
            # --------------------------------------------------
            student.save()

            # --------------------------------------------------
            # ELECTIVE SUBJECTS - OPTIONAL
            # --------------------------------------------------
            elective_subjects = request.POST.getlist("elective_subjects")

            subjects_hidden = request.POST.get(
                "elective_subjects_hidden",
                "",
            )

            if subjects_hidden:
                hidden_subjects = [
                    subject.strip()
                    for subject in subjects_hidden.split(",")
                    if subject.strip()
                ]

                if hidden_subjects and not elective_subjects:
                    elective_subjects = hidden_subjects

            single_subject = request.POST.get(
                "elective_subjects",
                "",
            )

            if single_subject and not elective_subjects:
                elective_subjects = [single_subject]

            student.subjects.clear()

            if elective_subjects:
                added_count = 0

                for subject_name in elective_subjects:
                    subject_name = subject_name.strip()

                    if subject_name:
                        subject_obj, created = Subject.objects.get_or_create(
                            name=subject_name,
                            defaults={
                                "is_active": True,
                            },
                        )

                        student.subjects.add(subject_obj)
                        added_count += 1

                if added_count > 0:
                    messages.info(
                        request,
                        f"{added_count} elective subjects selected.",
                    )

            # --------------------------------------------------
            # CBE COMPULSORY SUBJECTS
            # Only add these if pathway was selected.
            # Old system students skip this section.
            # --------------------------------------------------
            if student.pathway:
                compulsory_subjects = {
                    "arts_sports": [
                        "English",
                        "Kiswahili/KSL",
                        "Core Mathematics",
                        "Community Service Learning (CSL)",
                    ],
                    "social_sciences": [
                        "English",
                        "Kiswahili/KSL",
                        "Core Mathematics",
                        "Community Service Learning (CSL)",
                    ],
                    "stem": [
                        "English",
                        "Kiswahili/KSL",
                        "Core Mathematics",
                        "Community Service Learning (CSL)",
                    ],
                }

                pathway_subjects = compulsory_subjects.get(
                    student.pathway,
                    [],
                )

                for subject_name in pathway_subjects:
                    subject_obj, created = Subject.objects.get_or_create(
                        name=subject_name,
                        defaults={
                            "is_compulsory": True,
                            "category": "compulsory",
                            "is_active": True,
                        },
                    )

                    student.subjects.add(subject_obj)

            messages.success(
                request,
                (
                    f"Student {student.first_name} "
                    f"{student.last_name} created successfully!"
                ),
            )

            # --------------------------------------------------
            # TENANT-SAFE REDIRECT
            # --------------------------------------------------
            active_tenant_schema = getattr(
                getattr(request, "tenant", None),
                "schema_name",
                tenant_schema,
            )

            if active_tenant_schema and active_tenant_schema != "public":
                return redirect(
                    f"/tenant/{active_tenant_schema}/app/students/{student.pk}/"
                )

            return redirect(
                "digitallibrary:student_detail",
                pk=student.pk,
            )

        messages.error(
            request,
            "Please correct the errors below.",
        )

    else:
        form = StudentForm()

    classes = Class.objects.all().order_by("name")

    context = {
        "form": form,
        "classes": classes,
        "title": "Create Student",
        "action": "Create",
    }

    return render(
        request,
        "digitallibrary/student_form.html",
        context,
    )
# ========== PRINT FEE STRUCTURE VIEW ==========

@fees_access
def print_fee_structure(request, fee_structure_id):
    """Print fee structure details"""
    from .models import FeeStructure, FeeComponent, SchoolSetting
    
    fee_structure = get_object_or_404(FeeStructure, id=fee_structure_id)
    school = SchoolSetting.objects.first()
    
    # Get fee components
    fee_components = FeeComponent.objects.filter(fee_structure=fee_structure)
    
    context = {
        'fee_structure': fee_structure,
        'fee_components': fee_components,
        'school': school,
        'school_name': school.name if school else 'School Name',
        'school_logo': school.logo.url if school and school.logo else None,
        'school_motto': school.motto if school else 'Excellence in Education',
        'title': 'Print Fee Structure',
        'is_print_view': True,
    }
    return render(request, 'fees/fee_structure_print.html', context)


# ========== FEE UPDATE PAGE ==========

def fee_update_page(request):
    """Page to update student fees"""
    from .models import Student, FeeStructure, Payment
    
    students = Student.objects.select_related('current_class').all()
    
    for student in students:
        # Calculate total fees for student
        fee_items = FeeStructure.objects.filter(
            student_class=student.current_class
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


# ========== GET STUDENTS BY CLASS ==========

def get_students_by_class(request, class_id):
    """API to get students for a specific class"""
    from .models import Student
    
    students = Student.objects.filter(
        current_class_id=class_id,
        is_active=True
    ).values('id', 'admission_number', 'first_name', 'last_name')
    
    return JsonResponse({
        'success': True,
        'students': list(students)
    })


def get_all_students(request):
    """API to get all active students"""
    from .models import Student
    
    students = Student.objects.filter(
        is_active=True
    ).values('id', 'admission_number', 'first_name', 'last_name')
    
    return JsonResponse({
        'success': True,
        'students': list(students)
    })


# ========== SUBMIT FEEDBACK ==========

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import json

@csrf_exempt
@require_http_methods(["POST"])
def submit_feedback(request, tenant_schema=None):
    """Submit feedback with full school info - tenant-safe JSON version"""
    import json
    import traceback

    from django.http import JsonResponse
    from django.db import connection
    from django.conf import settings
    from django.core.mail import send_mail

    from .models import Feedback

    # ------------------------------------------------------------
    # 1. Resolve tenant schema safely
    # ------------------------------------------------------------
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    tenant_schema = str(tenant_schema).strip()

    if tenant_schema in ["", "public", "None", "none", "null", "undefined"]:
        tenant_schema = "nyaneje"

    request.tenant_schema = tenant_schema

    if hasattr(request, "session"):
        request.session["tenant_schema"] = tenant_schema
        request.session.modified = True

    # ------------------------------------------------------------
    # 2. Helper: Get client IP
    # ------------------------------------------------------------
    def get_client_ip(req):
        x_forwarded_for = req.META.get("HTTP_X_FORWARDED_FOR")

        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        return req.META.get("REMOTE_ADDR")

    # ------------------------------------------------------------
    # 3. Helper: Send email notification safely
    # ------------------------------------------------------------
    def send_feedback_notification(feedback):
        try:
            admin_email = getattr(settings, "ADMIN_EMAIL", None)
            default_from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)

            if not admin_email or not default_from_email:
                print("⚠️ Feedback email skipped: ADMIN_EMAIL or DEFAULT_FROM_EMAIL not configured.")
                return

            subject = f"[Feedback] {feedback.school_name or 'Unknown School'} - {feedback.subject}"

            message = f"""
New Feedback Received

SCHOOL INFORMATION
School: {feedback.school_name or 'Unknown'}
Location: {feedback.school_location or 'Not specified'}
School ID: {feedback.school_id or 'N/A'}
Tenant Schema: {tenant_schema}

USER INFORMATION
Name: {feedback.user_name or 'Anonymous'}
Role: {feedback.user_role or 'User'}
Email: {feedback.user_email or 'Not provided'}

FEEDBACK DETAILS
Type: {feedback.get_feedback_type_display()}
Priority: {feedback.get_priority_display()}
Rating: {feedback.rating or 'No rating'}/5
Subject: {feedback.subject}

Message:
{feedback.message}

Page URL:
{feedback.page_url or 'Not provided'}

Browser:
{feedback.browser_info or 'Not provided'}

IP Address:
{feedback.ip_address or 'Not available'}

Time:
{feedback.created_at.strftime('%Y-%m-%d %H:%M:%S')}
"""

            send_mail(
                subject,
                message,
                default_from_email,
                [admin_email],
                fail_silently=True,
            )

        except Exception as e:
            print(f"❌ Failed to send feedback email: {e}")

    # ------------------------------------------------------------
    # 4. Parse and save feedback
    # ------------------------------------------------------------
    try:
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({
                "success": False,
                "status": "error",
                "error": "Invalid JSON data.",
                "message": "Invalid JSON data.",
            }, status=400)

        subject = (data.get("subject") or "").strip()
        message = (data.get("message") or "").strip()

        if not subject or not message:
            return JsonResponse({
                "success": False,
                "status": "error",
                "error": "Subject and message are required.",
                "message": "Subject and message are required.",
            }, status=400)

        school = getattr(request, "tenant", None)

        user = request.user if request.user.is_authenticated else None

        user_role = None
        if user and hasattr(user, "profile"):
            user_role = getattr(user.profile, "role", None)

        rating_value = data.get("rating")
        try:
            rating_value = int(rating_value) if rating_value not in [None, "", "0"] else None
        except Exception:
            rating_value = None

        feedback = Feedback.objects.create(
            user=user,
            user_role=data.get("user_role") or user_role,
            user_email=data.get("user_email") or (user.email if user else None),
            user_name=data.get("user_name") or (user.get_full_name() if user else None),

            school_id=data.get("school_id") or getattr(school, "school_id", None) or getattr(school, "id", None),
            school_name=data.get("school_name") or getattr(school, "name", None) or f"{tenant_schema.title()} School",
            school_location=data.get("school_location") or getattr(school, "location", None),
            school_email=data.get("school_email") or getattr(school, "contact_email", None),
            school_phone=data.get("school_phone") or getattr(school, "contact_phone", None),
            school_domain=data.get("school_domain") or getattr(school, "domain", None),
            school_subdomain=data.get("school_subdomain") or tenant_schema,

            feedback_type=data.get("feedback_type", "general"),
            priority=data.get("priority", "medium"),
            subject=subject[:200],
            message=message,
            rating=rating_value,

            page_url=data.get("page_url", request.META.get("HTTP_REFERER", "")),
            browser_info=request.headers.get("User-Agent", "")[:500],
            ip_address=get_client_ip(request),
        )

        print(f"✅ Feedback saved - School: {feedback.school_name}, ID: {feedback.school_id}")

        send_feedback_notification(feedback)

        # IMPORTANT:
        # Return both success=True and status='success'
        # because your JavaScript checks data.success.
        return JsonResponse({
            "success": True,
            "status": "success",
            "message": "Feedback submitted successfully.",
            "feedback_id": feedback.id,
        })

    except Exception as e:
        print(f"❌ Error in submit_feedback: {str(e)}")
        traceback.print_exc()

        return JsonResponse({
            "success": False,
            "status": "error",
            "error": str(e),
            "message": str(e),
        }, status=500)

def send_feedback_notification(feedback):
    """Send email notification for new feedback"""
    from django.conf import settings
    from django.core.mail import send_mail
    
    try:
        subject = f"[Feedback] {feedback.school_name or 'Unknown School'} - {feedback.subject}"
        
        message = f"""
        New Feedback Received
        
        SCHOOL INFORMATION
        School: {feedback.school_name or 'Unknown'}
        Location: {feedback.school_location or 'Not specified'}
        School ID: {feedback.school_id or 'N/A'}
        
        USER INFORMATION
        Name: {feedback.user_name or 'Anonymous'}
        Role: {feedback.user_role or 'User'}
        Email: {feedback.user_email or 'Not provided'}
        
        FEEDBACK DETAILS
        Type: {feedback.get_feedback_type_display()}
        Priority: {feedback.get_priority_display()}
        Rating: {feedback.rating or 'No rating'}/5
        Subject: {feedback.subject}
        
        Message:
        {feedback.message}
        
        Time: {feedback.created_at.strftime('%Y-%m-%d %H:%M:%S')}
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
# ========== PERFORMANCE DASHBOARD VIEWS ==========

@tenant_app_view
def performance_dashboard(request):
    """Performance dashboard with actual data"""
    from .models import Exam, Student, Subject, Class, SchoolSetting, StudentResult
    from django.db.models import Avg, Count
    
    # Try to import the correct result model
    Result = StudentResult
    
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
        'school': school,
        'school_name': school.name if school else 'Performance Dashboard',
        'school_logo': school.logo.url if school and school.logo else None,
        'school_motto': school.motto if school else '',
    }
    
    return render(request, 'performance/dashboard.html', context)


@login_required
def exam_performance_detail(request, exam_id, tenant_schema=None):
    """View detailed performance for a specific exam"""
    from django.shortcuts import get_object_or_404, render
    from django.db.models import Avg, Sum, Max, Min
    from .models import Exam, Subject, Student, StudentResult

    exam = get_object_or_404(Exam, id=exam_id)

    if exam.student_class:
        students = exam.student_class.students.filter(is_active=True)
    else:
        students = Student.objects.filter(is_active=True)

    total_students = students.count()
    subjects = Subject.objects.all()
    total_subjects = subjects.count()
    results = StudentResult.objects.filter(exam=exam)

    class_average = results.aggregate(avg=Avg("score"))["avg"] or 0

    total_results = results.values("student").distinct().count()
    passed_results = results.filter(score__gte=50).values("student").distinct().count()
    pass_rate = (passed_results / total_results * 100) if total_results > 0 else 0

    top_student_data = (
        results.values("student")
        .annotate(total=Sum("score"))
        .order_by("-total")
        .first()
    )

    top_student = None
    if top_student_data:
        top_student = Student.objects.filter(id=top_student_data["student"]).first()

    subjects_performance = []

    for subject in subjects:
        subject_results = results.filter(subject=subject)

        if subject_results.exists():
            avg = subject_results.aggregate(avg=Avg("score"))["avg"] or 0
            highest = subject_results.aggregate(max=Max("score"))["max"] or 0
            lowest = subject_results.aggregate(min=Min("score"))["min"] or 0
            passed = subject_results.filter(score__gte=50).count()

            if avg >= 80:
                grade = "A"
            elif avg >= 70:
                grade = "B"
            elif avg >= 60:
                grade = "C"
            elif avg >= 50:
                grade = "D"
            else:
                grade = "E"

            subjects_performance.append({
                "id": subject.id,
                "name": subject.name,
                "average": avg,
                "highest": highest,
                "lowest": lowest,
                "passed": passed,
                "total_students": total_students,
                "grade": grade,
            })

    rankings = []

    for student in students:
        student_results = results.filter(student=student)

        if student_results.exists():
            subject_scores = []

            for subject in subjects:
                subject_result = student_results.filter(subject=subject).first()
                subject_scores.append(subject_result.score if subject_result else None)

            total = sum([r.score for r in student_results if r.score is not None])
            average = total / student_results.count() if student_results.count() > 0 else 0

            if average >= 80:
                grade = "A"
            elif average >= 75:
                grade = "A-"
            elif average >= 70:
                grade = "B+"
            elif average >= 65:
                grade = "B"
            elif average >= 60:
                grade = "B-"
            elif average >= 55:
                grade = "C+"
            elif average >= 50:
                grade = "C"
            elif average >= 45:
                grade = "C-"
            elif average >= 40:
                grade = "D+"
            else:
                grade = "E"

            rankings.append({
                "student": student,
                "subject_scores": subject_scores,
                "total": total,
                "average": average,
                "grade": grade,
            })

    rankings.sort(key=lambda x: x["average"], reverse=True)

    context = {
        "tenant_schema": tenant_schema,
        "exam": exam,
        "total_students": total_students,
        "total_subjects": total_subjects,
        "class_average": class_average,
        "pass_rate": pass_rate,
        "top_student": top_student,
        "subjects_performance": subjects_performance,
        "subjects_list": subjects,
        "rankings": rankings,
    }

    return render(request, "performance/exam_performance_detail.html", context)

def system_dashboard(request):
    """Executive dashboard with filtering"""
    from .models import Exam, Class, Subject, Student, StudentResult
    from django.db.models import Avg
    
    current_year = request.GET.get('year', '')
    current_term = request.GET.get('term', '')
    selected_class = request.GET.get('class', '')
    selected_subject = request.GET.get('subject', '')
    
    exams_qs = Exam.objects.all().order_by('-academic_year', '-created_at')
    
    if current_year:
        exams_qs = exams_qs.filter(academic_year=current_year)
    if current_term:
        exams_qs = exams_qs.filter(term=current_term)
    if selected_class:
        exams_qs = exams_qs.filter(student_class_id=selected_class)
    
    available_years = Exam.objects.values_list('academic_year', flat=True).distinct().order_by('-academic_year')
    
    recent_exams = []
    for exam in exams_qs:
        if exam.student_class:
            total_students = exam.student_class.students.filter(is_active=True).count()
        else:
            total_students = Student.objects.filter(is_active=True).count()
        
        results_qs = StudentResult.objects.filter(exam=exam)
        
        if selected_subject:
            results_qs = results_qs.filter(subject_id=selected_subject)
            results_count = results_qs.values('student').distinct().count()
        else:
            results_count = results_qs.values('student').distinct().count()
        
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
    
    results_qs = StudentResult.objects.all()
    if current_year:
        results_qs = results_qs.filter(exam__academic_year=current_year)
    if current_term:
        results_qs = results_qs.filter(exam__term=current_term)
    if selected_class:
        results_qs = results_qs.filter(student__current_class_id=selected_class)
    if selected_subject:
        results_qs = results_qs.filter(subject_id=selected_subject)
    
    avg_score = results_qs.aggregate(avg=Avg('score'))['avg'] or 0
    
    total_results = results_qs.count()
    passed_results = results_qs.filter(score__gte=50).count()
    pass_rate = (passed_results / total_results * 100) if total_results > 0 else 0
    
    students_qs = Student.objects.filter(is_active=True)
    if selected_class:
        students_qs = students_qs.filter(current_class_id=selected_class)
    total_students = students_qs.count()
    
    total_exams = exams_qs.count()
    classes = Class.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('name')
    
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
        'classes': classes,
        'subjects': subjects,
        'available_years': available_years,
    }
    
    return render(request, 'performance/system_dashboard.html', context)
# ========== ENTER RESULTS FORM VIEW ==========


@tenant_app_view
def bulk_enter_results(request, tenant_schema=None):
    """Step 1: Select exam and subject for bulk entry."""
    from django.shortcuts import render, redirect
    from django.contrib import messages
    from django.db import connection
    from .models import Exam, Subject, SchoolSetting

    current_schema = getattr(connection, "schema_name", None)

    print("\n" + "=" * 60)
    print("🔵 bulk_enter_results called")
    print(f"   Active DB schema: {current_schema}")
    print(f"   tenant_schema from URL: {tenant_schema}")
    print(f"   Method: {request.method}")
    print("=" * 60)

    # IMPORTANT:
    # Do not use get_tenant(request) here.
    # Do not call connection.set_tenant(...) here.
    # PathTenantSchemaMiddleware already switched to the correct tenant schema.

    exams = Exam.objects.all().order_by("-id")
    subjects = Subject.objects.all().order_by("name")
    school = SchoolSetting.objects.first()

    if request.method == "POST":
        exam_id = request.POST.get("exam_id") or request.POST.get("exam")
        subject_id = request.POST.get("subject_id") or request.POST.get("subject")

        if not exam_id or not subject_id:
            messages.error(request, "Please select both exam and subject.")
            return redirect(request.path)

        return redirect(
            "digitallibrary:bulk_results_entry",
            exam_id=exam_id,
            subject_id=subject_id
        )

    context = {
        "tenant_schema": tenant_schema,
        "active_schema": current_schema,

        "exams": exams,
        "exam_list": exams,
        "available_exams": exams,

        "subjects": subjects,
        "subject_list": subjects,
        "available_subjects": subjects,

        "school": school,
        "title": "Bulk Enter Results",
    }

    print(f"   Exams available for dropdown: {exams.count()}")

    for exam in exams[:10]:
        print(f"   Exam: {exam.id} - {exam.name}")

    return render(request, "performance/bulk_enter_results.html", context)


@tenant_app_view
def bulk_select(request, tenant_schema=None):
    """Step 1: Select exam and subject for bulk entry."""
    from django.shortcuts import render, redirect
    from django.contrib import messages
    from django.db import connection
    from .models import Exam, Subject, Student, SchoolSetting

    current_schema = getattr(connection, "schema_name", None)

    print("\n" + "=" * 60)
    print("🔵 bulk_select called")
    print(f"   Active DB schema: {current_schema}")
    print(f"   tenant_schema from URL: {tenant_schema}")
    print(f"   Method: {request.method}")
    print("=" * 60)

    exams = Exam.objects.all().order_by("-id")
    subjects = Subject.objects.all().order_by("name")

    selected_exam_id = None
    selected_subject_id = None
    selected_exam = None
    total_students = 0

    if request.method == "POST":
        exam_id = request.POST.get("exam")
        subject_id = request.POST.get("subject")

        if exam_id and subject_id:
            try:
                exam = Exam.objects.get(id=exam_id)
                subject = Subject.objects.get(id=subject_id)

                return redirect(
                    "digitallibrary:bulk_results_entry",
                    exam_id=exam.id,
                    subject_id=subject.id
                )

            except (Exam.DoesNotExist, Subject.DoesNotExist):
                messages.error(request, "Invalid exam or subject selection.")

        selected_exam_id = exam_id
        selected_subject_id = subject_id

        if selected_exam_id:
            try:
                selected_exam = Exam.objects.get(id=selected_exam_id)
            except Exam.DoesNotExist:
                selected_exam = None

    else:
        exam_id = request.GET.get("exam")

        if exam_id:
            try:
                selected_exam = Exam.objects.get(id=exam_id)
                selected_exam_id = exam_id
            except Exam.DoesNotExist:
                selected_exam = None

    if selected_exam:
        if selected_exam.student_class:
            total_students = selected_exam.student_class.students.filter(
                is_active=True
            ).count()
        else:
            total_students = Student.objects.filter(is_active=True).count()

    context = {
        "tenant_schema": tenant_schema,
        "active_schema": current_schema,

        "exams": exams,
        "exam_list": exams,
        "available_exams": exams,

        "subjects": subjects,
        "subject_list": subjects,
        "available_subjects": subjects,

        "selected_exam_id": selected_exam_id,
        "selected_subject_id": selected_subject_id,
        "selected_exam": selected_exam,
        "total_students": total_students,

        "school": SchoolSetting.objects.first(),
        "title": "Select Exam and Subject",
    }

    return render(request, "digitallibrary/bulk_select.html", context)


@tenant_app_view
def bulk_results_entry(request, exam_id, subject_id, tenant_schema=None):
    """Step 2: Enter results for all students in a table."""
    from django.shortcuts import render, redirect, get_object_or_404
    from django.contrib import messages
    from django.db import connection
    from .models import Exam, Subject, Student, StudentResult, SchoolSetting

    current_schema = getattr(connection, "schema_name", None)

    print("\n" + "=" * 60)
    print("🔵 bulk_results_entry called")
    print(f"   Active DB schema: {current_schema}")
    print(f"   tenant_schema from URL: {tenant_schema}")
    print(f"   Exam ID: {exam_id}")
    print(f"   Subject ID: {subject_id}")
    print(f"   Method: {request.method}")
    print("=" * 60)

    exam = get_object_or_404(Exam, id=exam_id)
    subject = get_object_or_404(Subject, id=subject_id)

    if exam.student_class:
        students = exam.student_class.students.filter(is_active=True)
    else:
        students = Student.objects.filter(is_active=True)

    students = students.order_by("first_name", "last_name")

    results = StudentResult.objects.filter(
        exam=exam,
        subject=subject,
        student__in=students
    ).select_related("student")

    existing_results = {result.student_id: result for result in results}

    if request.method == "POST":
        saved_count = 0

        for key, value in request.POST.items():
            if key.startswith("score_") and value:
                student_id = key.replace("score_", "")

                try:
                    score = float(value)
                    student = Student.objects.get(id=student_id)

                    if score < 0 or (exam.max_score and score > exam.max_score):
                        continue

                    StudentResult.objects.update_or_create(
                        exam=exam,
                        subject=subject,
                        student=student,
                        defaults={
                            "score": score,
                            "entered_by": request.user,
                        }
                    )

                    saved_count += 1

                except (ValueError, Student.DoesNotExist):
                    continue

        messages.success(
            request,
            f"Successfully saved {saved_count} results for {subject.name}."
        )

        return redirect(
            "digitallibrary:bulk_results_entry",
            exam_id=exam.id,
            subject_id=subject.id
        )

    total_students = students.count()
    completed_count = len(existing_results)

    completion_percentage = (
        int((completed_count / total_students) * 100)
        if total_students > 0
        else 0
    )

    pending_count = total_students - completed_count

    context = {
        "tenant_schema": tenant_schema,
        "active_schema": current_schema,

        "exam": exam,
        "subject": subject,
        "students": students,
        "existing_results": existing_results,

        "completion_percentage": completion_percentage,
        "pending_count": pending_count,

        "school": SchoolSetting.objects.first(),
        "title": f"Enter Results - {exam.name} - {subject.name}",
    }

    return render(request, "digitallibrary/bulk_results_entry.html", context)


@tenant_app_view
def exam_results_entry(request, exam_id, tenant_schema=None):
    """Enter results for an exam by subject, filtered by registered student subjects."""
    from django.shortcuts import render, redirect, get_object_or_404
    from django.contrib import messages
    from django.db import connection
    from .models import Exam, Subject, StudentResult, SchoolSetting

    current_schema = getattr(connection, "schema_name", None)

    print("\n" + "=" * 60)
    print("🔵 exam_results_entry called")
    print(f"   Active DB schema: {current_schema}")
    print(f"   tenant_schema from URL: {tenant_schema}")
    print(f"   Exam ID: {exam_id}")
    print(f"   Method: {request.method}")
    print("=" * 60)

    exam = get_object_or_404(Exam, pk=exam_id)
    subjects = Subject.objects.filter(is_active=True).order_by("name")

    selected_subject_id = request.GET.get("subject")
    selected_subject = None
    students = []
    existing_results = {}

    if selected_subject_id:
        try:
            selected_subject = Subject.objects.get(
                pk=selected_subject_id,
                is_active=True
            )

            students_qs = exam.get_students_for_exam()

            students = students_qs.filter(
                subjects=selected_subject,
                is_active=True
            ).distinct().order_by("admission_number")

            existing_results_qs = StudentResult.objects.filter(
                exam=exam,
                subject=selected_subject,
                student__in=students
            ).select_related("student")

            existing_results = {
                result.student_id: result
                for result in existing_results_qs
            }

        except Subject.DoesNotExist:
            messages.error(request, "Selected subject does not exist.")

    if request.method == "POST":
        subject_id = request.POST.get("subject_id")

        if subject_id:
            selected_subject = get_object_or_404(
                Subject,
                pk=subject_id,
                is_active=True
            )

            students = exam.get_students_for_exam().filter(
                subjects=selected_subject,
                is_active=True
            ).distinct()

            saved_count = 0

            for student in students:
                score_key = f"score_{student.id}"

                if score_key in request.POST:
                    score = request.POST.get(score_key)

                    if score and score.strip():
                        try:
                            score_value = float(score)

                            if 0 <= score_value <= (exam.max_score or 100):
                                StudentResult.objects.update_or_create(
                                    student=student,
                                    exam=exam,
                                    subject=selected_subject,
                                    defaults={
                                        "score": score_value,
                                        "entered_by": request.user,
                                    }
                                )

                                saved_count += 1

                        except ValueError:
                            pass

            if saved_count > 0:
                messages.success(
                    request,
                    f"Results for {exam.name} - {selected_subject.name} saved successfully!"
                )
            else:
                messages.warning(request, "No results were saved.")

            return redirect(f"{request.path}?subject={subject_id}")

    context = {
        "tenant_schema": tenant_schema,
        "active_schema": current_schema,

        "exam": exam,
        "subjects": subjects,
        "selected_subject": selected_subject,
        "students": students,
        "existing_results": existing_results,

        "title": f"Enter Results - {exam.name}",
        "school": SchoolSetting.objects.first(),
    }

    return render(request, "performance/exam_results_entry.html", context)
# ========== EXPORT EXAM PERFORMANCE VIEW ==========

import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Max, Min
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import (
    Exam,
    ExamResultSummary,
    Student,
    StudentResult,
    Subject,
)


@login_required
def export_exam_performance(
    request,
    tenant_schema=None,
    exam_id=None,
    *args,
    **kwargs,
):
    """Export exam performance to CSV in a tenant-aware route."""

    tenant_schema = resolve_tenant_schema(request, tenant_schema)

    if exam_id is None:
        raise Http404("Exam ID is required.")

    exam = get_object_or_404(Exam, id=exam_id)

    if exam.student_class:
        students = exam.student_class.students.filter(
            is_active=True
        ).order_by("first_name", "last_name")
    else:
        students = Student.objects.filter(
            is_active=True
        ).order_by("first_name", "last_name")

    subjects = Subject.objects.all().order_by("name")

    results = StudentResult.objects.filter(
        exam=exam,
        student__in=students,
    ).select_related("student", "subject")

    response = HttpResponse(
        content_type="text/csv; charset=utf-8"
    )

    safe_exam_name = "".join(
        character
        for character in exam.name
        if character.isalnum() or character in (" ", "-", "_")
    ).strip().replace(" ", "_")

    response["Content-Disposition"] = (
        f'attachment; filename="{safe_exam_name}_performance.csv"'
    )

    # Add UTF-8 BOM so Excel opens names correctly.
    response.write("\ufeff")

    writer = csv.writer(response)

    header = [
        "Rank",
        "Admission Number",
        "Student Name",
    ]

    header.extend(subject.name for subject in subjects)

    header.extend([
        "Total Score",
        "Average Score",
        "Grade",
        "Status",
    ])

    writer.writerow(header)

    rankings = []

    for student in students:
        student_results = list(
            results.filter(student=student)
        )

        if not student_results:
            continue

        result_by_subject = {
            result.subject_id: result
            for result in student_results
        }

        scores = []

        for subject in subjects:
            subject_result = result_by_subject.get(subject.id)

            scores.append(
                subject_result.score
                if subject_result is not None
                else ""
            )

        numeric_scores = [
            result.score
            for result in student_results
            if result.score is not None
        ]

        if not numeric_scores:
            continue

        total = sum(numeric_scores)
        average = total / len(numeric_scores)

        if average >= 80:
            grade = "A"
        elif average >= 70:
            grade = "B"
        elif average >= 60:
            grade = "C"
        elif average >= 50:
            grade = "D"
        else:
            grade = "E"

        status = "Pass" if average >= 50 else "Fail"

        rankings.append({
            "student": student,
            "scores": scores,
            "total": total,
            "average": average,
            "grade": grade,
            "status": status,
        })

    rankings.sort(
        key=lambda item: item["average"],
        reverse=True,
    )

    for rank, ranking in enumerate(rankings, start=1):
        student = ranking["student"]

        row = [
            rank,
            student.admission_number,
            student.get_full_name(),
        ]

        row.extend(ranking["scores"])

        row.extend([
            ranking["total"],
            f'{ranking["average"]:.1f}',
            ranking["grade"],
            ranking["status"],
        ])

        writer.writerow(row)

    return response


@login_required
def export_performance_report(
    request,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """Export the filtered performance report to CSV."""

    tenant_schema = resolve_tenant_schema(request, tenant_schema)

    academic_year = request.GET.get("year", "").strip()
    term = request.GET.get("term", "").strip()
    selected_class = request.GET.get("class", "").strip()
    selected_exam = request.GET.get("exam", "").strip()

    results_qs = StudentResult.objects.select_related(
        "student",
        "student__current_class",
        "exam",
    )

    if academic_year:
        results_qs = results_qs.filter(
            exam__academic_year=academic_year
        )

    if term:
        results_qs = results_qs.filter(
            exam__term=term
        )

    if selected_class:
        results_qs = results_qs.filter(
            student__current_class_id=selected_class
        )

    if selected_exam:
        results_qs = results_qs.filter(
            exam_id=selected_exam
        )

    top_students = (
        results_qs.values("student_id")
        .annotate(avg=Avg("score"))
        .order_by("-avg")
    )

    response = HttpResponse(
        content_type="text/csv; charset=utf-8"
    )

    response["Content-Disposition"] = (
        'attachment; filename="performance_report.csv"'
    )

    response.write("\ufeff")

    writer = csv.writer(response)

    writer.writerow([
        "Rank",
        "Admission Number",
        "Student Name",
        "Class",
        "Average Score",
        "Grade",
    ])

    students_by_id = {
        student.id: student
        for student in Student.objects.filter(
            id__in=[
                item["student_id"]
                for item in top_students
            ]
        ).select_related("current_class")
    }

    for rank, summary in enumerate(top_students, start=1):
        student = students_by_id.get(
            summary["student_id"]
        )

        if not student:
            continue

        average = summary["avg"] or 0

        if average >= 80:
            grade = "A"
        elif average >= 70:
            grade = "B"
        elif average >= 60:
            grade = "C"
        elif average >= 50:
            grade = "D"
        else:
            grade = "E"

        writer.writerow([
            rank,
            student.admission_number,
            student.get_full_name(),
            (
                student.current_class.name
                if student.current_class
                else "N/A"
            ),
            f"{average:.1f}",
            grade,
        ])

    return response


@login_required
def export_ranking_csv(
    request,
    tenant_schema=None,
    exam_id=None,
    *args,
    **kwargs,
):
    """Export exam rankings to CSV in a tenant-aware route."""

    tenant_schema = resolve_tenant_schema(request, tenant_schema)

    if exam_id is None:
        raise Http404("Exam ID is required.")

    exam = get_object_or_404(Exam, id=exam_id)

    rankings = (
        ExamResultSummary.objects.filter(exam=exam)
        .select_related("student")
        .order_by("rank", "-average_score")
    )

    response = HttpResponse(
        content_type="text/csv; charset=utf-8"
    )

    safe_exam_name = "".join(
        character
        for character in exam.name
        if character.isalnum() or character in (" ", "-", "_")
    ).strip().replace(" ", "_")

    response["Content-Disposition"] = (
        f'attachment; filename="{safe_exam_name}_rankings.csv"'
    )

    response.write("\ufeff")

    writer = csv.writer(response)

    writer.writerow([
        "Rank",
        "Admission Number",
        "Student Name",
        "Total Score",
        "Average Score",
        "Grade",
    ])

    for ranking in rankings:
        writer.writerow([
            ranking.rank,
            ranking.student.admission_number,
            ranking.student.get_full_name(),
            ranking.total_score,
            ranking.average_score,
            ranking.overall_grade,
        ])

    return response


@login_required
def subject_exam_performance_detail(
    request,
    tenant_schema=None,
    subject_id=None,
    exam_id=None,
    *args,
    **kwargs,
):
    """Show performance for one subject in one exam."""

    tenant_schema = resolve_tenant_schema(request, tenant_schema)

    if subject_id is None:
        raise Http404("Subject ID is required.")

    if exam_id is None:
        raise Http404("Exam ID is required.")

    subject = get_object_or_404(
        Subject,
        id=subject_id,
    )

    exam = get_object_or_404(
        Exam,
        id=exam_id,
    )

    results = (
        StudentResult.objects.filter(
            subject=subject,
            exam=exam,
        )
        .select_related("student")
        .order_by("-score")
    )

    statistics = results.aggregate(
        average=Avg("score"),
        highest=Max("score"),
        lowest=Min("score"),
    )

    total_students = results.count()
    avg_score = statistics["average"] or 0
    highest = statistics["highest"] or 0
    lowest = statistics["lowest"] or 0

    passed = results.filter(
        score__gte=50
    ).count()

    pass_rate = (
        passed / total_students * 100
        if total_students
        else 0
    )

    grade_distribution = {
        "A (80-100)": results.filter(
            score__gte=80
        ).count(),
        "B (70-79)": results.filter(
            score__gte=70,
            score__lt=80,
        ).count(),
        "C (60-69)": results.filter(
            score__gte=60,
            score__lt=70,
        ).count(),
        "D (50-59)": results.filter(
            score__gte=50,
            score__lt=60,
        ).count(),
        "E (0-49)": results.filter(
            score__lt=50,
        ).count(),
    }

    context = {
        "tenant_schema": tenant_schema,
        "subject": subject,
        "exam": exam,
        "results": results,
        "total_students": total_students,
        "avg_score": avg_score,
        "highest": highest,
        "lowest": lowest,
        "passed": passed,
        "pass_rate": pass_rate,
        "grade_distribution": grade_distribution,
    }

    return render(
        request,
        "performance/subject_exam_performance_detail.html",
        context,
    )


def subject_exam_performance(request, subject_id, exam_id):
    """View performance for a specific subject in an exam"""
    from .models import Subject, Exam, Result, Student
    
    subject = Subject.objects.get(id=subject_id)
    exam = Exam.objects.get(id=exam_id)
    
    results = Result.objects.filter(exam=exam, subject=subject).select_related('student')
    
    total_students = Student.objects.filter(is_active=True).count()
    avg_score = results.aggregate(avg=Avg('score'))['avg'] or 0
    top_score = results.aggregate(max=Avg('score'))['max'] or 0
    lowest_score = results.aggregate(min=Avg('score'))['min'] or 0
    
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
# ========== PARENT PORTAL VIEWS ==========

# ========== TENANT-SAFE PARENT PORTAL VIEWS ==========

from functools import wraps
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


# ------------------------------------------------------------
# Helper: normalize parent phone numbers
# ------------------------------------------------------------
def normalize_parent_phone(value):
    """
    Convert common Kenyan phone formats to one canonical format:
    0712345678, 254712345678 and +254712345678 -> 254712345678
    """
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())

    if digits.startswith("0") and len(digits) == 10:
        return "254" + digits[1:]

    if digits.startswith("7") and len(digits) == 9:
        return "254" + digits

    if digits.startswith("254") and len(digits) == 12:
        return digits

    return digits


def linked_students_for_phone(Student, phone):
    """
    Return active students whose primary or alternative parent phone
    matches the supplied phone after normalization.
    """
    normalized_phone = normalize_parent_phone(phone)

    matched_ids = []

    for student in Student.objects.filter(is_active=True).only(
        "id",
        "parent_phone",
        "parent_alternative_phone",
    ):
        primary_phone = normalize_parent_phone(student.parent_phone)
        alternative_phone = normalize_parent_phone(
            student.parent_alternative_phone
        )

        if normalized_phone in {primary_phone, alternative_phone}:
            matched_ids.append(student.id)

    return Student.objects.filter(id__in=matched_ids, is_active=True)


# ------------------------------------------------------------
# Helper: resolve tenant schema
# ------------------------------------------------------------
def resolve_tenant_schema(request, tenant_schema=None):
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    tenant_schema = str(tenant_schema).strip()

    if tenant_schema in ["", "public", "None", "none", "null", "undefined"]:
        tenant_schema = "nyaneje"

    request.tenant_schema = tenant_schema

    if hasattr(request, "session"):
        request.session["tenant_schema"] = tenant_schema
        request.session.modified = True

    return tenant_schema


def parent_base_context(request, tenant_schema=None):
    tenant_schema = resolve_tenant_schema(request, tenant_schema)
    tenant_base_url = f"/tenant/{tenant_schema}/app"

    return {
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "app_prefix": tenant_base_url,
        "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
        "parent_login_url": f"{tenant_base_url}/parent/login/",
        "parent_verify_otp_url": f"{tenant_base_url}/parent/verify-otp/",
        "parent_dashboard_url": f"{tenant_base_url}/parent/dashboard/",
        "parent_logout_url": f"{tenant_base_url}/parent/logout/",
    }


def parent_redirect(request, tenant_schema, path):
    tenant_schema = resolve_tenant_schema(request, tenant_schema)
    return redirect(f"/tenant/{tenant_schema}/app{path}")


# ------------------------------------------------------------
# Decorator: parent session required
# ------------------------------------------------------------
def parent_session_required(view_func):
    """Decorator to ensure parent session exists"""

    @wraps(view_func)
    def wrapper(request, tenant_schema=None, *args, **kwargs):
        tenant_schema = resolve_tenant_schema(request, tenant_schema)

        if not request.session.get("parent_phone"):
            messages.error(request, "Please login first.")
            return parent_redirect(request, tenant_schema, "/parent/login/")

        return view_func(request, tenant_schema=tenant_schema, *args, **kwargs)

    return wrapper


# ------------------------------------------------------------
# Parent Login
# ------------------------------------------------------------
def parent_login(request, tenant_schema=None, *args, **kwargs):
    """Parent login using phone number and OTP - tenant-safe"""

    from .forms import ParentLoginForm
    from .models import Student, ParentOTP

    tenant_schema = resolve_tenant_schema(request, tenant_schema)
    context_base = parent_base_context(request, tenant_schema)

    if request.method == "POST":
        form = ParentLoginForm(request.POST)

        if form.is_valid():
            phone = form.cleaned_data["phone"]

            phone = normalize_parent_phone(phone)
            students = linked_students_for_phone(Student, phone)

            if not students.exists():
                messages.error(request, "No student is linked to this phone number.")
                return parent_redirect(request, tenant_schema, "/parent/login/")

            otp_code = ParentOTP.generate_otp()
            expires_at = timezone.now() + timedelta(minutes=10)

            ParentOTP.objects.create(
                phone=phone,
                otp_code=otp_code,
                expires_at=expires_at,
            )

            request.session["parent_phone_pending"] = phone
            request.session["tenant_schema"] = tenant_schema
            request.session.modified = True

            message = f"Your ShuleHub Parent Portal verification code is: {otp_code}"

            if getattr(settings, "MOCK_SMS_MODE", True):
                messages.info(request, f"TEST MODE: Your OTP is: {otp_code}")
            else:
                try:
                    from .sms_utils import send_sms

                    result = send_sms(phone, message)

                    if result.get("success"):
                        messages.success(request, f"Verification code sent to {phone}")
                    else:
                        messages.error(
                            request,
                            f"SMS delivery failed. Please use this code: {otp_code}",
                        )

                except Exception:
                    messages.error(
                        request,
                        f"SMS service error. Please use this code: {otp_code}",
                    )

            return parent_redirect(request, tenant_schema, "/parent/verify-otp/")

    else:
        form = ParentLoginForm()

    context = {
        **context_base,
        "form": form,
        "title": "Parent Login",
    }

    return render(request, "parent_portal/parent_login.html", context)


# ------------------------------------------------------------
# Verify OTP
# ------------------------------------------------------------
def verify_parent_otp(request, tenant_schema=None, *args, **kwargs):
    """Verify OTP for parent login - tenant-safe"""

    from .forms import ParentOTPForm
    from .models import ParentOTP

    tenant_schema = resolve_tenant_schema(request, tenant_schema)
    context_base = parent_base_context(request, tenant_schema)

    phone = normalize_parent_phone(request.session.get("parent_phone_pending"))

    if not phone:
        messages.error(request, "Please enter your phone number first.")
        return parent_redirect(request, tenant_schema, "/parent/login/")

    if request.method == "POST":
        form = ParentOTPForm(request.POST)

        if form.is_valid():
            otp_code = form.cleaned_data["otp_code"]

            otp = ParentOTP.objects.filter(
                phone=phone,
                otp_code=otp_code,
                is_used=False,
            ).order_by("-created_at").first()

            if not otp:
                messages.error(request, "Invalid OTP code. Please try again.")
                return parent_redirect(request, tenant_schema, "/parent/verify-otp/")

            if otp.is_expired():
                messages.error(request, "OTP has expired. Please request a new one.")
                otp.delete()
                request.session.pop("parent_phone_pending", None)
                request.session.modified = True
                return parent_redirect(request, tenant_schema, "/parent/login/")

            otp.is_used = True
            otp.save(update_fields=["is_used"])

            request.session["parent_phone"] = phone
            request.session["tenant_schema"] = tenant_schema
            request.session.pop("parent_phone_pending", None)
            request.session.modified = True

            messages.success(request, "Login successful! Welcome to the Parent Portal.")
            return parent_redirect(request, tenant_schema, "/parent/dashboard/")

        else:
            messages.error(request, "Please enter a valid 6-digit OTP code.")

    else:
        form = ParentOTPForm()

    context = {
        **context_base,
        "form": form,
        "phone": phone,
        "title": "Verify OTP",
    }

    return render(request, "parent_portal/verify_parent_otp.html", context)


# ------------------------------------------------------------
# Parent Logout
# ------------------------------------------------------------
def parent_logout(request, tenant_schema=None, *args, **kwargs):
    """Parent logout - tenant-safe"""

    tenant_schema = resolve_tenant_schema(request, tenant_schema)

    request.session.pop("parent_phone", None)
    request.session.pop("parent_phone_pending", None)
    request.session["tenant_schema"] = tenant_schema
    request.session.modified = True

    messages.success(request, "You have been logged out.")
    return parent_redirect(request, tenant_schema, "/parent/login/")


# ------------------------------------------------------------
# Parent Dashboard
# ------------------------------------------------------------

def _parent_fee_summary(student, academic_year=None, term_number=None):
    """
    Return one consistent live fee summary for parent-facing pages.

    Rules:
    1. Historical arrears are calculated independently.
    2. Payments recorded for the selected term reduce that term's fees.
    3. Lifetime payments are reported separately for dashboard totals.
    4. Current-term payments are not mixed with payments from older terms.
    """
    from decimal import Decimal

    from django.db.models import Sum

    from .models import (
        FeePayment,
        FeeStructure,
        HistoricalArrears,
        Term,
    )

    zero = Decimal("0.00")

    def as_decimal(value):
        try:
            return Decimal(str(value or zero))
        except Exception:
            return zero

    selected_term = None

    if academic_year is not None and term_number is not None:
        try:
            normalized_term = int(term_number)
        except (TypeError, ValueError):
            normalized_term = None

        if normalized_term is not None:
            selected_term = (
                Term.objects.filter(
                    academic_year=str(academic_year),
                    term_number=normalized_term,
                )
                .order_by("-is_active", "-id")
                .first()
            )

    if selected_term is None:
        selected_term = (
            Term.objects.filter(is_active=True)
            .order_by(
                "-academic_year",
                "-term_number",
                "-id",
            )
            .first()
        )

    if selected_term is None:
        selected_term = (
            Term.objects.order_by(
                "-academic_year",
                "-term_number",
                "-id",
            )
            .first()
        )

    if selected_term:
        academic_year = selected_term.academic_year
        term_number = selected_term.term_number

    total_expected = zero
    term_paid = zero

    expected_getter = getattr(
        student,
        "get_total_fees_expected",
        None,
    )

    paid_getter = getattr(
        student,
        "get_total_fees_paid",
        None,
    )

    if selected_term and callable(expected_getter):
        try:
            total_expected = as_decimal(
                expected_getter(
                    academic_year,
                    term_number,
                )
            )
        except Exception:
            total_expected = zero

    if selected_term and total_expected == zero:
        total_expected = sum(
            (
                as_decimal(item.total_fees)
                for item in FeeStructure.objects.filter(
                    student_class=student.current_class,
                    academic_year=academic_year,
                    term=term_number,
                )
            ),
            zero,
        )

    if selected_term and callable(paid_getter):
        try:
            term_paid = as_decimal(
                paid_getter(
                    academic_year,
                    term_number,
                )
            )
        except Exception:
            term_paid = zero

    if selected_term and term_paid == zero:
        term_paid = as_decimal(
            FeePayment.objects.filter(
                student=student,
                academic_year=academic_year,
                term=term_number,
            ).aggregate(
                total=Sum("amount")
            )["total"]
        )

    total_paid_all_time = as_decimal(
        FeePayment.objects.filter(
            student=student,
        ).aggregate(
            total=Sum("amount")
        )["total"]
    )

    original_historical_arrears = as_decimal(
        HistoricalArrears.objects.filter(
            student=student,
        ).aggregate(
            total=Sum("amount")
        )["total"]
    )

    unsettled_historical_arrears = as_decimal(
        HistoricalArrears.objects.filter(
            student=student,
            is_settled=False,
        ).aggregate(
            total=Sum("amount")
        )["total"]
    )

    # Current-term payments reduce current-term fees only.
    payment_applied_to_current = min(
        term_paid,
        total_expected,
    )

    current_balance = max(
        total_expected - payment_applied_to_current,
        zero,
    )

    current_term_credit = max(
        term_paid - total_expected,
        zero,
    )

    # Remaining arrears should come from unsettled arrears records.
    historical_arrears = max(
        unsettled_historical_arrears,
        zero,
    )

    total_outstanding = max(
        historical_arrears + current_balance,
        zero,
    )

    if current_term_credit > zero and historical_arrears == zero:
        fee_status = "OVERPAID"
    elif total_outstanding == zero:
        fee_status = "PAID"
    elif term_paid > zero or total_paid_all_time > zero:
        fee_status = "PARTIAL"
    else:
        fee_status = "DEFAULTING"

    return {
        "current_term": selected_term,
        "academic_year": academic_year,
        "term_number": term_number,
        "total_expected": total_expected,
        "term_paid": term_paid,
        "total_paid": total_paid_all_time,
        "original_historical_arrears": (
            original_historical_arrears
        ),
        "payment_applied_to_arrears": (
            original_historical_arrears
            - historical_arrears
        ),
        "payment_applied_to_current": (
            payment_applied_to_current
        ),
        "historical_arrears": historical_arrears,
        "current_balance": current_balance,
        "total_outstanding": total_outstanding,
        "credit": current_term_credit,
        "fee_status": fee_status,
    }


@parent_session_required
def parent_dashboard(request, tenant_schema=None, *args, **kwargs):
    """Parent dashboard with live, tenant-safe fee information."""
    from decimal import Decimal

    from django.db import connection
    from django.db.models import Q
    from django.shortcuts import render
    from django.urls import reverse
    from django.utils import timezone
    from django_tenants.utils import schema_context

    from .models import (
        Announcement,
        FeeBalance,
        PerformanceSummary,
        SchoolSetting,
        Student,
        StudentResult,
    )

    schema_name = resolve_tenant_schema(
        request,
        tenant_schema,
    )

    if not schema_name or schema_name == "public":
        schema_name = getattr(
            connection,
            "schema_name",
            None,
        )

    context_base = parent_base_context(
        request,
        schema_name,
    )

    tenant_base_url = context_base["tenant_base_url"]

    phone = normalize_parent_phone(
        request.session.get("parent_phone")
    )

    with schema_context(schema_name):
        students = (
            linked_students_for_phone(
                Student,
                phone,
            )
            .select_related("current_class")
            .prefetch_related("subjects")
        )

        students_data = []
        total_fees_paid = Decimal("0.00")
        total_results = 0
        parent_name = None
        dashboard_term = None

        def tenantize(path):
            """
            Prefix app-level parent URLs with the current tenant path.

            Child parent routes are registered as /app/parent/... and do not
            accept tenant_schema in reverse(). The middleware expects the final
            browser URL to include /tenant/<schema>/.
            """
            if path.startswith(
                f"/tenant/{schema_name}/"
            ):
                return path

            if path.startswith("/app/"):
                return (
                    f"/tenant/{schema_name}{path}"
                )

            if path.startswith("/"):
                return f"{tenant_base_url}{path}"

            return f"{tenant_base_url}/{path}"

        for student in students:
            if not parent_name:
                parent_name = (
                    student.parent_name
                    or "Parent"
                )

            fee = _parent_fee_summary(student)

            if dashboard_term is None:
                dashboard_term = fee["current_term"]

            if fee["current_term"]:
                FeeBalance.objects.update_or_create(
                    student=student,
                    academic_year=fee["academic_year"],
                    term=fee["term_number"],
                    defaults={
                        "total_expected": (
                            fee["total_expected"]
                        ),
                        "total_paid": (
                            fee["term_paid"]
                        ),
                        "balance": (
                            fee["current_balance"]
                        ),
                        "status": fee["fee_status"],
                    },
                )

            total_fees_paid += fee["total_paid"]

            results_count = (
                StudentResult.objects.filter(
                    student=student,
                )
                .values("exam_id")
                .distinct()
                .count()
            )

            total_results += results_count

            subject_count = (
                student.subjects.count()
                or 8
            )

            performance = "Good"

            latest_performance = (
                PerformanceSummary.objects.filter(
                    student=student,
                )
                .order_by(
                    "-academic_year",
                    "-term",
                )
                .first()
            )

            if latest_performance:
                average_score = (
                    latest_performance.average_score
                    or Decimal("0.00")
                )

                if average_score >= 80:
                    performance = "Excellent"
                elif average_score >= 70:
                    performance = "Very Good"
                elif average_score >= 60:
                    performance = "Good"
                elif average_score >= 50:
                    performance = "Average"
                else:
                    performance = (
                        "Needs Improvement"
                    )

            detail_url = tenantize(
                reverse(
                    "digitallibrary:parent_student_detail",
                    kwargs={
                        "student_id": student.id,
                    },
                )
            )

            results_url = tenantize(
                reverse(
                    "digitallibrary:parent_results",
                    kwargs={
                        "student_id": student.id,
                    },
                )
            )

            fee_statement_url = tenantize(
                reverse(
                    "digitallibrary:parent_fee_statement",
                    kwargs={
                        "student_id": student.id,
                    },
                )
            )

            mpesa_url = tenantize(
                reverse(
                    "digitallibrary:parent_pay_fees",
                    kwargs={
                        "student_id": student.id,
                    },
                )
            )

            students_data.append({
                "student": student,
                **fee,
                "results_count": results_count,
                "subject_count": subject_count,
                "performance": performance,
                "detail_url": detail_url,
                "results_url": results_url,
                "fee_statement_url": (
                    fee_statement_url
                ),
                "mpesa_url": mpesa_url,
            })

        school = SchoolSetting.objects.first()

        announcements = (
            Announcement.objects.filter(
                Q(target_audience="all")
                | Q(target_audience="parents"),
                Q(expires_at__isnull=True)
                | Q(expires_at__gt=timezone.now()),
            )
            .order_by("-created_at")[:5]
        )

        context = {
            **context_base,
            "students_data": students_data,
            "students": students,
            "total_fees_paid": total_fees_paid,
            "total_results": total_results,
            "students_count": students.count(),
            "parent_name": parent_name or "Parent",
            "title": "Parent Dashboard",
            "school": school,
            "current_term": dashboard_term,
            "announcements": announcements,
            "notifications": announcements,
            "tenant_schema": schema_name,
        }

        return render(
            request,
            "parent_portal/parent_dashboard.html",
            context,
        )



# ------------------------------------------------------------
# Parent Fee Detail
# ------------------------------------------------------------
@parent_session_required
def parent_fee_detail(
    request,
    tenant_schema=None,
    student_id=None,
    *args,
    **kwargs,
):
    """Detailed parent fee page using the shared live calculation."""
    from django.contrib import messages
    from django.db import connection
    from django.shortcuts import render
    from django_tenants.utils import schema_context

    from .models import (
        FeeBalance,
        FeePayment,
        FeeStructure,
        SchoolSetting,
        Student,
        Term,
    )

    schema_name = resolve_tenant_schema(request, tenant_schema)

    if not schema_name or schema_name == "public":
        schema_name = getattr(connection, "schema_name", None)

    context_base = parent_base_context(request, schema_name)
    phone = normalize_parent_phone(
        request.session.get("parent_phone")
    )

    with schema_context(schema_name):
        try:
            student = linked_students_for_phone(
                Student,
                phone,
            ).get(id=student_id)
        except Student.DoesNotExist:
            messages.error(
                request,
                "Student not found or not linked to your account.",
            )
            return parent_redirect(
                request,
                schema_name,
                "/parent/dashboard/",
            )

        fee = _parent_fee_summary(
            student,
            request.GET.get("academic_year"),
            request.GET.get("term"),
        )

        fee_structures = FeeStructure.objects.filter(
            student_class=student.current_class,
            academic_year=fee["academic_year"],
            term=fee["term_number"],
        )

        payments = FeePayment.objects.filter(
            student=student,
        ).order_by("-payment_date", "-created_at")

        fee_breakdown = []
        for structure in fee_structures:
            components = structure.custom_fees.all()

            if components.exists():
                for component in components:
                    fee_breakdown.append({
                        "name": component.name,
                        "amount": component.amount,
                    })
            else:
                fee_breakdown.append({
                    "name": f"Term {structure.term} Fees",
                    "amount": structure.total_fees,
                })

        if fee["current_term"]:
            FeeBalance.objects.update_or_create(
                student=student,
                academic_year=fee["academic_year"],
                term=fee["term_number"],
                defaults={
                    "total_expected": fee["total_expected"],
                    "total_paid": fee["payment_applied_to_current"],
                    "balance": fee["current_balance"],
                    "status": fee["fee_status"],
                },
            )

        context = {
            **context_base,
            "student": student,
            **fee,
            "payments": payments,
            "fee_breakdown": fee_breakdown,
            "terms": Term.objects.all().order_by(
                "-academic_year",
                "-term_number",
            ),
            "school": SchoolSetting.objects.first(),
        }

        return render(
            request,
            "parent_portal/fee_detail.html",
            context,
        )


# ------------------------------------------------------------
# Parent Student Detail
# ------------------------------------------------------------
@parent_session_required
def parent_student_detail(
    request,
    tenant_schema=None,
    student_id=None,
    *args,
    **kwargs,
):
    """View a linked student with live fee and result information."""
    from django.db import connection
    from django.shortcuts import get_object_or_404, render
    from django_tenants.utils import schema_context

    from .models import (
        FeeBalance,
        FeePayment,
        SchoolSetting,
        Student,
        StudentResult,
    )

    schema_name = resolve_tenant_schema(request, tenant_schema)

    if not schema_name or schema_name == "public":
        schema_name = getattr(connection, "schema_name", None)

    context_base = parent_base_context(request, schema_name)
    phone = normalize_parent_phone(
        request.session.get("parent_phone")
    )

    with schema_context(schema_name):
        students = linked_students_for_phone(Student, phone)
        student = get_object_or_404(students, id=student_id)
        fee = _parent_fee_summary(student)

        context = {
            **context_base,
            "student": student,
            **fee,
            "fee_balances": FeeBalance.objects.filter(
                student=student,
            ).order_by("-academic_year", "-term"),
            "payments": FeePayment.objects.filter(
                student=student,
            ).order_by("-payment_date", "-created_at")[:10],
            "results": StudentResult.objects.filter(
                student=student,
            )
            .select_related("exam", "subject")
            .order_by(
                "-exam__academic_year",
                "-exam__term",
                "subject__name",
            )[:20],
            "title": student.get_full_name(),
            "school": SchoolSetting.objects.first(),
        }

        return render(
            request,
            "parent_portal/parent_student_detail.html",
            context,
        )


# ------------------------------------------------------------
# Parent Fee Statement
# ------------------------------------------------------------
@parent_session_required
def parent_fee_statement(
    request,
    tenant_schema=None,
    student_id=None,
    *args,
    **kwargs,
):
    """View a linked student's statement with a live fee summary."""
    from django.db import connection
    from django.shortcuts import get_object_or_404, render
    from django_tenants.utils import schema_context

    from .models import (
        FeeBalance,
        FeePayment,
        SchoolSetting,
        Student,
    )

    schema_name = resolve_tenant_schema(request, tenant_schema)

    if not schema_name or schema_name == "public":
        schema_name = getattr(connection, "schema_name", None)

    context_base = parent_base_context(request, schema_name)
    phone = normalize_parent_phone(
        request.session.get("parent_phone")
    )

    with schema_context(schema_name):
        students = linked_students_for_phone(Student, phone)
        student = get_object_or_404(students, id=student_id)
        fee = _parent_fee_summary(student)

        context = {
            **context_base,
            "student": student,
            **fee,
            "fee_balances": FeeBalance.objects.filter(
                student=student,
            ).order_by("-academic_year", "-term"),
            "payments": FeePayment.objects.filter(
                student=student,
            ).order_by("-payment_date", "-created_at"),
            "title": "Fee Statement",
            "school": SchoolSetting.objects.first(),
        }

        return render(
            request,
            "parent_portal/parent_fee_statement.html",
            context,
        )


# ------------------------------------------------------------
# Parent Results
# ------------------------------------------------------------
@parent_session_required
def parent_results(request, tenant_schema=None, student_id=None, *args, **kwargs):
    """View results for a student - tenant-safe"""

    from .models import Student, StudentResult, SchoolSetting

    tenant_schema = resolve_tenant_schema(request, tenant_schema)
    context_base = parent_base_context(request, tenant_schema)

    phone = normalize_parent_phone(request.session.get("parent_phone"))

    students = linked_students_for_phone(Student, phone)

    student = get_object_or_404(students, id=student_id)

    results = StudentResult.objects.filter(
        student=student,
    ).select_related("exam", "subject").order_by(
        "-exam__academic_year",
        "-exam__term",
        "subject__name",
    )

    school = SchoolSetting.objects.first()

    context = {
        **context_base,
        "student": student,
        "results": results,
        "title": "Results",
        "school": school,
    }

    return render(request, "parent_portal/parent_results.html", context)


# ------------------------------------------------------------
# Parent Pay Fees
# ------------------------------------------------------------
@parent_session_required
def parent_pay_fees(
    request,
    tenant_schema=None,
    student_id=None,
    *args,
    **kwargs,
):
    """Display the tenant-safe parent fee payment page."""

    from decimal import Decimal

    from django.shortcuts import get_object_or_404, render

    from .models import FeePayment, SchoolSetting, Student

    tenant_schema = resolve_tenant_schema(
        request,
        tenant_schema,
    )

    context_base = parent_base_context(
        request,
        tenant_schema,
    )

    phone = normalize_parent_phone(
        request.session.get("parent_phone")
    )

    students = linked_students_for_phone(
        Student,
        phone,
    )

    student = get_object_or_404(
        students,
        id=student_id,
    )

    # Use the same live calculation as the dashboard and fee detail page.
    fee_summary = _parent_fee_summary(student)

    recent_payments = (
        FeePayment.objects.filter(student=student)
        .order_by("-payment_date", "-created_at")[:10]
    )

    minimum_payment = Decimal("1000.00")
    total_outstanding = fee_summary["total_outstanding"]

    # Allow full settlement where the remaining balance is below KES 1,000.
    if (
        total_outstanding > Decimal("0.00")
        and total_outstanding < minimum_payment
    ):
        minimum_payment = total_outstanding

    school = SchoolSetting.objects.first()

    context = {
        **context_base,
        **fee_summary,
        "student": student,
        "recent_payments": recent_payments,
        "minimum_payment": minimum_payment,
        "school": school,
        "title": "Pay Fees",
        "tenant_schema": tenant_schema,

        # Compatibility with any older template variables.
        "balance": total_outstanding,
        "total_fees": fee_summary["total_expected"],
    }

    return render(
        request,
        "parent_portal/parent_pay_fees.html",
        context,
    )

# ------------------------------------------------------------
# Parent View Grades
# ------------------------------------------------------------
@parent_session_required
def parent_view_grades(request, tenant_schema=None, *args, **kwargs):
    """Show all grades for parent's children - tenant-safe"""

    from .models import Student, SchoolSetting

    tenant_schema = resolve_tenant_schema(request, tenant_schema)
    context_base = parent_base_context(request, tenant_schema)

    phone = normalize_parent_phone(request.session.get("parent_phone"))

    children = linked_students_for_phone(Student, phone)

    school = SchoolSetting.objects.first()

    context = {
        **context_base,
        "children": children,
        "school": school,
    }

    return render(request, "digitallibrary/parent_grades.html", context)


# ------------------------------------------------------------
# Parent View Attendance
# ------------------------------------------------------------
@parent_session_required
def parent_view_attendance(request, tenant_schema=None, *args, **kwargs):
    """Show attendance records for parent's children - tenant-safe"""

    from .models import Student, SchoolSetting

    tenant_schema = resolve_tenant_schema(request, tenant_schema)
    context_base = parent_base_context(request, tenant_schema)

    phone = normalize_parent_phone(request.session.get("parent_phone"))

    children = linked_students_for_phone(Student, phone)

    school = SchoolSetting.objects.first()

    context = {
        **context_base,
        "children": children,
        "school": school,
    }

    return render(request, "digitallibrary/parent_attendance.html", context)


# ------------------------------------------------------------
# Parent Fee Balance
# ------------------------------------------------------------
@parent_session_required
def parent_fee_balance(
    request,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """Show live fee summaries for all children linked to the parent."""
    from django.db import connection
    from django.shortcuts import render
    from django_tenants.utils import schema_context

    from .models import SchoolSetting, Student

    schema_name = resolve_tenant_schema(request, tenant_schema)

    if not schema_name or schema_name == "public":
        schema_name = getattr(connection, "schema_name", None)

    context_base = parent_base_context(request, schema_name)
    phone = normalize_parent_phone(
        request.session.get("parent_phone")
    )

    with schema_context(schema_name):
        children = (
            linked_students_for_phone(Student, phone)
            .select_related("current_class")
        )

        children_data = [
            {
                "student": child,
                **_parent_fee_summary(child),
            }
            for child in children
        ]

        context = {
            **context_base,
            "children": children,
            "children_data": children_data,
            "school": SchoolSetting.objects.first(),
            "title": "Fee Balances",
        }

        return render(
            request,
            "digitallibrary/parent_fee.html",
            context,
        )



# ------------------------------------------------------------
# Parent Resend OTP
# ------------------------------------------------------------
@csrf_exempt
@require_POST
def parent_resend_otp(request, tenant_schema=None, *args, **kwargs):
    """Resend OTP to parent phone number - tenant-safe"""

    import json
    import random

    from .models import ParentOTP, Student

    tenant_schema = resolve_tenant_schema(request, tenant_schema)

    try:
        data = json.loads(request.body)
        phone = data.get("phone", "")

        if not phone:
            return JsonResponse({
                "success": False,
                "error": "Phone number is required",
            })

        phone = normalize_parent_phone(phone)
        students = linked_students_for_phone(Student, phone)

        if not students.exists():
            return JsonResponse({
                "success": False,
                "error": "No student found with this phone number",
            })

        otp_code = str(random.randint(100000, 999999))
        expires_at = timezone.now() + timedelta(minutes=10)

        ParentOTP.objects.filter(phone=phone, is_used=False).delete()

        ParentOTP.objects.create(
            phone=phone,
            otp_code=otp_code,
            expires_at=expires_at,
            is_used=False,
        )

        message = f"Your ShuleHub Parent Portal verification code is: {otp_code}"

        if getattr(settings, "MOCK_SMS_MODE", True):
            return JsonResponse({
                "success": True,
                "message": "OTP sent successfully (TEST MODE)",
                "otp": otp_code,
            })

        from .sms_utils import send_sms

        result = send_sms(phone, message)

        if result.get("success"):
            return JsonResponse({
                "success": True,
                "message": "Verification code resent successfully",
            })

        return JsonResponse({
            "success": False,
            "error": result.get("error", "Failed to send SMS"),
        })

    except json.JSONDecodeError:
        return JsonResponse({
            "success": False,
            "error": "Invalid request",
        })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e),
        })
# digitallibrary/views_school.py

from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import SchoolSetting

@staff_member_required
def school_settings(request, tenant_schema=None, *args, **kwargs):
    """School settings page - tenant-safe version"""

    from django.shortcuts import render, redirect
    from django.contrib import messages
    from django.db import connection

    from .models import SchoolSetting

    # ------------------------------------------------------------
    # 1. Resolve tenant schema safely
    # ------------------------------------------------------------
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    tenant_schema = str(tenant_schema).strip()

    if tenant_schema in ["", "public", "None", "none", "null", "undefined"]:
        tenant_schema = "nyaneje"

    request.tenant_schema = tenant_schema

    if hasattr(request, "session"):
        request.session["tenant_schema"] = tenant_schema
        request.session.modified = True

    tenant_base_url = f"/tenant/{tenant_schema}/app"
    tenant_school_settings_url = f"{tenant_base_url}/school-settings/"
    tenant_dashboard_url = f"{tenant_base_url}/dashboard/"

    # ------------------------------------------------------------
    # 2. Get or create school settings
    # ------------------------------------------------------------
    setting = SchoolSetting.objects.first()

    if not setting:
        create_kwargs = {
            "name": f"{tenant_schema.title()} School",
            "motto": "Excellence in Education",
            "phone": "",
            "email": "",
            "address": "",
            "website": "",
        }

        field_names = {field.name for field in SchoolSetting._meta.fields}

        if "school_name" in field_names:
            create_kwargs["school_name"] = f"{tenant_schema.title()} School"

        setting = SchoolSetting.objects.create(**create_kwargs)

    # ------------------------------------------------------------
    # 3. Handle update
    # ------------------------------------------------------------
    if request.method == "POST":
        setting.name = request.POST.get("name", setting.name or "")
        setting.motto = request.POST.get("motto", setting.motto or "")
        setting.phone = request.POST.get("phone", setting.phone or "")
        setting.email = request.POST.get("email", setting.email or "")
        setting.address = request.POST.get("address", setting.address or "")
        setting.website = request.POST.get("website", setting.website or "")

        if hasattr(setting, "school_name"):
            setting.school_name = request.POST.get("school_name") or setting.name

        if hasattr(setting, "primary_color"):
            setting.primary_color = request.POST.get("primary_color", setting.primary_color)

        if hasattr(setting, "secondary_color"):
            setting.secondary_color = request.POST.get("secondary_color", setting.secondary_color)

        if hasattr(setting, "accent_color"):
            setting.accent_color = request.POST.get("accent_color", setting.accent_color)

        if hasattr(setting, "timezone"):
            setting.timezone = request.POST.get("timezone", setting.timezone or "Africa/Nairobi")

        if hasattr(setting, "currency"):
            setting.currency = request.POST.get("currency", setting.currency or "KES")

        if request.FILES.get("logo"):
            setting.logo = request.FILES["logo"]

        setting.save()

        messages.success(request, "School settings updated successfully!")

        # IMPORTANT:
        # Redirect to tenant URL, not /app/school-settings/
        return redirect(tenant_school_settings_url)

    # ------------------------------------------------------------
    # 4. Render page
    # ------------------------------------------------------------
    context = {
        "setting": setting,
        "school_setting": setting,
        "school_settings": setting,

        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_base_url": tenant_base_url,

        "tenant_school_settings_url": tenant_school_settings_url,
        "tenant_dashboard_url": tenant_dashboard_url,
    }

    return render(request, "digitallibrary/school_settings.html", context)
# =========================
# GRADING SYSTEM VIEWS
# =========================

@staff_member_required
def set_grading_preference(request, tenant_schema=None, exam_id=None):
    """Set the grading system preference for this exam session"""

    from django.shortcuts import redirect, get_object_or_404
    from django.contrib import messages
    from django_tenants.utils import schema_context
    from .models import Exam, Subject, GradingSystem, TeacherGradingPreference

    # ------------------------------------------------------------
    # Detect tenant schema safely
    # ------------------------------------------------------------
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
    )

    # Fallback from URL path: /tenant/nyaneje/app/...
    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    print(f"\n{'=' * 60}")
    print("🔧 set_grading_preference called")
    print(f"   schema_name: {schema_name}")
    print(f"   exam_id: {exam_id}")
    print(f"   Method: {request.method}")
    print(f"   Path: {request.path}")
    print(f"   POST params: {dict(request.POST)}")
    print(f"{'=' * 60}")

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "Tenant context was not detected. Please open this page from the school dashboard."
        )
        return redirect("/")

    with schema_context(schema_name):

        exam = get_object_or_404(Exam, id=exam_id)

        subject_id = request.GET.get("subject") or request.POST.get("subject_id")
        subject = None

        if subject_id and subject_id != "None":
            subject = get_object_or_404(Subject, id=subject_id)

        if request.method == "POST":
            grading_system_id = request.POST.get("grading_system_id")

            print(f"   grading_system_id: '{grading_system_id}'")
            print(f"   subject_id: '{subject_id}'")

            # Get or create teacher preference
            preference, created = TeacherGradingPreference.objects.get_or_create(
                teacher=request.user,
                exam=exam,
                subject=subject,
            )

            # ----------------------------------------------------
            # 1. CBE grading system
            # ----------------------------------------------------
            if grading_system_id == "cbe":
                preference.use_cbe_pathways = True
                preference.use_custom_grading = False
                preference.custom_grading_system = None

                request.session["active_grading_system_id"] = "cbe"

                messages.success(
                    request,
                    "✓ CBE Grading System Activated (EE1, EE2, ME1, ME2, AE2, AE1, BE2, BE1)"
                )

                print("   Set session: active_grading_system_id = 'cbe'")

            # ----------------------------------------------------
            # 2. KCSE / traditional grading system
            # ----------------------------------------------------
            elif grading_system_id == "traditional" or grading_system_id == "kcse":
                preference.use_cbe_pathways = False
                preference.use_custom_grading = False
                preference.custom_grading_system = None

                request.session["active_grading_system_id"] = "traditional"

                messages.success(
                    request,
                    "✓ KCSE / Traditional Grading System Activated"
                )

                print("   Set session: active_grading_system_id = 'traditional'")

            # ----------------------------------------------------
            # 3. School-created custom grading system
            # ----------------------------------------------------
            elif grading_system_id:
                try:
                    grading_system = GradingSystem.objects.get(
                        id=int(grading_system_id),
                        is_active=True
                    )

                    preference.use_cbe_pathways = False
                    preference.use_custom_grading = True
                    preference.custom_grading_system = grading_system

                    request.session["active_grading_system_id"] = grading_system.id

                    messages.success(
                        request,
                        f"✓ {grading_system.name} Grading System Activated"
                    )

                    print(f"   Set session: active_grading_system_id = {grading_system.id}")

                except (GradingSystem.DoesNotExist, ValueError) as e:
                    messages.error(request, "Selected grading system not found.")
                    print(f"   ERROR: {e}")

            else:
                messages.error(request, "Please select a grading system.")
                print("   ERROR: No grading_system_id provided")

            preference.save()

            # Redirect back to tenant-safe results entry form
            redirect_url = f"/tenant/{schema_name}/app/enter-results-form/?exam={exam.id}"

            if subject_id and subject_id != "None":
                redirect_url += f"&subject={subject_id}"

            print(f"   Redirecting to: {redirect_url}")
            print(f"{'=' * 60}\n")

            return redirect(redirect_url)

        # For GET requests, redirect back to form
        redirect_url = f"/tenant/{schema_name}/app/enter-results-form/?exam={exam.id}"

        if subject_id and subject_id != "None":
            redirect_url += f"&subject={subject_id}"

        return redirect(redirect_url)

@login_required
def add_grading_scales(request, system_id):
    """Add grading scales to a custom grading system"""
    
    grading_system = get_object_or_404(GradingSystem, id=system_id, created_by=request.user)
    
    if request.method == 'POST':
        # Process grading scales
        grades = request.POST.getlist('grade')
        min_scores = request.POST.getlist('min_score')
        max_scores = request.POST.getlist('max_score')
        points = request.POST.getlist('points')
        remarks = request.POST.getlist('remark')
        
        # Delete existing grades
        grading_system.grades.all().delete()
        
        # Create new grades
        for i in range(len(grades)):
            if grades[i] and min_scores[i] and max_scores[i]:
                GradeScale.objects.create(
                    grading_system=grading_system,
                    grade=grades[i],
                    min_score=min_scores[i],
                    max_score=max_scores[i],
                    points=points[i] if points[i] else 0,
                    remark=remarks[i] if remarks[i] else ''
                )
        
        messages.success(request, f'Grading scales added to {grading_system.name}')
        return redirect('digitallibrary:set_grading_preference')
    
    # Default grade suggestions
    default_grades = [
        ('A', 80, 100, 12, 'Excellent'),
        ('B', 70, 79, 9, 'Good'),
        ('C', 60, 69, 6, 'Average'),
        ('D', 50, 59, 3, 'Below Average'),
        ('E', 0, 49, 1, 'Fail'),
    ]
    
    context = {
        'grading_system': grading_system,
        'default_grades': default_grades,
    }
    return render(request, 'digitallibrary/add_grading_scales.html', context)


def get_grade_for_score(score, exam=None, subject=None, student=None):
    """Get grade based on exam, subject, and student's CBE pathway if applicable"""
    
    # Check if student is in CBE pathway
    if student and hasattr(student, 'pathway') and student.pathway:
        try:
            cbe_pathway = CBEGradingPathway.objects.filter(
                pathway_type=student.pathway,
                is_active=True
            ).first()
            if cbe_pathway and cbe_pathway.grading_system:
                grade_obj = cbe_pathway.grading_system.grades.filter(
                    min_score__lte=score,
                    max_score__gte=score
                ).first()
                if grade_obj:
                    return grade_obj
        except:
            pass
    
    # Check for custom teacher grading
    if exam and subject:
        preference = TeacherGradingPreference.objects.filter(
            exam=exam,
            subject=subject
        ).first()
        
        if preference and preference.use_custom_grading and preference.custom_grading_system:
            grade_obj = preference.custom_grading_system.grades.filter(
                min_score__lte=score,
                max_score__gte=score
            ).first()
            if grade_obj:
                return grade_obj
    
    # Default grading system
    return Grade.objects.filter(
        min_score__lte=score,
        max_score__gte=score
    ).first()
from django.http import JsonResponse
from .models import Student, Exam, StudentResult, TeacherGradingPreference, CBEGradingPathway, GradeScale

@login_required
def api_calculate_grade(request):
    """API endpoint to calculate grade based on student's pathway and selected grading system"""
    if request.method == 'POST':
        data = json.loads(request.body)
        student_id = data.get('student_id')
        score = data.get('score')
        exam_id = data.get('exam_id')
        
        try:
            student = Student.objects.get(id=student_id)
            exam = Exam.objects.get(id=exam_id)
            
            # Check for grading preference
            preference = TeacherGradingPreference.objects.filter(
                exam=exam,
                subject__isnull=True
            ).first()
            
            grading_system = None
            
            if preference and preference.use_cbe_pathways:
                # Use CBE grading
                if student.pathway:
                    pathway = CBEGradingPathway.objects.filter(
                        pathway_type=student.pathway,
                        is_active=True
                    ).first()
                    if pathway:
                        grading_system = pathway.grading_system
            elif preference and preference.use_custom_grading:
                grading_system = preference.custom_grading_system
            
            # Calculate grade
            if grading_system:
                grade_scale = grading_system.grades.filter(
                    min_score__lte=score,
                    max_score__gte=score
                ).first()
                if grade_scale:
                    return JsonResponse({
                        'grade': grade_scale.grade,
                        'points': grade_scale.points,
                        'remark': grade_scale.remark,
                        'system': grading_system.system_type
                    })
            
            # Fallback to traditional grading
            percentage = (score / exam.max_score) * 100 if exam.max_score else score
            if percentage >= 80:
                return JsonResponse({'grade': 'A', 'points': 12})
            elif percentage >= 75:
                return JsonResponse({'grade': 'A-', 'points': 11})
            elif percentage >= 70:
                return JsonResponse({'grade': 'B+', 'points': 10})
            elif percentage >= 65:
                return JsonResponse({'grade': 'B', 'points': 9})
            elif percentage >= 60:
                return JsonResponse({'grade': 'B-', 'points': 8})
            elif percentage >= 55:
                return JsonResponse({'grade': 'C+', 'points': 7})
            elif percentage >= 50:
                return JsonResponse({'grade': 'C', 'points': 6})
            elif percentage >= 45:
                return JsonResponse({'grade': 'C-', 'points': 5})
            elif percentage >= 40:
                return JsonResponse({'grade': 'D+', 'points': 4})
            elif percentage >= 35:
                return JsonResponse({'grade': 'D', 'points': 3})
            elif percentage >= 30:
                return JsonResponse({'grade': 'D-', 'points': 2})
            else:
                return JsonResponse({'grade': 'E', 'points': 1})
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def generate_receipt(request, payment_id):
    """Generate PDF receipt for a payment"""
    payment = get_object_or_404(FeePayment, id=payment_id)
    
    # Check permission (admin, bursar, or the student's parent)
    if not (request.user.is_staff or 
            request.user.profile.role in ['admin', 'principal', 'bursar'] or
            (request.user.profile.role == 'parent' and payment.student in request.user.profile.children.all())):
        messages.error(request, 'You do not have permission to view this receipt')
        return redirect('digitallibrary:fees_dashboard')
    
    # Get school settings
    school = SchoolSetting.objects.first()
    
    # Calculate balance after this payment
    total_paid = FeePayment.objects.filter(student=payment.student).aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0.00')
    
    total_fees = FeeStructure.objects.filter(
        student_class=payment.student.current_class,
        academic_year=payment.academic_year,
        term=payment.term
    ).aggregate(total=models.Sum('total_fees'))['total'] or Decimal('0.00')
    
    balance = total_fees - total_paid
    
    context = {
        'payment': payment,
        'student': payment.student,
        'school': school,
        'total_paid': total_paid,
        'total_fees': total_fees,
        'balance': balance,
        'generated_date': timezone.now(),
        'generated_by': request.user,
    }
    
    # Render HTML template
    template = get_template('digitallibrary/receipt_template.html')
    html = template.render(context, request)
    
    # Create PDF
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        # Mark receipt as generated
        payment.receipt_generated = True
        payment.save()
        
        # Create HTTP response with PDF
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="receipt_{payment.receipt_number}.pdf"'
        return response
    
    return HttpResponse('Error generating PDF', status=500)


@login_required
def download_receipt(request, payment_id):
    """Download PDF receipt"""
    payment = get_object_or_404(FeePayment, id=payment_id)
    
    # Check permission
    if not (request.user.is_staff or 
            request.user.profile.role in ['admin', 'principal', 'bursar'] or
            (request.user.profile.role == 'parent' and payment.student in request.user.profile.children.all())):
        messages.error(request, 'You do not have permission to download this receipt')
        return redirect('digitallibrary:fees_dashboard')
    
    school = SchoolSetting.objects.first()
    
    total_paid = FeePayment.objects.filter(student=payment.student).aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0.00')
    
    total_fees = FeeStructure.objects.filter(
        student_class=payment.student.current_class,
        academic_year=payment.academic_year,
        term=payment.term
    ).aggregate(total=models.Sum('total_fees'))['total'] or Decimal('0.00')
    
    balance = total_fees - total_paid
    
    context = {
        'payment': payment,
        'student': payment.student,
        'school': school,
        'total_paid': total_paid,
        'total_fees': total_fees,
        'balance': balance,
        'generated_date': timezone.now(),
        'generated_by': request.user,
    }
    
    template = get_template('digitallibrary/receipt_template.html')
    html = template.render(context, request)
    
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="receipt_{payment.receipt_number}.pdf"'
        return response
    
    return HttpResponse('Error generating PDF', status=500)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from .models import Student, HistoricalArrears, Class, FeeBalance

@login_required
def add_historical_arrears(request, tenant_schema=None):
    """Add historical arrears for a student - tenant-safe version"""
    from decimal import Decimal
    from django.contrib import messages
    from django.shortcuts import render, redirect
    from django.db import connection

    # Import your models
    from .models import Student, Class, Term, HistoricalArrears

    # Resolve safe tenant schema
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"
    tenant_dashboard_url = f"{tenant_base_url}/dashboard/"
    tenant_historical_arrears_url = f"{tenant_base_url}/fees/historical-arrears/"

    # Prevent accidental public-schema access
    if getattr(connection, "schema_name", None) == "public":
        messages.error(request, "Historical arrears are only available inside a school tenant.")
        return redirect(tenant_dashboard_url)

    # Optional role protection
    try:
        user_role = request.user.profile.role
    except Exception:
        user_role = None

    if user_role not in ["admin", "principal", "bursar", "secretary"]:
        messages.error(request, "Access denied. You do not have permission to manage historical arrears.")
        return redirect(tenant_dashboard_url)

    # Initialize context
    context = {
        "student": None,
        "current_balance": 0,
        "classes": Class.objects.all().order_by("name"),
        "admission_no": "",
        "searched": False,

        # Tenant-safe context
        "tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "tenant_dashboard_url": tenant_dashboard_url,
        "tenant_historical_arrears_url": tenant_historical_arrears_url,
    }

    # Handle GET request - search for student
    if request.method == "GET" and "admission_no" in request.GET:
        admission_no = request.GET.get("admission_no", "").strip()

        context["admission_no"] = admission_no
        context["searched"] = True

        if admission_no:
            try:
                student = Student.objects.get(admission_number=admission_no)
                context["student"] = student

                latest_term = Term.objects.filter(is_active=True).first()

                if latest_term:
                    current_balance = student.get_fee_balance(
                        latest_term.academic_year,
                        latest_term.term_number
                    )
                    context["current_balance"] = current_balance
                else:
                    context["current_balance"] = 0

                messages.info(
                    request,
                    f"Student found: {student.first_name} {student.last_name}"
                )

            except Student.DoesNotExist:
                messages.error(
                    request,
                    f"No student found with admission number: {admission_no}"
                )
                context["student"] = None

    # Handle POST request - save historical arrears
    elif request.method == "POST":
        student_id = request.POST.get("student_id")
        amount = request.POST.get("amount")
        original_academic_year = request.POST.get("original_academic_year")
        original_class_id = request.POST.get("original_class_id")
        original_term = request.POST.get("original_term")
        notes = request.POST.get("notes", "")

        # Validate required fields
        if not all([student_id, amount, original_academic_year, original_class_id, original_term]):
            messages.error(request, "Please fill in all required fields")
            return redirect(tenant_historical_arrears_url)

        try:
            student = Student.objects.get(id=student_id)
            amount = Decimal(str(amount))
            original_class = Class.objects.get(id=original_class_id)
            original_term = int(original_term)

            if amount <= 0:
                messages.error(request, "Amount must be greater than zero.")
                return redirect(tenant_historical_arrears_url)

            HistoricalArrears.objects.create(
                student=student,
                amount=amount,
                original_class=original_class,
                original_academic_year=original_academic_year,
                original_term=original_term,
                notes=notes,
                added_by=request.user,
                is_settled=False
            )

            messages.success(
                request,
                f"Successfully added KES {amount:,.2f} historical arrears for {student.first_name} {student.last_name}"
            )

            return redirect(f"{tenant_base_url}/student/{student.id}/fee-detail/")

        except Student.DoesNotExist:
            messages.error(request, "Student not found")
            return redirect(tenant_historical_arrears_url)

        except Class.DoesNotExist:
            messages.error(request, "Selected class not found")
            return redirect(tenant_historical_arrears_url)

        except Exception as e:
            messages.error(request, f"Error adding arrears: {str(e)}")
            return redirect(tenant_historical_arrears_url)

    return render(request, "digitallibrary/fees/add_historical_arrears.html", context)
def student_fee_detail(
    request,
    tenant_schema=None,
    student_id=None,
    pk=None,
):
    """
    Display comprehensive fee details for a student.

    Payment allocation order:
    1. Oldest unsettled historical arrears
    2. Current-term fees
    3. Remaining amount becomes student credit
    """

    from decimal import Decimal

    from django.contrib import messages
    from django.db import connection
    from django.db.models import Sum
    from django.shortcuts import get_object_or_404, redirect, render
    from django_tenants.utils import schema_context

    from .models import (
        Student,
        Term,
        FeeBalance,
        HistoricalArrears,
        FeeStructure,
    )

    # Support both student_id and pk.
    student_id = student_id or pk

    if not student_id:
        messages.error(request, "No student was selected.")
        return redirect("/")

    # ------------------------------------------------------------
    # Detect the active tenant schema
    # ------------------------------------------------------------
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(
            getattr(request, "tenant", None),
            "schema_name",
            None,
        )
        or getattr(connection, "schema_name", None)
    )

    # Fallback for tenant-prefixed URLs:
    # /tenant/nyaneje/app/...
    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    # Do not silently use another school's schema.
    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "The school tenant could not be identified.",
        )
        return redirect("/")

    tenant_base_url = f"/tenant/{schema_name}/app"

    # ------------------------------------------------------------
    # Run all school-specific queries in the tenant schema
    # ------------------------------------------------------------
    with schema_context(schema_name):
        student = get_object_or_404(
            Student,
            id=student_id,
        )

        current_year = request.GET.get("academic_year")
        current_term = request.GET.get("term")

        # --------------------------------------------------------
        # Determine the selected academic year and term
        # --------------------------------------------------------
        if not current_year or not current_term:
            latest_term = (
                Term.objects.filter(is_active=True)
                .order_by(
                    "-academic_year",
                    "-term_number",
                )
                .first()
            )

            if not latest_term:
                latest_term = (
                    Term.objects.order_by(
                        "-academic_year",
                        "-term_number",
                    )
                    .first()
                )

            if latest_term:
                current_year = latest_term.academic_year
                current_term = latest_term.term_number
            else:
                current_year = "2026"
                current_term = 1

        try:
            current_term = int(current_term)
        except (TypeError, ValueError):
            current_term = 1

        # --------------------------------------------------------
        # Current-term expected fees and payments
        # --------------------------------------------------------
        total_expected = student.get_total_fees_expected(
            current_year,
            current_term,
        )

        total_paid = student.get_total_fees_paid(
            current_year,
            current_term,
        )

        total_expected = Decimal(str(total_expected or 0))
        total_paid = Decimal(str(total_paid or 0))

        # --------------------------------------------------------
        # Historical arrears
        # --------------------------------------------------------
        historical_arrears_queryset = (
            HistoricalArrears.objects.filter(
                student=student,
                is_settled=False,
            )
            .select_related(
                "original_class",
            )
            .order_by(
                "original_academic_year",
                "original_term",
                "created_at",
                "id",
            )
        )

        total_historical_arrears = (
            historical_arrears_queryset.aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )

        total_historical_arrears = Decimal(
            str(total_historical_arrears)
        )

        # --------------------------------------------------------
        # Allocate payments
        #
        # Payments first settle historical arrears, starting with
        # the oldest. Any remainder pays the current-term fees.
        # Any amount still left becomes credit.
        # --------------------------------------------------------
        remaining_payment = total_paid

        historical_payment_applied = min(
            remaining_payment,
            total_historical_arrears,
        )

        remaining_payment -= historical_payment_applied

        remaining_historical_arrears = (
            total_historical_arrears
            - historical_payment_applied
        )

        current_term_payment_applied = min(
            remaining_payment,
            total_expected,
        )

        remaining_payment -= current_term_payment_applied

        current_balance = (
            total_expected
            - current_term_payment_applied
        )

        credit_amount = max(
            remaining_payment,
            Decimal("0.00"),
        )

        total_due = (
            total_expected
            + total_historical_arrears
        )

        total_outstanding = (
            current_balance
            + remaining_historical_arrears
        )

        # Defensive protection: outstanding should never be negative.
        total_outstanding = max(
            total_outstanding,
            Decimal("0.00"),
        )

        # --------------------------------------------------------
        # Prepare historical arrears rows for display
        #
        # This does not overwrite the original accounting records.
        # It adds temporary display attributes showing how much of
        # each arrear has been covered.
        # --------------------------------------------------------
        historical_arrears = list(
            historical_arrears_queryset
        )

        payment_available_for_arrears = (
            historical_payment_applied
        )

        for arrear in historical_arrears:
            arrear_amount = Decimal(
                str(arrear.amount or 0)
            )

            amount_applied = min(
                payment_available_for_arrears,
                arrear_amount,
            )

            arrear.display_amount_paid = amount_applied
            arrear.display_outstanding = max(
                arrear_amount - amount_applied,
                Decimal("0.00"),
            )

            arrear.display_is_settled = (
                arrear.display_outstanding
                == Decimal("0.00")
            )

            payment_available_for_arrears -= (
                amount_applied
            )

        # --------------------------------------------------------
        # Determine status
        # --------------------------------------------------------
        if credit_amount > 0:
            fee_status = "OVERPAID"
            fee_status_label = "Overpaid"

        elif total_outstanding == 0:
            fee_status = "PAID"
            fee_status_label = "Fully Paid"

        elif total_paid > 0:
            fee_status = "PARTIAL"
            fee_status_label = "Partially Paid"

        else:
            fee_status = "DEFAULTING"
            fee_status_label = "Defaulting"

        # --------------------------------------------------------
        # Synchronise the FeeBalance record
        # --------------------------------------------------------
        fee_balance, _ = FeeBalance.objects.get_or_create(
            student=student,
            academic_year=current_year,
            term=current_term,
        )

        fee_balance.total_expected = total_expected
        fee_balance.total_paid = total_paid
        fee_balance.carried_over_balance = (
            total_historical_arrears
        )

        # Let FeeBalance.save() calculate its stored balance,
        # status and credit based on the updated model logic.
        fee_balance.save()

        # Ensure the page uses the allocation values calculated here.
        fee_balance.balance = total_outstanding
        fee_balance.credit_amount = credit_amount
        fee_balance.status = fee_status

        # --------------------------------------------------------
        # Payment history and filters
        # --------------------------------------------------------
        payments = student.get_payment_history(
            current_year,
            current_term,
        )

        terms = Term.objects.all().order_by(
            "-academic_year",
            "-term_number",
        )

        fee_structures = FeeStructure.objects.filter(
            student_class=student.current_class
        ).order_by(
            "-academic_year",
            "-term",
        )

        print("\n" + "=" * 60)
        print("Student fee details")
        print(
            f"Student: {student.first_name} "
            f"{student.last_name}"
        )
        print(
            f"Academic year: {current_year}, "
            f"Term: {current_term}"
        )
        print(f"Current fees: {total_expected}")
        print(
            f"Original historical arrears: "
            f"{total_historical_arrears}"
        )
        print(f"Total paid: {total_paid}")
        print(
            f"Payment applied to arrears: "
            f"{historical_payment_applied}"
        )
        print(
            f"Payment applied to current fees: "
            f"{current_term_payment_applied}"
        )
        print(
            f"Remaining historical arrears: "
            f"{remaining_historical_arrears}"
        )
        print(f"Current balance: {current_balance}")
        print(f"Total outstanding: {total_outstanding}")
        print(f"Credit: {credit_amount}")
        print(f"Status: {fee_status}")
        print("=" * 60)

        context = {
            "student": student,

            # Original accounting totals
            "total_expected": total_expected,
            "total_paid": total_paid,
            "total_due": total_due,
            "total_historical_arrears": (
                total_historical_arrears
            ),

            # Corrected payable balances
            "current_balance": current_balance,
            "remaining_historical_arrears": (
                remaining_historical_arrears
            ),
            "total_outstanding": total_outstanding,
            "credit_amount": credit_amount,

            # Allocation information
            "historical_payment_applied": (
                historical_payment_applied
            ),
            "current_term_payment_applied": (
                current_term_payment_applied
            ),

            # Status
            "fee_status": fee_status,
            "fee_status_label": fee_status_label,
            "is_overpaid": credit_amount > 0,
            "is_fully_paid": (
                total_outstanding == 0
                and credit_amount == 0
            ),

            # Records
            "payments": payments,
            "historical_arrears": historical_arrears,
            "fee_balance": fee_balance,
            "terms": terms,
            "fee_structures": fee_structures,

            # Filters
            "current_year": current_year,
            "current_term": current_term,

            # Tenant-safe context
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,

            # URLs
            "tenant_dashboard_url": (
                f"{tenant_base_url}/dashboard/"
            ),
            "tenant_fees_url": (
                f"{tenant_base_url}/fees/"
            ),
            "tenant_historical_arrears_url": (
                f"{tenant_base_url}"
                "/fees/historical-arrears/"
            ),
            "tenant_student_fee_detail_url": (
                f"{tenant_base_url}/student/"
                f"{student.id}/fee-detail/"
            ),
        }

        return render(
            request,
            "digitallibrary/student_fee_detail.html",
            context,
        )
def calculate_grade(percentage, grading_system='both'):
    """
    Calculate grade based on either Traditional or CBC system.
    
    Args:
        percentage: The score percentage (0-100)
        grading_system: 'traditional', 'cbc', or 'both' (returns both formats)
    
    Returns:
        Dictionary with grades from both systems or specified system
    """
    
    # TRADITIONAL 8-4-4 GRADING SYSTEM
    if percentage >= 80:
        traditional = ('A', 'Excellent', 12, 'PASS')
    elif percentage >= 75:
        traditional = ('A-', 'Very Good', 11, 'PASS')
    elif percentage >= 70:
        traditional = ('B+', 'Good', 10, 'PASS')
    elif percentage >= 65:
        traditional = ('B', 'Above Average', 9, 'PASS')
    elif percentage >= 60:
        traditional = ('B-', 'Average', 8, 'PASS')
    elif percentage >= 55:
        traditional = ('C+', 'Satisfactory', 7, 'PASS')
    elif percentage >= 50:
        traditional = ('C', 'Acceptable', 6, 'PASS')
    elif percentage >= 45:
        traditional = ('C-', 'Below Average', 5, 'PASS')
    elif percentage >= 40:
        traditional = ('D+', 'Weak', 4, 'PASS')
    elif percentage >= 35:
        traditional = ('D', 'Very Weak', 3, 'FAIL')
    elif percentage >= 30:
        traditional = ('D-', 'Poor', 2, 'FAIL')
    else:
        traditional = ('E', 'Very Poor', 1, 'FAIL')
    
    # CBC/COMPETENCY-BASED GRADING SYSTEM
    if percentage >= 90:
        cbc = ('EE1', 'Exceptional/Excellent', 8, 'PASS')
    elif percentage >= 75:
        cbc = ('EE2', 'Very Good', 7, 'PASS')
    elif percentage >= 58:
        cbc = ('ME1', 'Good', 6, 'PASS')
    elif percentage >= 41:
        cbc = ('ME2', 'Fair', 5, 'PASS')
    elif percentage >= 31:
        cbc = ('AE1', 'Needs Improvement', 4, 'FAIL')
    elif percentage >= 21:
        cbc = ('AE2', 'Below Average', 3, 'FAIL')
    elif percentage >= 11:
        cbc = ('BE1', 'Well Below Average', 2, 'FAIL')
    elif percentage >= 1:
        cbc = ('BE2', 'Minimal', 1, 'FAIL')
    else:
        cbc = ('BE2', 'Minimal', 0, 'FAIL')
    
    if grading_system == 'traditional':
        return {
            'grade_letter': traditional[0],
            'grade_description': traditional[1],
            'points': traditional[2],
            'status': traditional[3],
            'system': 'Traditional (8-4-4)'
        }
    elif grading_system == 'cbc':
        return {
            'grade_letter': cbc[0],
            'grade_description': cbc[1],
            'points': cbc[2],
            'status': cbc[3],
            'system': 'CBC/CBE'
        }
    else:  # 'both' - return both grading systems
        return {
            'traditional': {
                'grade_letter': traditional[0],
                'grade_description': traditional[1],
                'points': traditional[2],
                'status': traditional[3]
            },
            'cbc': {
                'grade_letter': cbc[0],
                'grade_description': cbc[1],
                'points': cbc[2],
                'status': cbc[3]
            }
        }


def get_school_grading_system(request):
    """Determine which grading system the school uses"""
    # You can store this in your School/Tenant model
    if hasattr(request.tenant, 'grading_system'):
        return request.tenant.grading_system  # 'traditional', 'cbc', or 'both'
    return 'traditional'  # Default to traditional
def generate_report_card(request, exam_id=None, student_id=None):
    """
    Generate a professional report card for a student's exam results.
    Usage: /app/report-card/?exam=1&student=5
    """
    from .models import Exam, Student, StudentResult, SchoolSetting
    from decimal import Decimal
    from django.utils import timezone
    from django.contrib import messages  # ← ADD THIS
    
    # Get exam and student from request
    exam_id = request.GET.get('exam') or exam_id
    student_id = request.GET.get('student') or student_id
    
    if not exam_id or not student_id:
        messages.error(request, "Exam and Student are required to generate report card")
        return redirect('digitallibrary:performance_dashboard')
    
    try:
        exam = Exam.objects.get(id=exam_id)
        student = Student.objects.get(id=student_id, is_active=True)
    except Exam.DoesNotExist:
        messages.error(request, "Exam not found")
        return redirect('digitallibrary:performance_dashboard')
    except Student.DoesNotExist:
        messages.error(request, "Student not found")
        return redirect('digitallibrary:performance_dashboard')
    
    # Get results for this student and exam
    results = StudentResult.objects.filter(
        student=student,
        exam=exam
    ).select_related('subject')
    
    if not results.exists():
        messages.warning(request, f"No results found for {student.get_full_name()} in {exam.name}")
        return redirect('digitallibrary:student_performance', student_id=student.id)
    
    subject_results = []
    strengths = []
    weaknesses = []
    total_points = 0
    
    # Get grading system from school
    grading_system = 'traditional'
    if hasattr(request.tenant, 'grading_system'):
        grading_system = request.tenant.grading_system
    
    for result in results:
        # Calculate percentage
        max_score = float(exam.max_score) if exam.max_score else 100.0
        percentage = (float(result.score) / max_score) * 100
        
        # Get grade using the calculate_grade function
        grades = calculate_grade(percentage, grading_system)
        
        if grading_system == 'both':
            grade_display = f"{grades['traditional']['grade_letter']} / {grades['cbc']['grade_letter']}"
            grade_desc = f"{grades['traditional']['grade_description']} / {grades['cbc']['grade_description']}"
            status = grades['traditional']['status']
            points = grades['traditional']['points']
        else:
            grade_display = grades['grade_letter']
            grade_desc = grades['grade_description']
            status = grades['status']
            points = grades['points']
        
        total_points += points
        
        # Get teacher comment
        teacher_comment = get_teacher_comment(result.subject.name, percentage)
        
        subject_data = {
            'subject': result.subject,
            'score': float(result.score),
            'max_score': max_score,
            'percentage': round(percentage, 1),
            'grade_letter': grade_display,
            'grade_description': grade_desc,
            'status': status,
            'points': points,
            'teacher_comment': teacher_comment,
        }
        
        subject_results.append(subject_data)
        
        # Identify strengths and weaknesses
        if percentage >= 70:
            strengths.append(subject_data)
        elif percentage < 50:
            weaknesses.append(subject_data)
    
    # Calculate overall statistics
    mean_percentage = sum(r['percentage'] for r in subject_results) / len(subject_results)
    overall_grade_info = calculate_grade(mean_percentage, grading_system)
    
    if grading_system == 'both':
        overall_grade_display = f"{overall_grade_info['traditional']['grade_letter']} / {overall_grade_info['cbc']['grade_letter']}"
    else:
        overall_grade_display = overall_grade_info['grade_letter']
    
    # Generate overall remarks
    if mean_percentage >= 80:
        teacher_remarks = f"Excellent performance! {student.first_name} has shown exceptional understanding across all subjects. Keep up the great work!"
    elif mean_percentage >= 70:
        teacher_remarks = f"Very good performance. {student.first_name} is doing well. With a little more effort, can achieve even better results."
    elif mean_percentage >= 60:
        teacher_remarks = f"Good performance. {student.first_name} has a solid understanding. Focus on improving in the weaker areas."
    elif mean_percentage >= 50:
        if weaknesses:
            weak_subjects = ', '.join([w['subject'].name for w in weaknesses[:2]])
            teacher_remarks = f"Satisfactory performance. {student.first_name} needs to put more effort into {weak_subjects}."
        else:
            teacher_remarks = f"Satisfactory performance. {student.first_name} is doing well but can improve further."
    elif mean_percentage >= 40:
        teacher_remarks = f"Below average performance. {student.first_name} needs significant improvement. Please attend remedial classes."
    else:
        teacher_remarks = f"Critical attention needed. {student.first_name} is struggling. Parent-teacher meeting is strongly recommended."
    
    # Get school info
    school = SchoolSetting.objects.first()
    
    context = {
        'student': student,
        'exam': exam,
        'subject_results': subject_results,
        'strengths': strengths,
        'weaknesses': weaknesses,
        'overall_stats': {
            'mean_score': round(mean_percentage, 1),
            'total_points': total_points,
            'total_subjects': len(subject_results),
            'overall_grade': overall_grade_display,
            'grading_system': grading_system.upper()
        },
        'teacher_remarks': teacher_remarks,
        'school': school,
        'school_name': school.name if school else 'ShuleHub',
        'report_date': timezone.now().strftime("%B %d, %Y"),
        'report_id': f"RPT-{exam.id}-{student.id}-{timezone.now().strftime('%Y%m%d')}",
    }
    
    return render(request, 'digitallibrary/professional_report_card.html', context)


def get_teacher_comment(subject_name, percentage):
    """Generate meaningful comment based on percentage"""
    if percentage >= 80:
        return f"🏆 EXCELLENT! {subject_name} is a strong subject. Keep up the great work!"
    elif percentage >= 70:
        return f"👍 VERY GOOD in {subject_name}. Aim for an A next time!"
    elif percentage >= 60:
        return f"📚 GOOD effort in {subject_name}. With more practice, you can score higher."
    elif percentage >= 50:
        return f"📖 SATISFACTORY in {subject_name}. Review your weak areas."
    elif percentage >= 40:
        return f"⚠️ FAIR performance in {subject_name}. Please consult the teacher."
    else:
        return f"❌ NEEDS IMPROVEMENT in {subject_name}. Extra classes recommended."  # ← ADD THIS        return f"❌ NEEDS IMPROVEMENT in {subject_name}. Extra classes recommended."
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.management import call_command
from django_tenants.utils import schema_context
from django.db import connection
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone

from tenants.models import School, Domain
# digitallibrary/views.py

from django.contrib.admin.views.decorators import staff_member_required
from .models import GradingSystem, GradeScale

@staff_member_required
def grading_system_list(request, tenant_schema=None):
    """List all grading systems - tenant-safe version"""
    from django.db import connection

    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"

    systems = GradingSystem.objects.all()

    context = {
        "systems": systems,

        # Tenant-safe context
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,

        # Useful URLs for template buttons
        "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
        "tenant_performance_url": f"{tenant_base_url}/performance/",
        "tenant_grading_systems_url": f"{tenant_base_url}/grading/systems/",
        "tenant_grading_system_create_url": f"{tenant_base_url}/grading/systems/create/",
    }

    return render(request, "digitallibrary/grading/systems.html", context)
@staff_member_required
def grading_system_create(request, tenant_schema=None):
    """
    Create a new grading system - tenant-safe version.

    Supports:
    - single subject assignment through GradingSystem.subject
    - multiple subject assignment through GradingSystem.applicable_subjects
    - subject-specific grading flag
    - grade scales
    """

    from django.shortcuts import render, redirect
    from django.contrib import messages
    from django.db import connection
    from django_tenants.utils import schema_context
    from .models import GradingSystem, GradeScale, Subject

    # ------------------------------------------------------------
    # Detect tenant schema safely
    # ------------------------------------------------------------
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    # Fallback from URL path: /tenant/nyaneje/app/...
    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    # Temporary fallback for your current tenant
    if not schema_name or schema_name == "public":
        schema_name = "nyaneje"

    tenant_base_url = f"/tenant/{schema_name}/app"
    grading_systems_url = f"{tenant_base_url}/grading/systems/"

    print("\n" + "=" * 60)
    print("🟢 grading_system_create called")
    print(f"   Method: {request.method}")
    print(f"   Path: {request.path}")
    print(f"   Tenant schema detected: {schema_name}")

    if request.method == "POST":
        print(f"   POST data: {dict(request.POST)}")

    print("=" * 60)

    # ------------------------------------------------------------
    # Run all queries inside tenant schema
    # ------------------------------------------------------------
    with schema_context(schema_name):

        subjects = Subject.objects.all().order_by("name")

        if request.method == "POST":
            name = request.POST.get("name", "").strip()
            description = request.POST.get("description", "").strip()
            system_type = request.POST.get("system_type", "default")
            passing_score = request.POST.get("passing_score") or 50

            # Your template may use either "subject" or "specific_subject"
            subject_id = request.POST.get("subject") or request.POST.get("specific_subject")

            # Multiple subjects
            applicable_subject_ids = request.POST.getlist("applicable_subjects")

            is_subject_specific = request.POST.get("is_subject_specific") == "on"
            is_active = request.POST.get("is_active") == "on"
            is_default = request.POST.get("is_default") == "on"

            print(f"   name: {name}")
            print(f"   system_type: {system_type}")
            print(f"   passing_score: {passing_score}")
            print(f"   subject_id: {subject_id}")
            print(f"   applicable_subject_ids: {applicable_subject_ids}")
            print(f"   is_subject_specific: {is_subject_specific}")
            print(f"   is_active: {is_active}")
            print(f"   is_default: {is_default}")

            if not name:
                messages.error(request, "System name is required.")
                return redirect(f"{tenant_base_url}/grading/systems/create/")

            selected_subject = None
            if subject_id:
                selected_subject = Subject.objects.filter(id=subject_id).first()

            # If a specific subject or applicable subjects are selected,
            # automatically treat it as subject-specific.
            if selected_subject or applicable_subject_ids:
                is_subject_specific = True

            # If set as default, unset other default systems first
            if is_default:
                GradingSystem.objects.filter(is_default=True).update(is_default=False)

            # If no default grading system exists yet, make this one default
            if not GradingSystem.objects.filter(is_default=True).exists():
                is_default = True

            system = GradingSystem.objects.create(
                name=name,
                description=description,
                system_type=system_type,
                created_by=request.user,
                subject=selected_subject,
                is_subject_specific=is_subject_specific,
                is_active=is_active,
                is_default=is_default,
                passing_score=passing_score,
            )

            # Save applicable subjects many-to-many
            if applicable_subject_ids:
                applicable_subjects = Subject.objects.filter(id__in=applicable_subject_ids)
                system.applicable_subjects.set(applicable_subjects)
            else:
                system.applicable_subjects.clear()

            # ----------------------------------------------------
            # Save grade scales from the table
            # ----------------------------------------------------
            grades = request.POST.getlist("grade")
            min_scores = request.POST.getlist("min_score")
            max_scores = request.POST.getlist("max_score")
            points = request.POST.getlist("points")
            remarks = request.POST.getlist("remark")

            saved_scales = 0

            for i in range(len(grades)):
                grade = grades[i].strip() if i < len(grades) else ""
                min_score = min_scores[i] if i < len(min_scores) else ""
                max_score = max_scores[i] if i < len(max_scores) else ""
                point = points[i] if i < len(points) and points[i] else 0
                remark = remarks[i] if i < len(remarks) else ""

                if grade and min_score and max_score:
                    GradeScale.objects.create(
                        grading_system=system,
                        grade=grade,
                        min_score=min_score,
                        max_score=max_score,
                        points=point,
                        remark=remark,
                    )
                    saved_scales += 1

            print(f"   Created grading system ID: {system.id}")
            print(f"   Saved grade scales: {saved_scales}")
            print(f"   Subject: {system.subject}")
            print(f"   Applicable subjects: {[s.name for s in system.applicable_subjects.all()]}")

            messages.success(
                request,
                f'Grading system "{name}" created successfully with {saved_scales} grade scale(s)!'
            )

            return redirect(f"{tenant_base_url}/grading/systems/{system.id}/edit/")

        context = {
            "system": None,
            "subjects": subjects,

            # Tenant-safe context
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,

            # Useful URLs for template buttons
            "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
            "tenant_performance_url": f"{tenant_base_url}/performance/",
            "tenant_grading_systems_url": grading_systems_url,
            "tenant_grading_system_create_url": f"{tenant_base_url}/grading/systems/create/",
        }

        return render(request, "digitallibrary/grading/system_form.html", context)
    
@staff_member_required
def grading_system_edit(request, tenant_schema=None, pk=None):
    """Edit grading system and its grade scales with subject assignment - tenant-safe version"""

    from django.shortcuts import render, redirect, get_object_or_404
    from django.contrib import messages
    from django.db import connection
    from django_tenants.utils import schema_context
    from .models import GradingSystem, GradeScale, Subject

    # ------------------------------------------------------------
    # Detect tenant schema safely
    # ------------------------------------------------------------
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    # Fallback from URL path: /tenant/nyaneje/app/...
    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    # Temporary fallback for your current tenant
    if not schema_name or schema_name == "public":
        schema_name = "nyaneje"

    tenant_base_url = f"/tenant/{schema_name}/app"
    grading_systems_url = f"{tenant_base_url}/grading/systems/"
    edit_url = f"{tenant_base_url}/grading/systems/{pk}/edit/"

    print("\n" + "=" * 60)
    print("🟡 grading_system_edit called")
    print(f"   Method: {request.method}")
    print(f"   Path: {request.path}")
    print(f"   Tenant schema detected: {schema_name}")
    print(f"   Grading system ID: {pk}")

    if request.method == "POST":
        print(f"   POST data: {dict(request.POST)}")

    print("=" * 60)

    with schema_context(schema_name):

        system = get_object_or_404(GradingSystem, id=pk)

        if request.method == "POST":
            # ----------------------------------------------------
            # Update basic info
            # ----------------------------------------------------
            system.name = request.POST.get("name", "").strip()
            system.description = request.POST.get("description", "").strip()
            system.system_type = request.POST.get("system_type", system.system_type)
            system.passing_score = request.POST.get("passing_score") or system.passing_score
            system.is_active = request.POST.get("is_active") == "on"

            # ----------------------------------------------------
            # Handle default status
            # Support both names: set_default and is_default
            # ----------------------------------------------------
            is_default_checked = (
                request.POST.get("set_default") == "on"
                or request.POST.get("is_default") == "on"
            )

            if is_default_checked:
                if system.school:
                    GradingSystem.objects.filter(
                        school=system.school,
                        is_default=True
                    ).exclude(id=system.id).update(is_default=False)
                else:
                    GradingSystem.objects.filter(
                        is_default=True
                    ).exclude(id=system.id).update(is_default=False)

                system.is_default = True
            else:
                system.is_default = False

            # ----------------------------------------------------
            # Handle subject assignment
            # Your model field is "subject", not "specific_subject"
            # ----------------------------------------------------
            subject_id = request.POST.get("subject") or request.POST.get("specific_subject")

            if subject_id:
                selected_subject = Subject.objects.filter(id=subject_id).first()
                system.subject = selected_subject
            else:
                system.subject = None

            applicable_subject_ids = request.POST.getlist("applicable_subjects")

            system.is_subject_specific = request.POST.get("is_subject_specific") == "on"

            # If subject or multiple subjects selected, force subject-specific true
            if system.subject or applicable_subject_ids:
                system.is_subject_specific = True

            system.save()

            # ----------------------------------------------------
            # Handle applicable subjects many-to-many
            # ----------------------------------------------------
            if applicable_subject_ids:
                applicable_subjects = Subject.objects.filter(id__in=applicable_subject_ids)
                system.applicable_subjects.set(applicable_subjects)
            else:
                system.applicable_subjects.clear()

            # ----------------------------------------------------
            # Handle grade scales
            # Support both template naming styles:
            # grade[] and grade
            # min_score[] and min_score
            # ----------------------------------------------------
            grade_ids = request.POST.getlist("grade_id") or request.POST.getlist("grade_id[]")

            grades = request.POST.getlist("grade[]")
            if not grades:
                grades = request.POST.getlist("grade")

            min_scores = request.POST.getlist("min_score[]")
            if not min_scores:
                min_scores = request.POST.getlist("min_score")

            max_scores = request.POST.getlist("max_score[]")
            if not max_scores:
                max_scores = request.POST.getlist("max_score")

            points = request.POST.getlist("points[]")
            if not points:
                points = request.POST.getlist("points")

            remarks = request.POST.getlist("remark[]")
            if not remarks:
                remarks = request.POST.getlist("remark")

            existing_ids = []

            for i, grade in enumerate(grades):
                grade = grade.strip() if grade else ""

                min_score = min_scores[i] if i < len(min_scores) else ""
                max_score = max_scores[i] if i < len(max_scores) else ""
                point = points[i] if i < len(points) and points[i] else 0
                remark = remarks[i] if i < len(remarks) else ""

                if grade and min_score and max_score:
                    grade_id = grade_ids[i] if i < len(grade_ids) and grade_ids[i] else None

                    if grade_id:
                        grade_scale, created = GradeScale.objects.update_or_create(
                            id=grade_id,
                            grading_system=system,
                            defaults={
                                "grade": grade,
                                "min_score": min_score,
                                "max_score": max_score,
                                "points": point,
                                "remark": remark,
                                "is_active": True,
                            }
                        )
                    else:
                        grade_scale = GradeScale.objects.create(
                            grading_system=system,
                            grade=grade,
                            min_score=min_score,
                            max_score=max_score,
                            points=point,
                            remark=remark,
                            is_active=True,
                        )

                    existing_ids.append(grade_scale.id)

            # Delete removed grades
            GradeScale.objects.filter(
                grading_system=system
            ).exclude(
                id__in=existing_ids
            ).delete()

            print(f"   Updated grading system: {system.name}")
            print(f"   Subject: {system.subject}")
            print(f"   Is subject specific: {system.is_subject_specific}")
            print(f"   Applicable subjects: {[s.name for s in system.applicable_subjects.all()]}")
            print(f"   Grade scales count: {system.grades.count()}")

            messages.success(
                request,
                f'Grading system "{system.name}" updated successfully!'
            )

            return redirect(edit_url)

        # --------------------------------------------------------
        # GET request
        # --------------------------------------------------------
        subjects = Subject.objects.filter(is_active=True).order_by("name")

        context = {
            "system": system,
            "subjects": subjects,
            "grade_scales": system.grades.all().order_by("-min_score"),

            # Tenant-safe context
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,

            # Useful URLs
            "tenant_dashboard_url": f"{tenant_base_url}/dashboard/",
            "tenant_performance_url": f"{tenant_base_url}/performance/",
            "tenant_grading_systems_url": grading_systems_url,
            "tenant_grading_system_create_url": f"{tenant_base_url}/grading/systems/create/",
            "tenant_grading_system_edit_url": edit_url,
        }

        return render(request, "digitallibrary/grading/system_form.html", context)


@staff_member_required
def grading_system_delete(request, tenant_schema=None, pk=None):
    """Delete a grading system - tenant-safe version"""

    from django.shortcuts import redirect, get_object_or_404
    from django.contrib import messages
    from django.db import connection
    from django_tenants.utils import schema_context
    from .models import GradingSystem

    # ------------------------------------------------------------
    # Detect tenant schema safely
    # ------------------------------------------------------------
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        path_parts = request.path.strip("/").split("/")
        if len(path_parts) >= 2 and path_parts[0] == "tenant":
            schema_name = path_parts[1]

    if not schema_name or schema_name == "public":
        schema_name = "nyaneje"

    tenant_base_url = f"/tenant/{schema_name}/app"
    grading_systems_url = f"{tenant_base_url}/grading/systems/"

    print("\n" + "=" * 60)
    print("🔴 grading_system_delete called")
    print(f"   Method: {request.method}")
    print(f"   Path: {request.path}")
    print(f"   Tenant schema detected: {schema_name}")
    print(f"   Grading system ID: {pk}")
    print("=" * 60)

    with schema_context(schema_name):
        system = get_object_or_404(GradingSystem, id=pk)

        if system.is_default:
            messages.error(request, "Cannot delete the default grading system.")
        else:
            system_name = system.name
            system.delete()
            messages.success(
                request,
                f'Grading system "{system_name}" deleted successfully.'
            )

    return redirect(grading_systems_url)
# digitallibrary/views.py

from .models import SMSLog, UserProfile

@staff_member_required
def sms_to_staff(request, tenant_schema=None):
    """Send SMS to teachers and support staff - tenant-safe version"""
    from django.db import connection

    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    if tenant_schema == "public":
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"
    sms_to_staff_url = f"{tenant_base_url}/sms/to-staff/"
    dashboard_url = f"{tenant_base_url}/dashboard/"

    if request.method == "POST":
        recipient_type = request.POST.get("recipient_type")
        message = request.POST.get("message")
        selected_users = request.POST.getlist("users")

        if recipient_type == "all":
            users = User.objects.filter(
                profile__role__in=["teacher", "bursar", "secretary", "admin"]
            )

        elif recipient_type == "teachers":
            users = User.objects.filter(profile__role="teacher")

        elif recipient_type == "staff":
            users = User.objects.filter(
                profile__role__in=["bursar", "secretary", "admin"]
            )

        elif recipient_type == "specific" and selected_users:
            users = User.objects.filter(id__in=selected_users)

        else:
            users = User.objects.none()

        from .sms_utils import send_sms

        sent_count = 0
        failed_count = 0

        for user in users:
            phone = None

            try:
                phone = user.profile.phone_number
            except Exception:
                phone = None

            if phone:
                success = send_sms(phone, message)

                SMSLog.objects.create(
                    recipient=phone,
                    recipient_name=user.get_full_name() or user.username,
                    message=message,
                    category="general",
                    status="sent" if success else "failed",
                    sent_by=request.user,
                )

                if success:
                    sent_count += 1
                else:
                    failed_count += 1

        messages.success(
            request,
            f"SMS sent to {sent_count} staff members. Failed: {failed_count}"
        )

        # Tenant-safe redirect
        return redirect(sms_to_staff_url)

    users = User.objects.filter(
        profile__role__in=["teacher", "bursar", "secretary", "admin"]
    )

    recent_logs = SMSLog.objects.order_by("-created_at")[:10]

    context = {
        "users": users,
        "roles": ["teacher", "bursar", "secretary", "admin"],
        "recent_logs": recent_logs,

        # Tenant-safe context
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,
        "tenant_dashboard_url": dashboard_url,
        "tenant_sms_staff_url": sms_to_staff_url,
    }

    return render(request, "digitallibrary/sms/sms_to_staff.html", context)
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import GradingPreferenceForm
from .models import TeacherGradingPreference, GradingSystem, CBEGradingPathway

@login_required
def teacher_grading_preference(request):
    """View for teachers to set their grading system preference"""
    
    # Get existing preference for this teacher (global or specific)
    preference = TeacherGradingPreference.objects.filter(
        teacher=request.user,
        is_global=True
    ).first()
    
    if request.method == 'POST':
        form = GradingPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            pref = form.save(commit=False)
            pref.teacher = request.user
            pref.is_global = True
            pref.save()
            messages.success(request, 'Your grading preference has been saved!')
            return redirect('digitallibrary:teacher_dashboard')
    else:
        form = GradingPreferenceForm(instance=preference)
    
    context = {
        'form': form,
        'grading_systems': GradingSystem.objects.filter(is_active=True),
        'cbe_pathways': CBEGradingPathway.objects.filter(is_active=True),
    }
    
    return render(request, 'digitallibrary/grading/teacher_preference.html', context)


@login_required
def exam_grading_preference(request, exam_id, subject_id=None):
    """Set grading preference for a specific exam/subject"""
    
    exam = get_object_or_404(Exam, id=exam_id)
    subject = None
    if subject_id:
        subject = get_object_or_404(Subject, id=subject_id)
    
    # Get existing preference
    preference = TeacherGradingPreference.objects.filter(
        teacher=request.user,
        exam=exam,
        subject=subject
    ).first()
    
    if request.method == 'POST':
        form = GradingPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            pref = form.save(commit=False)
            pref.teacher = request.user
            pref.exam = exam
            pref.subject = subject
            pref.is_global = False
            pref.save()
            messages.success(request, f'Grading preference saved for {exam.name}')
            return redirect('digitallibrary:enter_results_form')
    else:
        form = GradingPreferenceForm(instance=preference)
    
    context = {
        'form': form,
        'exam': exam,
        'subject': subject,
        'grading_systems': GradingSystem.objects.filter(is_active=True),
        'cbe_pathways': CBEGradingPathway.objects.filter(is_active=True),
    }
    
    return render(request, 'digitallibrary/grading/exam_preference.html', context)
# digitallibrary/views.py

from django.contrib.admin.views.decorators import staff_member_required
from .models import SubjectGradingConfig, Subject, GradingSystem, Term

@staff_member_required
def subject_grading_list(request, subject_id=None):
    """List grading configurations for subjects"""
    if subject_id:
        subject = get_object_or_404(Subject, id=subject_id)
        configs = SubjectGradingConfig.objects.filter(subject=subject)
        template = 'digitallibrary/grading/subject_configs.html'
        context = {
            'subject': subject,
            'configs': configs,
            'title': f'Grading Configurations - {subject.name}'
        }
    else:
        configs = SubjectGradingConfig.objects.all().select_related('subject', 'grading_system')
        template = 'digitallibrary/grading/all_subject_configs.html'
        context = {
            'configs': configs,
            'title': 'Subject Grading Configurations'
        }
    
    return render(request, template, context)

@staff_member_required
def subject_grading_create(request, subject_id):
    """Create a grading configuration for a subject"""
    subject = get_object_or_404(Subject, id=subject_id)
    grading_systems = GradingSystem.objects.filter(is_active=True)
    
    if request.method == 'POST':
        grading_system_id = request.POST.get('grading_system')
        academic_year = request.POST.get('academic_year')
        term = request.POST.get('term')
        max_score = request.POST.get('max_score')
        passing_score = request.POST.get('passing_score')
        exam_weight = request.POST.get('exam_weight')
        coursework_weight = request.POST.get('coursework_weight')
        
        grading_system = get_object_or_404(GradingSystem, id=grading_system_id)
        
        config, created = SubjectGradingConfig.objects.get_or_create(
            subject=subject,
            academic_year=academic_year,
            term=term if term else None,
            defaults={
                'grading_system': grading_system,
                'max_score': max_score or 100,
                'passing_score': passing_score or 50,
                'exam_weight': exam_weight or 70,
                'coursework_weight': coursework_weight or 30,
            }
        )
        
        if not created:
            config.grading_system = grading_system
            config.max_score = max_score or 100
            config.passing_score = passing_score or 50
            config.exam_weight = exam_weight or 70
            config.coursework_weight = coursework_weight or 30
            config.save()
            messages.success(request, f'Updated grading configuration for {subject.name}')
        else:
            messages.success(request, f'Created grading configuration for {subject.name}')
        
        return redirect('digitallibrary:subject_grading_list', subject_id=subject.id)
    
    context = {
        'subject': subject,
        'grading_systems': grading_systems,
        'academic_years': get_academic_years(),
        'terms': [(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
    }
    return render(request, 'digitallibrary/grading/subject_grading_form.html', context)

@staff_member_required
def subject_grading_edit(request, config_id):
    """Edit a subject grading configuration"""
    config = get_object_or_404(SubjectGradingConfig, id=config_id)
    grading_systems = GradingSystem.objects.filter(is_active=True)
    
    if request.method == 'POST':
        config.grading_system_id = request.POST.get('grading_system')
        config.max_score = request.POST.get('max_score')
        config.passing_score = request.POST.get('passing_score')
        config.exam_weight = request.POST.get('exam_weight')
        config.coursework_weight = request.POST.get('coursework_weight')
        config.is_active = request.POST.get('is_active') == 'on'
        config.save()
        
        messages.success(request, f'Updated grading configuration for {config.subject.name}')
        return redirect('digitallibrary:subject_grading_list', subject_id=config.subject.id)
    
    context = {
        'config': config,
        'grading_systems': grading_systems,
        'academic_years': get_academic_years(),
        'terms': [(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
    }
    return render(request, 'digitallibrary/grading/subject_grading_form.html', context)

def get_academic_years():
    """Helper to get academic year choices"""
    current_year = timezone.now().year
    return [(str(year), str(year)) for year in range(current_year - 5, current_year + 6)]
from django.http import HttpResponse
from django.template import loader
import os
from django.conf import settings

import os
from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse
from django_tenants.utils import schema_context
from tenants.models import School  # Your School model
# Import from your actual models
from digitallibrary.models import Student, Resource
# Teacher doesn't exist as a separate model - use UserProfile instead
from digitallibrary.models import UserProfile
# If you need a Teacher reference, you can do:
Teacher = UserProfile  # Alias for compatibility

def landing_page(request):
    """Landing page with real database statistics"""
    from django.db import connection
    from django.http import HttpResponse
    
    # Get real data using raw SQL
    schools_count = 0
    teachers_count = 0
    students_count = 0
    resources_count = 0
    views_count = 0
    
    try:
        with connection.cursor() as cursor:
            # Count schools
            cursor.execute("SELECT COUNT(*) FROM tenants_school WHERE is_active = true")
            result = cursor.fetchone()
            schools_count = result[0] if result else 0
            
            # Count teachers (staff users who are not superusers)
            cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_staff = true AND is_superuser = false AND is_active = true")
            result = cursor.fetchone()
            teachers_count = result[0] if result else 0
            
            # Count students (non-staff active users)
            cursor.execute("SELECT COUNT(*) FROM auth_user WHERE is_staff = false AND is_active = true")
            result = cursor.fetchone()
            students_count = result[0] if result else 0
            
            # Count resources
            try:
                cursor.execute("SELECT COUNT(*) FROM digitallibrary_resource WHERE is_approved = true")
                result = cursor.fetchone()
                resources_count = result[0] if result else 0
            except:
                resources_count = 0
            
            # Count views
            try:
                cursor.execute("SELECT COUNT(*) FROM digitallibrary_resourceview")
                result = cursor.fetchone()
                views_count = result[0] if result else 0
            except:
                views_count = 0
            
            print(f"Real data - Schools: {schools_count}, Teachers: {teachers_count}, Students: {students_count}, Resources: {resources_count}, Views: {views_count}")
            
    except Exception as e:
        print(f"Error getting counts: {e}")
    
    # Beautiful HTML template with real data
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShuleHub | Digital School Management System</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ font-family: 'Inter', sans-serif; }}
        body {{ background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%); }}
        .stat-card {{ transition: all 0.3s ease; }}
        .stat-card:hover {{ transform: translateY(-10px); }}
    </style>
</head>
<body class="text-white">
    <!-- Navigation -->
    <nav class="bg-black/30 backdrop-blur-md fixed w-full z-50">
        <div class="container mx-auto px-6 py-4">
            <div class="flex justify-between items-center">
                <div class="flex items-center space-x-2">
                    <div class="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl flex items-center justify-center">
                        <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
                        </svg>
                    </div>
                    <span class="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-500">ShuleHub</span>
                </div>
                <div class="hidden md:flex space-x-8">
                    <a href="#features" class="text-gray-300 hover:text-green-400 transition">Features</a>
                    <a href="#stats" class="text-gray-300 hover:text-green-400 transition">Impact</a>
                    <a href="#contact" class="text-gray-300 hover:text-green-400 transition">Contact</a>
                </div>
                <a href="/admin/" class="px-6 py-2 bg-gradient-to-r from-green-600 to-emerald-600 rounded-full text-sm font-semibold hover:shadow-lg hover:shadow-green-500/30 transition transform hover:scale-105">
                    Admin Login
                </a>
            </div>
        </div>
    </nav>

    <!-- Hero Section -->
    <section class="pt-32 pb-20 text-center relative">
        <div class="container mx-auto px-6">
            <div class="inline-block mb-6 animate-bounce">
                <div class="glass rounded-2xl px-8 py-4 bg-white/10 backdrop-blur">
                    <span class="text-green-400 font-semibold tracking-wider">🚀 NEXT-GEN EDUCATION PLATFORM</span>
                </div>
            </div>
            <h1 class="text-5xl md:text-7xl lg:text-8xl font-black mb-6">
                Transform Your<br>
                <span class="text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-500">School Management</span>
            </h1>
            <p class="text-xl md:text-2xl text-gray-400 max-w-3xl mx-auto mb-12">
                The most powerful integrated digital school management system empowering education across Kenya
            </p>
            <div class="flex flex-col sm:flex-row gap-4 justify-center">
                <a href="#contact" class="px-8 py-4 bg-gradient-to-r from-green-600 to-emerald-600 rounded-xl font-bold text-lg hover:shadow-2xl hover:shadow-green-500/40 transition transform hover:scale-105">
                    Start Free Trial <i class="fas fa-arrow-right ml-2"></i>
                </a>
                <a href="#features" class="px-8 py-4 bg-white/10 backdrop-blur rounded-xl font-bold text-lg border border-green-500/30 hover:border-green-500 transition transform hover:scale-105">
                    Explore Features <i class="fas fa-play ml-2"></i>
                </a>
            </div>
        </div>
    </section>

    <!-- Stats Section with REAL DATA -->
    <section id="stats" class="py-20">
        <div class="container mx-auto px-6">
            <div class="text-center mb-16">
                <h2 class="text-4xl md:text-5xl font-bold mb-4 text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-500">Making an Impact Across Kenya</h2>
                <p class="text-xl text-gray-400">Real-time statistics from schools using ShuleHub</p>
            </div>
            
            <div class="grid grid-cols-2 md:grid-cols-5 gap-6 max-w-6xl mx-auto">
                <div class="bg-white/10 backdrop-blur rounded-2xl p-6 text-center stat-card">
                    <div class="text-4xl mb-2">🏫</div>
                    <div class="text-3xl md:text-4xl font-bold text-green-400">{schools_count:,}</div>
                    <div class="text-sm text-gray-300 mt-2 font-semibold">Schools Onboarded</div>
                </div>
                <div class="bg-white/10 backdrop-blur rounded-2xl p-6 text-center stat-card">
                    <div class="text-4xl mb-2">👨‍🏫</div>
                    <div class="text-3xl md:text-4xl font-bold text-green-400">{teachers_count:,}</div>
                    <div class="text-sm text-gray-300 mt-2 font-semibold">Teachers Onboarded</div>
                </div>
                <div class="bg-white/10 backdrop-blur rounded-2xl p-6 text-center stat-card">
                    <div class="text-4xl mb-2">👨‍🎓</div>
                    <div class="text-3xl md:text-4xl font-bold text-green-400">{students_count:,}</div>
                    <div class="text-sm text-gray-300 mt-2 font-semibold">Active Students</div>
                </div>
                <div class="bg-white/10 backdrop-blur rounded-2xl p-6 text-center stat-card">
                    <div class="text-4xl mb-2">📚</div>
                    <div class="text-3xl md:text-4xl font-bold text-green-400">{resources_count:,}</div>
                    <div class="text-sm text-gray-300 mt-2 font-semibold">Learning Resources</div>
                </div>
                <div class="bg-white/10 backdrop-blur rounded-2xl p-6 text-center stat-card">
                    <div class="text-4xl mb-2">👁️</div>
                    <div class="text-3xl md:text-4xl font-bold text-green-400">{views_count:,}</div>
                    <div class="text-sm text-gray-300 mt-2 font-semibold">Resources Accessed</div>
                </div>
            </div>
        </div>
    </section>

    <!-- Features Section -->
    <section id="features" class="py-20 bg-black/20">
        <div class="container mx-auto px-6">
            <h2 class="text-3xl md:text-4xl font-bold text-center mb-12 text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-500">Why Choose ShuleHub?</h2>
            <div class="grid md:grid-cols-3 gap-8 max-w-6xl mx-auto">
                <div class="bg-white/5 rounded-2xl p-6 text-center hover:transform hover:scale-105 transition">
                    <div class="text-5xl mb-3">📚</div>
                    <h3 class="text-xl font-bold text-green-400 mb-2">Complete Platform</h3>
                    <p class="text-gray-400">All-in-one school management solution for Kenyan schools</p>
                </div>
                <div class="bg-white/5 rounded-2xl p-6 text-center hover:transform hover:scale-105 transition">
                    <div class="text-5xl mb-3">📖</div>
                    <h3 class="text-xl font-bold text-green-400 mb-2">Digital Library</h3>
                    <p class="text-gray-400">Access textbooks, past papers, and educational resources</p>
                </div>
                <div class="bg-white/5 rounded-2xl p-6 text-center hover:transform hover:scale-105 transition">
                    <div class="text-5xl mb-3">📊</div>
                    <h3 class="text-xl font-bold text-green-400 mb-2">Performance Tracking</h3>
                    <p class="text-gray-400">Track and analyze student academic performance</p>
                </div>
                <div class="bg-white/5 rounded-2xl p-6 text-center hover:transform hover:scale-105 transition">
                    <div class="text-5xl mb-3">📱</div>
                    <h3 class="text-xl font-bold text-green-400 mb-2">SMS Alerts</h3>
                    <p class="text-gray-400">Keep parents informed with automated notifications</p>
                </div>
                <div class="bg-white/5 rounded-2xl p-6 text-center hover:transform hover:scale-105 transition">
                    <div class="text-5xl mb-3">👨‍👩‍👧‍👦</div>
                    <h3 class="text-xl font-bold text-green-400 mb-2">Parent Portal</h3>
                    <p class="text-gray-400">Real-time access to results, fees, and attendance</p>
                </div>
                <div class="bg-white/5 rounded-2xl p-6 text-center hover:transform hover:scale-105 transition">
                    <div class="text-5xl mb-3">💰</div>
                    <h3 class="text-xl font-bold text-green-400 mb-2">Fee Management</h3>
                    <p class="text-gray-400">Track payments, manage balances, and generate receipts</p>
                </div>
            </div>
        </div>
    </section>

    <!-- CTA Banner -->
    <section class="py-20">
        <div class="container mx-auto px-6">
            <div class="bg-gradient-to-r from-green-600/20 to-emerald-600/20 rounded-3xl p-12 text-center max-w-5xl mx-auto backdrop-blur border border-green-500/30">
                <h2 class="text-3xl md:text-4xl font-bold mb-4">Ready to Transform <span class="text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-500">Your School?</span></h2>
                <p class="text-xl text-gray-300 mb-8">Join {schools_count}+ schools already using ShuleHub to enhance learning outcomes</p>
                <div class="flex flex-wrap gap-4 justify-center">
                    <a href="mailto:kabasil81@gmail.com?subject=School%20Onboarding%20Request" class="px-8 py-4 bg-gradient-to-r from-green-600 to-emerald-600 rounded-xl font-bold hover:shadow-2xl hover:shadow-green-500/40 transition transform hover:scale-105">
                        Start Your Journey <i class="fas fa-arrow-right ml-2"></i>
                    </a>
                    <a href="tel:+254708941520" class="px-8 py-4 bg-white/10 rounded-xl font-bold border border-green-500/30 hover:border-green-500 transition transform hover:scale-105">
                        <i class="fas fa-phone-alt mr-2"></i> Schedule Demo
                    </a>
                </div>
            </div>
        </div>
    </section>

    <!-- Contact Section -->
    <section id="contact" class="py-20 bg-black/20">
        <div class="container mx-auto px-6">
            <div class="grid md:grid-cols-2 gap-12 max-w-5xl mx-auto">
                <div>
                    <h2 class="text-4xl font-bold mb-4 text-transparent bg-clip-text bg-gradient-to-r from-green-400 to-emerald-500">Get in Touch</h2>
                    <p class="text-gray-400 mb-8 text-lg">Have questions? We're here to help you transform your school's management.</p>
                    
                    <div class="space-y-6">
                        <div class="flex items-center space-x-4">
                            <div class="w-12 h-12 bg-green-500/20 rounded-xl flex items-center justify-center">
                                <svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                                </svg>
                            </div>
                            <div>
                                <p class="text-gray-400 text-sm">Email Us</p>
                                <a href="mailto:kabasil81@gmail.com" class="text-white font-semibold hover:text-green-400 transition">kabasil81@gmail.com</a>
                            </div>
                        </div>
                        
                        <div class="flex items-center space-x-4">
                            <div class="w-12 h-12 bg-green-500/20 rounded-xl flex items-center justify-center">
                                <svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
                                </svg>
                            </div>
                            <div>
                                <p class="text-gray-400 text-sm">Call Us</p>
                                <a href="tel:+254708941520" class="text-white font-semibold hover:text-green-400 transition">+254 708 941 520</a>
                            </div>
                        </div>
                        
                        <div class="flex items-center space-x-4">
                            <div class="w-12 h-12 bg-green-500/20 rounded-xl flex items-center justify-center">
                                <svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.66 0 3-4 3-9s-1.34-9-3-9m0 18c-1.66 0-3-4-3-9s1.34-9 3-9"></path>
                                </svg>
                            </div>
                            <div>
                                <p class="text-gray-400 text-sm">School Subdomain</p>
                                <code class="text-green-400 text-sm">yourschool.shulehub.org</code>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="bg-white/10 backdrop-blur rounded-2xl p-8">
                    <h3 class="text-2xl font-bold mb-4">Ready to get started?</h3>
                    <p class="text-gray-400 mb-6">Fill out this form and our team will reach out within 24 hours.</p>
                    
                    <form action="mailto:kabasil81@gmail.com" method="POST" enctype="text/plain" class="space-y-4">
                        <input type="text" placeholder="School Name" class="w-full px-4 py-3 bg-gray-900/50 rounded-xl border border-gray-700 focus:border-green-500 focus:outline-none transition text-white">
                        <input type="email" placeholder="Your Email" class="w-full px-4 py-3 bg-gray-900/50 rounded-xl border border-gray-700 focus:border-green-500 focus:outline-none transition text-white">
                        <input type="tel" placeholder="Phone Number" class="w-full px-4 py-3 bg-gray-900/50 rounded-xl border border-gray-700 focus:border-green-500 focus:outline-none transition text-white">
                        <textarea rows="4" placeholder="Message" class="w-full px-4 py-3 bg-gray-900/50 rounded-xl border border-gray-700 focus:border-green-500 focus:outline-none transition text-white"></textarea>
                        <button type="submit" class="w-full px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 rounded-xl font-semibold hover:shadow-lg hover:shadow-green-500/30 transition transform hover:scale-105">
                            Send Message <i class="fas fa-paper-plane ml-2"></i>
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="py-12 px-6 border-t border-gray-800">
        <div class="container mx-auto text-center">
            <div class="flex justify-center space-x-8 mb-6">
                <a href="#" class="text-gray-500 hover:text-green-400 transition"><i class="fab fa-facebook-f text-xl"></i></a>
                <a href="#" class="text-gray-500 hover:text-green-400 transition"><i class="fab fa-twitter text-xl"></i></a>
                <a href="#" class="text-gray-500 hover:text-green-400 transition"><i class="fab fa-linkedin-in text-xl"></i></a>
                <a href="#" class="text-gray-500 hover:text-green-400 transition"><i class="fab fa-instagram text-xl"></i></a>
            </div>
            <p class="text-gray-500">© 2026 ShuleHub. All rights reserved. Empowering Kenyan Education.</p>
        </div>
    </footer>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/js/all.min.js"></script>
</body>
</html>"""
    
    return HttpResponse(html)

# digitallibrary/views.py - Add these functions at the end of the file or near other student views

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404, render
from .models import Student, StudentActionLog
import json
import logging

logger = logging.getLogger(__name__)


def is_admin_or_principal(user):
    """Check if user is admin or principal"""
    if user.is_superuser:
        return True
    if hasattr(user, 'profile') and user.profile.role in ['admin', 'principal']:
        return True
    return False


@login_required
@user_passes_test(is_admin_or_principal)
@require_http_methods(["POST"])
def soft_delete_student(request, student_id):
    """
    Soft delete a student - marks as inactive with reason
    """
    try:
        student = get_object_or_404(Student, id=student_id)
        
        # Parse request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}
        
        reason_type = data.get('reason_type', 'other')
        reason = data.get('reason', '')
        transfer_to = data.get('transfer_to', '')
        
        # Validate reason
        if reason_type == 'other' and not reason.strip():
            return JsonResponse({
                'success': False,
                'error': 'Please provide a reason for deactivation'
            })
        
        # Perform soft delete
        student.soft_delete(
            user=request.user,
            reason=reason or dict(Student.TRANSFER_REASON_CHOICES).get(reason_type, 'Deactivated'),
            reason_type=reason_type,
            transfer_to=transfer_to
        )
        
        # Log the action
        logger.info(f"Student {student.admission_number} ({student.get_full_name()}) deactivated by {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'Student {student.get_full_name()} has been deactivated successfully',
            'student_id': student.id,
            'status': 'inactive'
        })
        
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
    except Exception as e:
        logger.error(f"Error deactivating student {student_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@user_passes_test(is_admin_or_principal)
@require_http_methods(["POST"])
def reactivate_student(request, student_id):
    """
    Reactivate a soft-deleted student
    """
    try:
        student = get_object_or_404(Student, id=student_id)
        
        # Parse request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}
        
        reason = data.get('reason', 'Reactivated by admin')
        
        # Check if student is already active
        if student.is_active:
            return JsonResponse({
                'success': False,
                'error': 'Student is already active'
            })
        
        # Perform reactivation
        student.reactivate(user=request.user, reason=reason)
        
        # Log the action
        logger.info(f"Student {student.admission_number} ({student.get_full_name()}) reactivated by {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'Student {student.get_full_name()} has been reactivated successfully',
            'student_id': student.id,
            'status': 'active'
        })
        
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Student not found'}, status=404)
    except Exception as e:
        logger.error(f"Error reactivating student {student_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@user_passes_test(is_admin_or_principal)
def student_action_log(request, student_id):
    """
    View to show student action history
    """
    student = get_object_or_404(Student, id=student_id)
    actions = student.action_logs.all()[:50]
    
    context = {
        'student': student,
        'actions': actions,
    }
    return render(request, 'fees/student_action_log.html', context)


@login_required
@user_passes_test(is_admin_or_principal)
@require_http_methods(["POST"])
def bulk_student_action(request):
    """
    Bulk action for multiple students (delete/reactivate)
    """
    try:
        data = json.loads(request.body)
        student_ids = data.get('student_ids', [])
        action = data.get('action', '')  # 'delete' or 'reactivate'
        reason = data.get('reason', '')
        
        if not student_ids:
            return JsonResponse({'success': False, 'error': 'No students selected'})
        
        results = {
            'successful': [],
            'failed': []
        }
        
        for student_id in student_ids:
            try:
                student = Student.objects.get(id=student_id)
                
                if action == 'delete':
                    if student.is_active:
                        student.soft_delete(user=request.user, reason=reason, reason_type='bulk')
                        results['successful'].append({
                            'id': student.id,
                            'name': student.get_full_name(),
                            'admission': student.admission_number
                        })
                    else:
                        results['failed'].append({
                            'id': student.id,
                            'name': student.get_full_name(),
                            'error': 'Already inactive'
                        })
                elif action == 'reactivate':
                    if not student.is_active:
                        student.reactivate(user=request.user, reason=reason)
                        results['successful'].append({
                            'id': student.id,
                            'name': student.get_full_name(),
                            'admission': student.admission_number
                        })
                    else:
                        results['failed'].append({
                            'id': student.id,
                            'name': student.get_full_name(),
                            'error': 'Already active'
                        })
            except Student.DoesNotExist:
                results['failed'].append({
                    'id': student_id,
                    'error': 'Student not found'
                })
        
        return JsonResponse({
            'success': True,
            'results': results,
            'total_successful': len(results['successful']),
            'total_failed': len(results['failed'])
        })
        
    except Exception as e:
        logger.error(f"Error in bulk action: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
from django.contrib import messages
from .models import SchoolSetting

@staff_member_required
def exam_results_entry(request, exam_id):
    """
    Enter results for an exam - by subject, filtered by registered student subjects
    """
    from .models import Exam, Subject, Student, StudentResult
    
    exam = get_object_or_404(Exam, pk=exam_id)
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    
    selected_subject_id = request.GET.get('subject')
    selected_subject = None
    students = []
    existing_results = {}
    
    if selected_subject_id:
        try:
            selected_subject = Subject.objects.get(pk=selected_subject_id, is_active=True)
            
            students_qs = exam.get_students_for_exam()
            students = students_qs.filter(
                subjects=selected_subject,
                is_active=True
            ).distinct().order_by('admission_number')
            
            existing_results_qs = StudentResult.objects.filter(
                exam=exam,
                subject=selected_subject,
                student__in=students
            ).select_related('student')
            
            existing_results = {result.student_id: result for result in existing_results_qs}
            
        except Subject.DoesNotExist:
            messages.error(request, "Selected subject does not exist.")
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        
        if subject_id:
            selected_subject = get_object_or_404(Subject, pk=subject_id, is_active=True)
            
            students = exam.get_students_for_exam().filter(
                subjects=selected_subject,
                is_active=True
            ).distinct()
            
            saved_count = 0
            
            for student in students:
                score_key = f'score_{student.id}'
                if score_key in request.POST:
                    score = request.POST.get(score_key)
                    
                    if score and score.strip():
                        try:
                            score_value = float(score)
                            if 0 <= score_value <= (exam.max_score or 100):
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
                messages.success(request, f'Results for {exam.name} - {selected_subject.name} saved successfully!')
            else:
                messages.warning(request, 'No results were saved.')
            
            return redirect(f'{request.path}?subject={subject_id}')
    
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


# digitallibrary/views.py

@staff_member_required
def bulk_enter_results(request, tenant_schema=None):
    """
    Bulk Excel upload page - direct file upload and processing
    """
    from .models import Exam, Subject, SchoolSetting
    
    print("\n" + "="*60)
    print("🔵 bulk_enter_results view called")
    print(f"   Method: {request.method}")
    print("="*60)
    
    # Get exams and subjects for dropdowns
    exams = Exam.objects.filter(is_active=True).order_by('-academic_year', '-created_at')
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    
    print(f"📋 Exams found: {exams.count()}")
    print(f"📋 Subjects found: {subjects.count()}")
    
    if request.method == 'POST':
        exam_id = request.POST.get('exam')
        subject_id = request.POST.get('subject')
        grading_system = request.POST.get('grading_system', 'cbe')
        excel_file = request.FILES.get('excel_file')
        
        print(f"📝 POST data:")
        print(f"   exam_id: {exam_id}")
        print(f"   subject_id: {subject_id}")
        print(f"   grading_system: {grading_system}")
        print(f"   file: {excel_file.name if excel_file else 'None'}")
        
        if not exam_id or not subject_id or not excel_file:
            messages.error(request, 'Please select exam, subject and upload a file')
            return redirect('digitallibrary:bulk_enter_results')
        
        try:
            exam = Exam.objects.get(id=exam_id)
            subject = Subject.objects.get(id=subject_id)
            use_cbe = grading_system == 'cbe'
            
            # Process the Excel file
            import pandas as pd
            from django.db import connection
            
            # Read file
            ext = excel_file.name.split('.')[-1].lower()
            if ext == 'csv':
                df = pd.read_csv(excel_file)
            else:
                df = pd.read_excel(excel_file)
            
            # Normalize columns
            df.columns = df.columns.str.strip().str.lower()
            
            # Find admission and score columns
            admission_col = None
            score_col = None
            
            for col in df.columns:
                if 'admission' in col or 'adm' in col or 'reg' in col:
                    admission_col = col
                elif 'score' in col or 'mark' in col or 'result' in col:
                    score_col = col
            
            if admission_col is None or score_col is None:
                messages.error(request, 'Excel file must have "Admission Number" and "Score" columns')
                return redirect('digitallibrary:bulk_enter_results')
            
            results_processed = 0
            errors = []
            max_score = float(exam.max_score) if exam.max_score else 100.0
            
            with connection.cursor() as cursor:
                for index, row in df.iterrows():
                    admission_number = str(row[admission_col]).strip() if pd.notna(row[admission_col]) else None
                    score_value = row[score_col] if pd.notna(row[score_col]) else None
                    
                    if not admission_number or score_value is None:
                        continue
                    
                    try:
                        score = float(score_value)
                        
                        if score < 0 or score > max_score:
                            errors.append(f"Row {index + 2}: Score {score} out of range (0-{max_score})")
                            continue
                        
                        # Get student
                        from .models import Student
                        student = Student.objects.filter(admission_number=admission_number, is_active=True).first()
                        if not student:
                            errors.append(f"Row {index + 2}: Student '{admission_number}' not found")
                            continue
                        
                        if use_cbe:
                            # Get CBE grade
                            cursor.execute("""
                                SELECT id, points FROM digitallibrary_kneccbegrade 
                                WHERE min_score <= %s AND max_score >= %s
                                LIMIT 1
                            """, [score, score])
                            grade = cursor.fetchone()
                            if grade:
                                grade_id, points = grade
                                cursor.execute("""
                                    INSERT INTO digitallibrary_studentresult 
                                    (student_id, exam_id, subject_id, score, grade_id, points, entered_by_id, entered_at, updated_at)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                                    ON CONFLICT (student_id, exam_id, subject_id) 
                                    DO UPDATE SET 
                                        score = EXCLUDED.score,
                                        grade_id = EXCLUDED.grade_id,
                                        points = EXCLUDED.points,
                                        updated_at = NOW()
                                """, [student.id, exam.id, subject.id, score, grade_id, points, request.user.id])
                                results_processed += 1
                        else:
                            # Traditional grading
                            percentage = (score / max_score) * 100
                            if percentage >= 80: grade_name = 'A'; points = 12
                            elif percentage >= 75: grade_name = 'A-'; points = 11
                            elif percentage >= 70: grade_name = 'B+'; points = 10
                            elif percentage >= 65: grade_name = 'B'; points = 9
                            elif percentage >= 60: grade_name = 'B-'; points = 8
                            elif percentage >= 55: grade_name = 'C+'; points = 7
                            elif percentage >= 50: grade_name = 'C'; points = 6
                            elif percentage >= 45: grade_name = 'C-'; points = 5
                            elif percentage >= 40: grade_name = 'D+'; points = 4
                            elif percentage >= 35: grade_name = 'D'; points = 3
                            elif percentage >= 30: grade_name = 'D-'; points = 2
                            else: grade_name = 'E'; points = 1
                            
                            cursor.execute("""
                                SELECT id FROM digitallibrary_grade WHERE grade = %s LIMIT 1
                            """, [grade_name])
                            grade = cursor.fetchone()
                            grade_id = grade[0] if grade else None
                            
                            cursor.execute("""
                                INSERT INTO digitallibrary_studentresult 
                                (student_id, exam_id, subject_id, score, grade_id, points, entered_by_id, entered_at, updated_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                                ON CONFLICT (student_id, exam_id, subject_id) 
                                DO UPDATE SET 
                                    score = EXCLUDED.score,
                                    grade_id = EXCLUDED.grade_id,
                                    points = EXCLUDED.points,
                                    updated_at = NOW()
                            """, [student.id, exam.id, subject.id, score, grade_id, points, request.user.id])
                            results_processed += 1
                            
                    except Exception as e:
                        errors.append(f"Row {index + 2}: {str(e)}")
            
            if results_processed > 0:
                messages.success(request, f'✅ Successfully processed {results_processed} results for {exam.name} - {subject.name}')
            else:
                messages.warning(request, '⚠️ No valid results were found in the file.')
            
            if errors:
                for error in errors[:5]:
                    messages.warning(request, error)
                if len(errors) > 5:
                    messages.info(request, f'... and {len(errors) - 5} more errors')
                    
            return redirect('digitallibrary:exam_list')
            
        except Exam.DoesNotExist:
            messages.error(request, 'Selected exam not found')
        except Subject.DoesNotExist:
            messages.error(request, 'Selected subject not found')
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            print(f"❌ Exception: {e}")
        
        return redirect('digitallibrary:bulk_enter_results')
    
    # GET request - show the upload form
    context = {
        'exams': exams,
        'subjects': subjects,
        'title': 'Bulk Excel Upload',
        'school': SchoolSetting.objects.first(),
    }
    
    return render(request, 'performance/bulk_excel_upload.html', context)

@staff_member_required
def bulk_results_entry_by_class(request, exam_id, class_id):
    """
    Enter results for all students in a class for all subjects
    """
    from .models import Exam, Class, Subject, Student, StudentResult
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect, render
    
    # Get objects
    exam = get_object_or_404(Exam, id=exam_id)
    student_class = get_object_or_404(Class, id=class_id)
    
    # Get students in this class - try different field names
    students = Student.objects.filter(
        current_class=student_class,
        is_active=True
    ).order_by('first_name', 'last_name')
    
    # If no students found with 'current_class', try 'student_class'
    if not students.exists():
        students = Student.objects.filter(
            student_class=student_class,
            is_active=True
        ).order_by('first_name', 'last_name')
    
    # Get all active subjects
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    
    # Get existing results
    existing_results = {}
    if students.exists():
        results = StudentResult.objects.filter(
            exam=exam, 
            student__in=students
        )
        for r in results:
            key = f"{r.student_id}_{r.subject_id}"
            existing_results[key] = r
    
    # Handle POST request
    if request.method == 'POST':
        saved_count = 0
        for key, value in request.POST.items():
            if key.startswith('score_') and value.strip():
                parts = key.replace('score_', '').split('_')
                if len(parts) == 2:
                    student_id, subject_id = parts
                    try:
                        score = float(value)
                        student = Student.objects.get(id=student_id)
                        subject = Subject.objects.get(id=subject_id)
                        
                        StudentResult.objects.update_or_create(
                            student=student,
                            exam=exam,
                            subject=subject,
                            defaults={'score': score, 'entered_by': request.user}
                        )
                        saved_count += 1
                    except (ValueError, Student.DoesNotExist, Subject.DoesNotExist):
                        continue
        
        messages.success(request, f'Successfully saved {saved_count} results for {student_class.name}')
        return redirect('digitallibrary:bulk_results_entry_by_class', exam_id=exam.id, class_id=class_id)
    
    context = {
        'exam': exam,
        'class': student_class,
        'students': students,
        'subjects': subjects,
        'existing_results': existing_results,
        'student_count': students.count(),
        'subject_count': subjects.count(),
        'title': f'Bulk Results - {exam.name} - {student_class.name}',
    }
    return render(request, 'performance/bulk_results_entry_by_class.html', context)


from decimal import Decimal

import openpyxl
import pandas as pd

from django.contrib import messages
from django.db import connection, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django_tenants.utils import schema_context

from .decorators import teacher_required
from .models import (
    Class,
    Exam,
    SchoolSetting,
    Student,
    StudentResult,
    Subject,
)


def _resolve_tenant_schema(request, tenant_schema=None):
    """
    Resolve the active tenant from the URL, request, tenant object,
    or current database connection.
    """
    schema_name = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(
            getattr(request, "tenant", None),
            "schema_name",
            None,
        )
        or getattr(connection, "schema_name", None)
    )

    if not schema_name or schema_name == "public":
        parts = request.path.strip("/").split("/")

        if len(parts) >= 2 and parts[0] == "tenant":
            schema_name = parts[1]

    return schema_name


def _grade_from_percentage(percentage):
    """
    Return traditional grade name and points.
    """
    if percentage >= 80:
        return "A", 12
    if percentage >= 75:
        return "A-", 11
    if percentage >= 70:
        return "B+", 10
    if percentage >= 65:
        return "B", 9
    if percentage >= 60:
        return "B-", 8
    if percentage >= 55:
        return "C+", 7
    if percentage >= 50:
        return "C", 6
    if percentage >= 45:
        return "C-", 5
    if percentage >= 40:
        return "D+", 4
    if percentage >= 35:
        return "D", 3
    if percentage >= 30:
        return "D-", 2

    return "E", 1


@teacher_required
def bulk_enter_results(
    request,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """
    Bulk Excel or CSV upload page.

    Accessible to teachers, principals, and administrators
    inside the active tenant.
    """
    schema_name = _resolve_tenant_schema(
        request,
        tenant_schema,
    )

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "School tenant context was not detected.",
        )
        return redirect("/app/")

    tenant_base_url = f"/tenant/{schema_name}/app"
    bulk_enter_url = (
        f"{tenant_base_url}/bulk-enter-results/"
    )
    exam_list_url = f"{tenant_base_url}/exams/"

    with schema_context(schema_name):
        exams = Exam.objects.filter(
            is_active=True,
        ).order_by(
            "-academic_year",
            "-created_at",
        )

        subjects = Subject.objects.filter(
            is_active=True,
        ).order_by("name")

        if request.method == "POST":
            exam_id = request.POST.get("exam")
            subject_id = request.POST.get("subject")
            grading_system = request.POST.get(
                "grading_system",
                "cbe",
            )
            uploaded_file = request.FILES.get(
                "excel_file"
            )

            if (
                not exam_id
                or not subject_id
                or not uploaded_file
            ):
                messages.error(
                    request,
                    (
                        "Please select an exam and subject, "
                        "then upload a file."
                    ),
                )
                return redirect(bulk_enter_url)

            try:
                exam = Exam.objects.get(id=exam_id)
                subject = Subject.objects.get(
                    id=subject_id
                )

                extension = (
                    uploaded_file.name.rsplit(".", 1)[-1]
                    .lower()
                )

                if extension == "csv":
                    dataframe = pd.read_csv(
                        uploaded_file
                    )
                else:
                    dataframe = pd.read_excel(
                        uploaded_file
                    )

                dataframe.columns = (
                    dataframe.columns.astype(str)
                    .str.strip()
                    .str.lower()
                )

                admission_column = None
                score_column = None

                for column in dataframe.columns:
                    if any(
                        term in column
                        for term in (
                            "admission",
                            "adm",
                            "reg",
                            "student",
                        )
                    ):
                        admission_column = column

                    elif any(
                        term in column
                        for term in (
                            "score",
                            "mark",
                            "result",
                        )
                    ):
                        score_column = column

                if (
                    admission_column is None
                    or score_column is None
                ):
                    messages.error(
                        request,
                        (
                            'The file must contain '
                            '"Admission Number" and '
                            '"Score" columns.'
                        ),
                    )
                    return redirect(bulk_enter_url)

                max_score = Decimal(
                    str(exam.max_score or 100)
                )
                use_cbe = grading_system == "cbe"

                processed = 0
                errors = []

                with transaction.atomic():
                    with connection.cursor() as cursor:
                        for index, row in dataframe.iterrows():
                            row_number = index + 2

                            admission_number = (
                                str(
                                    row[admission_column]
                                ).strip()
                                if pd.notna(
                                    row[admission_column]
                                )
                                else None
                            )

                            raw_score = (
                                row[score_column]
                                if pd.notna(
                                    row[score_column]
                                )
                                else None
                            )

                            if (
                                not admission_number
                                or raw_score is None
                            ):
                                continue

                            try:
                                score = Decimal(
                                    str(raw_score)
                                )
                            except Exception:
                                errors.append(
                                    (
                                        f"Row {row_number}: "
                                        f"Invalid score "
                                        f"'{raw_score}'."
                                    )
                                )
                                continue

                            if (
                                score < 0
                                or score > max_score
                            ):
                                errors.append(
                                    (
                                        f"Row {row_number}: "
                                        f"Score {score} is outside "
                                        f"the range 0-{max_score}."
                                    )
                                )
                                continue

                            student = (
                                Student.objects.filter(
                                    admission_number=(
                                        admission_number
                                    ),
                                    is_active=True,
                                )
                                .first()
                            )

                            if not student:
                                errors.append(
                                    (
                                        f"Row {row_number}: "
                                        f"Student "
                                        f"'{admission_number}' "
                                        "was not found."
                                    )
                                )
                                continue

                            grade_id = None
                            grade_name = None
                            points = 0

                            if use_cbe:
                                percentage = (
                                    score
                                    / max_score
                                    * Decimal("100")
                                    if max_score > 0
                                    else score
                                )

                                cursor.execute(
                                    """
                                    SELECT id, grade, points
                                    FROM digitallibrary_kneccbegrade
                                    WHERE min_score <= %s
                                      AND max_score >= %s
                                    LIMIT 1
                                    """,
                                    [
                                        percentage,
                                        percentage,
                                    ],
                                )

                                grade_row = (
                                    cursor.fetchone()
                                )

                                if not grade_row:
                                    errors.append(
                                        (
                                            f"Row {row_number}: "
                                            "No matching CBE grade "
                                            "was found."
                                        )
                                    )
                                    continue

                                (
                                    grade_id,
                                    grade_name,
                                    points,
                                ) = grade_row

                            else:
                                percentage = (
                                    score
                                    / max_score
                                    * Decimal("100")
                                    if max_score > 0
                                    else score
                                )

                                (
                                    grade_name,
                                    points,
                                ) = _grade_from_percentage(
                                    percentage
                                )

                                cursor.execute(
                                    """
                                    SELECT id
                                    FROM digitallibrary_grade
                                    WHERE grade = %s
                                    LIMIT 1
                                    """,
                                    [grade_name],
                                )

                                grade_row = (
                                    cursor.fetchone()
                                )

                                grade_id = (
                                    grade_row[0]
                                    if grade_row
                                    else None
                                )

                            StudentResult.objects.update_or_create(
                                student=student,
                                exam=exam,
                                subject=subject,
                                defaults={
                                    "score": score,
                                    "grade_id": grade_id,
                                    "grade": grade_name,
                                    "points": points,
                                    "entered_by": request.user,
                                },
                            )

                            processed += 1

                if processed:
                    messages.success(
                        request,
                        (
                            f"Successfully processed "
                            f"{processed} result(s) for "
                            f"{exam.name} - {subject.name}."
                        ),
                    )
                else:
                    messages.warning(
                        request,
                        "No valid results were found.",
                    )

                for error in errors[:5]:
                    messages.warning(request, error)

                if len(errors) > 5:
                    messages.info(
                        request,
                        (
                            f"...and "
                            f"{len(errors) - 5} more errors."
                        ),
                    )

                return redirect(exam_list_url)

            except Exam.DoesNotExist:
                messages.error(
                    request,
                    "The selected exam was not found.",
                )

            except Subject.DoesNotExist:
                messages.error(
                    request,
                    "The selected subject was not found.",
                )

            except Exception as error:
                messages.error(
                    request,
                    f"Error processing file: {error}",
                )

            return redirect(bulk_enter_url)

        context = {
            "exams": exams,
            "subjects": subjects,
            "title": "Bulk Excel Upload",
            "school": SchoolSetting.objects.first(),
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_exam_list_url": exam_list_url,
            "tenant_bulk_enter_url": bulk_enter_url,
        }

        return render(
            request,
            "performance/bulk_excel_upload.html",
            context,
        )


@teacher_required
def bulk_results_entry_by_class(
    request,
    exam_id,
    class_id,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """
    Enter results for every active student in a class
    across all active subjects.
    """
    schema_name = _resolve_tenant_schema(
        request,
        tenant_schema,
    )

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "School tenant context was not detected.",
        )
        return redirect("/app/")

    tenant_base_url = f"/tenant/{schema_name}/app"

    with schema_context(schema_name):
        exam = get_object_or_404(
            Exam,
            id=exam_id,
        )

        student_class = get_object_or_404(
            Class,
            id=class_id,
        )

        students = Student.objects.filter(
            current_class=student_class,
            is_active=True,
        ).order_by(
            "first_name",
            "last_name",
        )

        subjects = Subject.objects.filter(
            is_active=True,
        ).order_by("name")

        existing_results = {
            f"{result.student_id}_{result.subject_id}": (
                result
            )
            for result in StudentResult.objects.filter(
                exam=exam,
                student__in=students,
                subject__in=subjects,
            )
        }

        if request.method == "POST":
            saved_count = 0
            skipped_count = 0

            valid_student_ids = set(
                students.values_list(
                    "id",
                    flat=True,
                )
            )

            valid_subject_ids = set(
                subjects.values_list(
                    "id",
                    flat=True,
                )
            )

            with transaction.atomic():
                for key, value in request.POST.items():
                    if (
                        not key.startswith("score_")
                        or not str(value).strip()
                    ):
                        continue

                    identifiers = (
                        key.replace("score_", "")
                        .split("_")
                    )

                    if len(identifiers) != 2:
                        skipped_count += 1
                        continue

                    try:
                        student_id = int(
                            identifiers[0]
                        )
                        subject_id = int(
                            identifiers[1]
                        )
                        score = Decimal(
                            str(value)
                        )
                    except Exception:
                        skipped_count += 1
                        continue

                    if (
                        student_id not in valid_student_ids
                        or subject_id
                        not in valid_subject_ids
                    ):
                        skipped_count += 1
                        continue

                    max_score = Decimal(
                        str(exam.max_score or 100)
                    )

                    if (
                        score < 0
                        or score > max_score
                    ):
                        skipped_count += 1
                        continue

                    student = students.get(
                        id=student_id
                    )
                    subject = subjects.get(
                        id=subject_id
                    )

                    StudentResult.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        defaults={
                            "score": score,
                            "entered_by": request.user,
                        },
                    )

                    saved_count += 1

            if saved_count:
                messages.success(
                    request,
                    (
                        f"Successfully saved "
                        f"{saved_count} result(s) for "
                        f"{student_class.name}."
                    ),
                )

            if skipped_count:
                messages.warning(
                    request,
                    (
                        f"{skipped_count} result(s) "
                        "were skipped."
                    ),
                )

            return redirect(
                (
                    f"{tenant_base_url}/"
                    f"bulk-results/class/"
                    f"{exam.id}/{student_class.id}/"
                )
            )

        context = {
            "exam": exam,
            "class": student_class,
            "students": students,
            "subjects": subjects,
            "existing_results": existing_results,
            "student_count": students.count(),
            "subject_count": subjects.count(),
            "title": (
                f"Bulk Results - {exam.name} - "
                f"{student_class.name}"
            ),
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_dashboard_url": (
                f"{tenant_base_url}/dashboard/"
            ),
            "tenant_exam_list_url": (
                f"{tenant_base_url}/exams/"
            ),
        }

        return render(
            request,
            "performance/bulk_results_entry_by_class.html",
            context,
        )


@teacher_required
def bulk_excel_upload(
    request,
    tenant_schema=None,
    *args,
    **kwargs,
):
    """
    Upload a simple Excel workbook with admission number
    and score columns.
    """
    schema_name = _resolve_tenant_schema(
        request,
        tenant_schema,
    )

    if not schema_name or schema_name == "public":
        messages.error(
            request,
            "School tenant context was not detected.",
        )
        return redirect("/app/")

    tenant_base_url = f"/tenant/{schema_name}/app"
    upload_url = (
        f"{tenant_base_url}/exams/"
        "bulk-excel-upload/"
    )
    exam_list_url = f"{tenant_base_url}/exams/"

    with schema_context(schema_name):
        exams = Exam.objects.all().order_by(
            "-academic_year",
            "-created_at",
        )

        subjects = Subject.objects.filter(
            is_active=True,
        ).order_by("name")

        if request.method == "POST":
            exam_id = request.POST.get("exam")
            subject_id = request.POST.get(
                "subject"
            )
            uploaded_file = request.FILES.get(
                "excel_file"
            )

            if not all(
                [
                    exam_id,
                    subject_id,
                    uploaded_file,
                ]
            ):
                messages.error(
                    request,
                    (
                        "Please select an exam and "
                        "subject, then upload an "
                        "Excel file."
                    ),
                )
                return redirect(upload_url)

            try:
                exam = Exam.objects.get(id=exam_id)
                subject = Subject.objects.get(
                    id=subject_id
                )

                workbook = openpyxl.load_workbook(
                    uploaded_file,
                    data_only=True,
                )

                sheet = workbook.active

                admission_column = None
                score_column = None

                for index, cell in enumerate(
                    sheet[1],
                    1,
                ):
                    header = (
                        str(cell.value)
                        .lower()
                        .strip()
                        if cell.value
                        else ""
                    )

                    if any(
                        term in header
                        for term in (
                            "admission",
                            "adm",
                            "reg",
                        )
                    ):
                        admission_column = index

                    elif any(
                        term in header
                        for term in (
                            "score",
                            "mark",
                            "result",
                        )
                    ):
                        score_column = index

                if (
                    admission_column is None
                    or score_column is None
                ):
                    messages.error(
                        request,
                        (
                            'Excel file must contain '
                            '"Admission Number" and '
                            '"Score" columns.'
                        ),
                    )
                    return redirect(upload_url)

                processed = 0
                errors = []

                max_score = Decimal(
                    str(exam.max_score or 100)
                )

                with transaction.atomic():
                    for row_number, row in enumerate(
                        sheet.iter_rows(
                            min_row=2,
                            values_only=True,
                        ),
                        start=2,
                    ):
                        if not row:
                            continue

                        admission_value = (
                            row[admission_column - 1]
                            if admission_column - 1
                            < len(row)
                            else None
                        )

                        score_value = (
                            row[score_column - 1]
                            if score_column - 1
                            < len(row)
                            else None
                        )

                        admission_number = (
                            str(admission_value).strip()
                            if admission_value is not None
                            else None
                        )

                        if (
                            not admission_number
                            or score_value is None
                        ):
                            continue

                        try:
                            score = Decimal(
                                str(score_value)
                            )
                        except Exception:
                            errors.append(
                                (
                                    f"Row {row_number}: "
                                    f"Invalid score "
                                    f"'{score_value}'."
                                )
                            )
                            continue

                        if (
                            score < 0
                            or score > max_score
                        ):
                            errors.append(
                                (
                                    f"Row {row_number}: "
                                    f"Score {score} is outside "
                                    f"the range 0-{max_score}."
                                )
                            )
                            continue

                        student = (
                            Student.objects.filter(
                                admission_number=(
                                    admission_number
                                ),
                                is_active=True,
                            )
                            .first()
                        )

                        if not student:
                            errors.append(
                                (
                                    f"Row {row_number}: "
                                    f"Student "
                                    f"'{admission_number}' "
                                    "was not found."
                                )
                            )
                            continue

                        StudentResult.objects.update_or_create(
                            student=student,
                            exam=exam,
                            subject=subject,
                            defaults={
                                "score": score,
                                "entered_by": request.user,
                            },
                        )

                        processed += 1

                if processed:
                    messages.success(
                        request,
                        (
                            f"Successfully processed "
                            f"{processed} result(s) for "
                            f"{exam.name} - "
                            f"{subject.name}."
                        ),
                    )
                else:
                    messages.warning(
                        request,
                        "No valid results were found.",
                    )

                for error in errors[:5]:
                    messages.warning(
                        request,
                        error,
                    )

                if len(errors) > 5:
                    messages.warning(
                        request,
                        (
                            f"...and "
                            f"{len(errors) - 5} more errors."
                        ),
                    )

                return redirect(exam_list_url)

            except Exam.DoesNotExist:
                messages.error(
                    request,
                    "The selected exam was not found.",
                )

            except Subject.DoesNotExist:
                messages.error(
                    request,
                    "The selected subject was not found.",
                )

            except Exception as error:
                messages.error(
                    request,
                    f"Error processing file: {error}",
                )

        context = {
            "exams": exams,
            "subjects": subjects,
            "title": "Bulk Excel Upload",
            "school": SchoolSetting.objects.first(),
            "tenant_schema": schema_name,
            "current_tenant_schema": schema_name,
            "tenant_prefix": schema_name,
            "tenant_base_url": tenant_base_url,
            "tenant_exam_list_url": exam_list_url,
            "tenant_upload_url": upload_url,
        }

        return render(
            request,
            "performance/bulk_excel_upload.html",
            context,
        )



@staff_member_required
def exam_create(request, tenant_schema=None):
    """
    Create a new exam - tenant-safe version
    """
    from django.db import connection
    from django.contrib import messages
    from django.shortcuts import render, redirect
    from .forms import ExamForm
    from .models import SchoolSetting

    # Resolve tenant schema safely
    tenant_schema = (
        tenant_schema
        or getattr(request, "tenant_schema", None)
        or getattr(getattr(request, "tenant", None), "schema_name", None)
        or getattr(connection, "schema_name", None)
        or "nyaneje"
    )

    tenant_schema = str(tenant_schema).strip()

    if tenant_schema in ["", "public", "None", "none", "null", "undefined"]:
        tenant_schema = "nyaneje"

    tenant_base_url = f"/tenant/{tenant_schema}/app"

    exam_list_url = f"{tenant_base_url}/exams/"
    exam_create_url = f"{tenant_base_url}/exams/create/"
    performance_url = f"{tenant_base_url}/performance/"
    dashboard_url = f"{tenant_base_url}/dashboard/"

    if request.method == "POST":
        form = ExamForm(request.POST)

        if form.is_valid():
            exam = form.save()
            messages.success(request, f'Exam "{exam.name}" created successfully!')

            # Tenant-safe redirect
            return redirect(exam_list_url)

        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
    else:
        form = ExamForm()

    context = {
        "form": form,
        "title": "Create New Exam",
        "school": SchoolSetting.objects.first(),

        # Tenant-safe context
        "tenant_schema": tenant_schema,
        "current_tenant_schema": tenant_schema,
        "tenant_prefix": tenant_schema,
        "tenant_base_url": tenant_base_url,

        # Tenant-safe URLs
        "tenant_exam_list_url": exam_list_url,
        "tenant_exam_create_url": exam_create_url,
        "tenant_exams_url": exam_list_url,
        "tenant_performance_url": performance_url,
        "tenant_dashboard_url": dashboard_url,
    }

    return render(request, "performance/exam_form.html", context)
@staff_member_required
def subject_grading_config(request, subject_id):
    """Allow teachers to customize grading for a specific subject"""
    from .models import Subject, GradingSystem, SubjectGradingConfig, GradeScale
    
    subject = get_object_or_404(Subject, id=subject_id)
    school_system = GradingSystem.objects.filter(is_default=True, is_active=True).first()
    
    # Get or create config for current year/term
    academic_year = request.GET.get('year', str(timezone.now().year))
    term = request.GET.get('term', '1')
    
    config, created = SubjectGradingConfig.objects.get_or_create(
        subject=subject,
        grading_system=school_system,
        academic_year=academic_year,
        term=term,
        defaults={
            'max_score': 100,
            'passing_score': 50,
            'exam_weight': 70,
            'coursework_weight': 30,
            'is_active': True
        }
    )
    
    if request.method == 'POST':
        # Update grading configuration
        config.passing_score = request.POST.get('passing_score', 50)
        config.max_score = request.POST.get('max_score', 100)
        config.exam_weight = request.POST.get('exam_weight', 70)
        config.coursework_weight = request.POST.get('coursework_weight', 30)
        config.save()
        
        # Update grade scales for this subject
        grade_ids = request.POST.getlist('grade_id')
        grades = request.POST.getlist('grade[]')
        min_scores = request.POST.getlist('min_score[]')
        max_scores = request.POST.getlist('max_score[]')
        points = request.POST.getlist('points[]')
        
        for i, grade in enumerate(grades):
            if grade and min_scores[i] and max_scores[i]:
                GradeScale.objects.update_or_create(
                    id=grade_ids[i] if i < len(grade_ids) and grade_ids[i] else None,
                    defaults={
                        'grading_system': school_system,
                        'grade': grade,
                        'min_score': min_scores[i],
                        'max_score': max_scores[i],
                        'points': points[i] if i < len(points) else 0,
                        'is_active': True
                    }
                )
        
        messages.success(request, f'Grading configuration updated for {subject.name}')
        return redirect('digitallibrary:subject_grading_config', subject_id=subject.id)
    
    context = {
        'subject': subject,
        'config': config,
        'grade_scales': school_system.grades.all().order_by('-min_score'),
        'school_system': school_system,
        'academic_year': academic_year,
        'term': term,
    }
    return render(request, 'digitallibrary/subject_grading_config.html', context)
# digitallibrary/views.py

@staff_member_required
def knec_cbe_grading(request):
    """Display KNEC CBE Grading System"""
    from .models import KNECCBEGrade
    import json
    
    grades = KNECCBEGrade.objects.filter(is_active=True).order_by('order')
    
    # Convert grades to JSON for JavaScript
    grades_json = json.dumps([
        {
            'level': g.level,
            'level_name': g.level_name,
            'min_score': float(g.min_score),
            'max_score': float(g.max_score),
            'points': int(g.points),
            'placement': g.placement,
            'description': g.description
        }
        for g in grades
    ])
    
    context = {
        'grades': grades,
        'grades_json': grades_json,
        'title': 'KNEC CBE Grading System',
    }
    return render(request, 'digitallibrary/knec_cbe_grading.html', context)


# Initialize default grades on system start
def initialize_grading_system():
    """Run this in your management command or app ready signal"""
    from .models import KNECCBEGrade
    KNECCBEGrade.initialize_default_grades()

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db import connection
from django_tenants.utils import get_tenant
from . import models

def is_admin_or_principal(user):
    """Check if user is admin or principal"""
    if user.is_authenticated and (user.is_superuser or user.is_staff):
        return True
    if hasattr(user, 'profile'):
        return user.profile.role in ['admin', 'principal']
    return False

@login_required
@user_passes_test(is_admin_or_principal)
def feedback_admin(request):
    """Admin view to manage all feedback using raw SQL"""
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    rating_filter = request.GET.get('rating', '')
    
    # Build SQL query
    sql = """
        SELECT id, user_name, user_email, feedback_type, priority, 
               subject, message, rating, status, school_name, 
               created_at, is_resolved, admin_response
        FROM digitallibrary_feedback
        WHERE 1=1
    """
    params = []
    
    if status_filter:
        sql += " AND status = %s"
        params.append(status_filter)
    
    if type_filter:
        sql += " AND feedback_type = %s"
        params.append(type_filter)
    
    if rating_filter:
        sql += " AND rating = %s"
        params.append(int(rating_filter))
    
    sql += " ORDER BY created_at DESC LIMIT 100"
    
    # Get feedback
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        feedbacks = cursor.fetchall()
    
    # Get statistics
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM digitallibrary_feedback")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM digitallibrary_feedback WHERE status = 'pending'")
        pending = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM digitallibrary_feedback WHERE status = 'resolved'")
        resolved = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM digitallibrary_feedback WHERE status = 'reviewing'")
        reviewing = cursor.fetchone()[0]
        
        cursor.execute("SELECT COALESCE(AVG(rating), 0) FROM digitallibrary_feedback WHERE rating > 0")
        avg_rating = cursor.fetchone()[0]
        
        # Get by type
        cursor.execute("""
            SELECT feedback_type, COUNT(*) 
            FROM digitallibrary_feedback 
            GROUP BY feedback_type
        """)
        by_type = cursor.fetchall()
        
        # Get by rating
        cursor.execute("""
            SELECT rating, COUNT(*) 
            FROM digitallibrary_feedback 
            WHERE rating > 0
            GROUP BY rating 
            ORDER BY rating DESC
        """)
        by_rating = cursor.fetchall()
    
    feedback_types = [
        ('bug', 'Bug Report'), ('feature', 'Feature Request'),
        ('improvement', 'Improvement'), ('general', 'General Feedback'),
        ('issue', 'System Issue'), ('training', 'Training Request'),
        ('suggestion', 'Suggestion'), ('complaint', 'Complaint'),
        ('inquiry', 'Inquiry'),
    ]
    
    status_choices = [
        ('pending', 'Pending'), ('reviewing', 'Under Review'),
        ('in_progress', 'In Progress'), ('resolved', 'Resolved'),
        ('closed', 'Closed'), ('rejected', 'Rejected'),
    ]
    
    context = {
        'feedbacks': feedbacks,
        'stats': {
            'total': total,
            'pending': pending,
            'resolved': resolved,
            'reviewing': reviewing,
            'average_rating': round(float(avg_rating), 1) if avg_rating else 0,
            'by_type': by_type,
            'by_rating': by_rating,
        },
        'current_filter': {
            'status': status_filter,
            'type': type_filter,
            'rating': rating_filter,
        },
        'feedback_types': feedback_types,
        'status_choices': status_choices,
    }
    
    return render(request, 'digitallibrary/feedback_admin.html', context)

@login_required
@user_passes_test(is_admin_or_principal)
def resolve_feedback(request, feedback_id):
    """Mark feedback as resolved using raw SQL"""
    if request.method == 'POST':
        admin_response = request.POST.get('admin_response', '')
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE digitallibrary_feedback 
                SET status = 'resolved', is_resolved = TRUE, 
                    resolved_at = NOW(), admin_response = %s
                WHERE id = %s
            """, [admin_response, feedback_id])
        messages.success(request, "Feedback marked as resolved!")
    
    return redirect('digitallibrary:feedback_admin')

@login_required
@user_passes_test(is_admin_or_principal)
def delete_feedback(request, feedback_id):
    """Delete feedback using raw SQL"""
    if request.method == 'POST':
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM digitallibrary_feedback WHERE id = %s", [feedback_id])
        messages.success(request, "Feedback deleted successfully!")
    
    return redirect('digitallibrary:feedback_admin')

@login_required
def feedback_list(request):
    """Public feedback list view using raw SQL"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, user_name, feedback_type, rating, message, 
                   created_at, admin_response, status
            FROM digitallibrary_feedback 
            WHERE is_public = TRUE AND status = 'resolved'
            ORDER BY created_at DESC 
            LIMIT 20
        """)
        feedbacks = cursor.fetchall()
    
    return render(request, 'digitallibrary/feedback_list.html', {'feedbacks': feedbacks})
# Add at the top with other imports
from django.contrib.auth import logout
from django.shortcuts import redirect

# Add this function at the end of the file
   
@login_required
def debug_session(request, tenant_schema=None):
    """Debug view to check authentication status"""
    return JsonResponse({
        'authenticated': request.user.is_authenticated,
        'username': request.user.username,
        'role': request.user.profile.role if hasattr(request.user, 'profile') else None,
        'session_key': request.session.session_key,
        'tenant': request.session.get('tenant_schema'),
    })
def tv_schedule(request, tenant_schema=None, *args, **kwargs):
    from django.shortcuts import render, redirect
    from django.contrib import messages
    from django.db import connection
    from .models import TVDisplay

    if not tenant_schema:
        tenant_schema = getattr(request, "tenant_schema", None)

    if not tenant_schema:
        tenant_schema = getattr(connection, "schema_name", None)

    if not tenant_schema or tenant_schema == "public":
        tenant_schema = "nyaneje"

    request.tenant_schema = tenant_schema

    if hasattr(request, "session"):
        request.session["tenant_schema"] = tenant_schema
        request.session.modified = True

    tv = TVDisplay.objects.filter(is_active=True).order_by("id").first()

    if tv is None:
        tv = TVDisplay.objects.create(
            name=f"{tenant_schema.title()} School TV",
            is_active=True,
            layout="split",
            theme="dark",
            refresh_interval=30,
            display_duration=10,
            show_clock=True,
            show_weather=True,
            show_news_ticker=True,
            show_noticeboard=True,
            show_events=True,
            show_exam_schedule=True,
            footer_text="ShuleHub TV - Keeping You Informed",
            accent_color="#3b82f6",
            background_color="#0f172a",
            text_color="#ffffff",
        )

    if request.method == "POST":
        # keep your existing schedule-saving logic here
        messages.success(request, "TV schedule updated successfully.")
        return redirect("digitallibrary:tv_schedule", tenant_schema=tenant_schema)

    context = {
        "tv": tv,
        "tenant_schema": tenant_schema,
    }

    return render(request, "digitallibrary/tv/schedule.html", context)
