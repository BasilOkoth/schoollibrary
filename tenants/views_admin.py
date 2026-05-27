# tenants/views_admin.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django_tenants.utils import schema_context, tenant_context
from .models import School, Domain, SuperAdminProfile
from django.contrib.auth import get_user_model

User = get_user_model()


@login_required
def super_admin_required(view_func):
    """Decorator to ensure user is super admin"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login first')
            return redirect('/login/')
        if not request.user.is_superuser:
            messages.error(request, 'Access denied. Super admin privileges required.')
            return redirect('/app/dashboard/')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@super_admin_required
def super_admin_dashboard(request):
    """Super admin dashboard"""
    with schema_context('public'):
        # Get all schools
        schools = School.objects.all().order_by('-created_at')
        
        # Statistics
        total_schools = schools.count()
        active_schools = schools.filter(is_active=True).count()
        trial_schools = schools.filter(on_trial=True).count()
        
        # Pagination
        paginator = Paginator(schools, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        context = {
            'schools': page_obj,
            'total_schools': total_schools,
            'active_schools': active_schools,
            'trial_schools': trial_schools,
            'page_obj': page_obj,
        }
        return render(request, 'tenants/super_admin/dashboard.html', context)


@login_required
@super_admin_required
def create_superuser(request):
    """Create additional superuser"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        with schema_context('public'):
            if User.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" already exists')
                return redirect('tenants:super_admin_dashboard')
            
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            user.is_staff = True
            user.save()
            
            messages.success(request, f'Superuser "{username}" created successfully')
            return redirect('tenants:super_admin_dashboard')
    
    return render(request, 'tenants/super_admin/create_superuser.html')