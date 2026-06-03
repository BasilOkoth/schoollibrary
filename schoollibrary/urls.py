# schoollibrary/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect, render
from django.views.generic import TemplateView, RedirectView
from django.http import HttpResponse
import logging

logger = logging.getLogger(__name__)


# ========== SIMPLE, RELIABLE VIEWS ==========
def health_check(request):
    """Health check endpoint for Render."""
    return HttpResponse("OK", content_type="text/plain")


def landing_page(request):
    """Public landing page - NO login required."""
    return HttpResponse("""
    <!DOCTYPE html>
    <html>
    <head><title>ShuleHub</title></head>
    <body style="font-family: Arial; text-align: center; padding: 50px;">
        <h1>🏫 ShuleHub</h1>
        <p>School Management System</p>
        <hr>
        <p><a href="/tenant/demo/app/login/">Login to Demo Tenant</a></p>
        <p><a href="/admin/">Admin Panel</a></p>
        <p><a href="/healthz/">Health Check</a></p>
    </body>
    </html>
    """)


def tenant_home(request, tenant_schema):
    """Redirect to the app for a specific tenant."""
    return redirect(f'/tenant/{tenant_schema}/app/')


# ========== URL PATTERNS ==========
urlpatterns = [
    # Health checks
    path('healthz/', health_check, name='healthz'),
    path('health/', health_check, name='health'),

    # Landing page
    path('', landing_page, name='home'),
    path('landing/', landing_page, name='landing_page'),

    # Admin
    path('admin/', admin.site.urls),
    path('superadmin/', include('superadmin.urls')),

    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='digitallibrary/login.html', redirect_authenticated_user=True), name='login'),
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

    # Apps
    path('mpesa/', include('mpesa.urls')),
    path('tenants/', include('tenants.urls')),

    # ***** TENANT ROUTES *****
    # These must come BEFORE the main app routes
    path('tenant/<str:tenant_schema>/', tenant_home, name='tenant_home'),
    path('tenant/<str:tenant_schema>/app/', include('digitallibrary.urls')),
    path('tenant/<str:tenant_schema>/library/', include('digitallibrary.urls')),

    # ***** MAIN APP ROUTES *****
    # These will work on the public domain (shulehub.org/app/)
    path('app/', include('digitallibrary.urls')),
    path('library/', include('digitallibrary.urls')),

    # PWA
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
    path('manifest.json/', TemplateView.as_view(template_name='manifest.json', content_type='application/json'), name='manifest'),
]

# Static and media files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
