# schoollibrary/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect
from django.views.generic import TemplateView, RedirectView
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
import logging

logger = logging.getLogger(__name__)


def health_check(request):
    """Health check endpoint for Render"""
    return HttpResponse("OK", content_type="text/plain")


def landing_page(request):
    """Public landing page - no login required"""
    from django.shortcuts import render
    from django.core.cache import cache
    from django.db.models import Sum
    from django_tenants.utils import schema_context
    
    metrics = cache.get("landing_page_metrics")
    if not metrics:
        metrics = {
            "total_schools": 0,
            "total_teachers": 0,
            "total_students": 0,
            "total_resources": 0,
        }
        try:
            from tenants.models import School
            from digitallibrary.models import UserProfile, Resource
            with schema_context("public"):
                schools = School.objects.filter(is_active=True)
                metrics["total_schools"] = schools.count()
                for school in schools:
                    try:
                        with schema_context(school.schema_name):
                            metrics["total_teachers"] += UserProfile.objects.filter(role="teacher", is_approved=True).count()
                            metrics["total_resources"] += Resource.objects.count()
                    except Exception:
                        pass
        except Exception:
            pass
        cache.set("landing_page_metrics", metrics, 3600)
    
    return render(request, "digitallibrary/landing_page.html", {"metrics": metrics})


def tenant_home(request, tenant_schema):
    """Redirect to the app for a specific tenant"""
    return redirect(f'/tenant/{tenant_schema}/app/')


# ========== URL PATTERNS ==========
urlpatterns = [
    # Health checks
    path('healthz/', health_check),
    path('health/', health_check),
    
    # Public landing page
    path('', landing_page, name='home'),
    path('landing/', landing_page, name='landing_page'),
    
    # Admin
    path('admin/', admin.site.urls),
    path('superadmin/', include('superadmin.urls')),
    
    # Authentication (public)
    path('accounts/login/', RedirectView.as_view(url='/login/', permanent=False), name='accounts_login'),
    path('login/', auth_views.LoginView.as_view(template_name='digitallibrary/login.html', redirect_authenticated_user=True), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='accounts_logout'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    
    # Password reset
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='digitallibrary/password_reset.html',
        email_template_name='digitallibrary/password_reset_email.html',
        success_url='/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='digitallibrary/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='digitallibrary/password_reset_confirm.html',
        success_url='/password-reset-complete/',
    ), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='digitallibrary/password_reset_complete.html',
    ), name='password_reset_complete'),
    
    # M-Pesa
    path('mpesa/', include('mpesa.urls')),
    path('tenants/', include('tenants.urls')),
    
    # Tenant routes - CRITICAL: These must be before the app routes
    path('tenant/<str:tenant_schema>/', tenant_home, name='tenant_home'),
    path('tenant/<str:tenant_schema>/app/', include('digitallibrary.urls')),
    path('tenant/<str:tenant_schema>/library/', include('digitallibrary.urls')),
    
    # Main app routes (uses public schema or session tenant)
    path('app/', include('digitallibrary.urls')),
    path('library/', include('digitallibrary.urls')),
    
    # PWA / Offline
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
    path('manifest.json/', TemplateView.as_view(template_name='manifest.json', content_type='application/json'), name='manifest'),
]

# Static and media files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
