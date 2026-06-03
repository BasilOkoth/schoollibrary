# schoollibrary/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.db.models import Sum
from django.contrib import admin
from digitallibrary import views
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.shortcuts import redirect, render
from django.views.generic import TemplateView, RedirectView
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import logout
from django.utils import timezone
import logging
import os
import re as _re

logger = logging.getLogger(__name__)


# ========== HEALTH CHECK VIEWS ==========
def health_check(request):
    """Health check endpoint for Render and monitoring."""
    from django.db import connections
    
    try:
        connections['default'].cursor()
        return HttpResponse("OK", content_type="text/plain", status=200)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HttpResponse("ERROR", content_type="text/plain", status=503)


def health_check_detailed(request):
    """Detailed health check with more information"""
    from django.db import connections
    import sys
    
    health_data = {
        "status": "healthy",
        "checks": {
            "database": "unknown",
            "django": "running",
            "python_version": sys.version,
        }
    }
    
    try:
        connections['default'].cursor()
        health_data["checks"]["database"] = "connected"
    except Exception as e:
        health_data["checks"]["database"] = f"error: {str(e)}"
        health_data["status"] = "unhealthy"
    
    return JsonResponse(health_data)


# ========== TENANT AND ROUTING HELPERS ==========
def tenant_home(request, tenant_schema):
    return redirect(f'/tenant/{tenant_schema}/app/')


def smart_login_redirect(request):
    next_url = request.GET.get('next', '')
    match = _re.match(r'^/tenant/([^/]+)/app/', next_url)
    if match:
        schema = match.group(1)
        tenant_login = f'/tenant/{schema}/app/login/'
        if next_url:
            tenant_login += f'?next={next_url}'
        return redirect(tenant_login)
    login_url = '/login/'
    if next_url:
        login_url += f'?next={next_url}'
    return redirect(login_url)


def get_default_tenant():
    try:
        from tenants.models import School
        first_tenant = School.objects.filter(is_active=True).exclude(schema_name='public').first()
        return first_tenant.schema_name if first_tenant else None
    except Exception:
        return None


def dynamic_app_redirect(request):
    tenant = request.session.get('tenant_schema')
    if not tenant:
        referer = request.META.get('HTTP_REFERER', '')
        match = _re.match(r'.*/tenant/([^/]+)/', referer)
        if match:
            tenant = match.group(1)
    if not tenant:
        tenant = get_default_tenant()
    if not tenant:
        tenant = 'public'
    return redirect(f'/tenant/{tenant}/app/')


def dynamic_app_catchall(request, remainder):
    tenant = request.session.get('tenant_schema')
    if not tenant:
        referer = request.META.get('HTTP_REFERER', '')
        match = _re.match(r'.*/tenant/([^/]+)/', referer)
        if match:
            tenant = match.group(1)
    if not tenant:
        tenant = get_default_tenant()
    if not tenant:
        tenant = 'public'
    return redirect(f'/tenant/{tenant}/app/{remainder}')


def custom_logout(request):
    logout(request)
    return redirect('/login/')


# ========== DEBUG VIEWS ==========
def debug_routing(request):
    from django.db import connection
    import sys
    debug_info = f"""
    <h1>Debug Routing Info</h1>
    <p>Host: {request.get_host()}</p>
    <p>Path: {request.path}</p>
    <p>Method: {request.method}</p>
    <p>Current Schema: {connection.schema_name}</p>
    <p>Is Authenticated: {request.user.is_authenticated}</p>
    <p>Session Key: {request.session.session_key}</p>
    <p>Python Version: {sys.version}</p>
    """
    return HttpResponse(debug_info, content_type="text/html")


def debug_app(request):
    from django.db import connection
    tenant_info = "No tenant"
    try:
        if hasattr(request, 'tenant'):
            tenant_info = f"Tenant: {request.tenant.name if request.tenant else 'None'}"
        else:
            tenant_info = "request.tenant attribute not found"
    except Exception as e:
        tenant_info = f"Error getting tenant: {str(e)}"
    debug_data = {
        'host': request.get_host(),
        'path': request.path,
        'method': request.method,
        'is_secure': request.is_secure(),
        'current_schema': connection.schema_name,
        'tenant_info': tenant_info,
        'is_authenticated': request.user.is_authenticated,
        'user': str(request.user) if request.user.is_authenticated else 'Anonymous',
        'session_key': request.session.session_key,
        'headers': dict(request.headers),
    }
    return JsonResponse(debug_data, json_dumps_params={'indent': 2})


# ========== LANDING PAGE VIEW ==========
def landing_page(request):
    from django.core.cache import cache
    from django.shortcuts import render
    from django_tenants.utils import schema_context

    metrics = cache.get("landing_page_metrics")
    if not metrics:
        metrics = {"total_schools": 0, "total_teachers": 0, "total_students": 0, "total_resources": 0, "total_views": 0, "total_accessed": 0}
        try:
            from tenants.models import School
            with schema_context("public"):
                schools = School.objects.filter(is_active=True)
                metrics["total_schools"] = schools.count()
                for school in schools:
                    try:
                        with schema_context(school.schema_name):
                            from digitallibrary.models import UserProfile, Student, Resource
                            metrics["total_teachers"] += UserProfile.objects.filter(role="teacher", is_approved=True).count()
                            metrics["total_students"] += Student.objects.filter(is_active=True).count()
                            metrics["total_resources"] += Resource.objects.count()
                            resource_views = Resource.objects.aggregate(total_views=Sum("views"))["total_views"] or 0
                            metrics["total_views"] += resource_views
                            metrics["total_accessed"] += resource_views
                    except Exception:
                        pass
        except Exception:
            pass
        cache.set("landing_page_metrics", metrics, 3600)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.GET.get("format") == "json":
        return JsonResponse(metrics)
    return render(request, "digitallibrary/landing_page.html", {"metrics": metrics})


# ========== ROBOTS.TXT ==========
def robots_txt(request):
    lines = ["User-Agent: *", "Disallow: /admin/", "Disallow: /superadmin/", "Disallow: /app/", "Allow: /", "Sitemap: https://shulehub.org/sitemap.xml"]
    return HttpResponse("\n".join(lines), content_type="text/plain")


# ========== URL PATTERNS ==========
urlpatterns = [
    path('healthz/', health_check, name='healthz'),
    path('health/', health_check, name='health'),
    path('health/detailed/', health_check_detailed, name='health_detailed'),
    path('', landing_page, name='landing_page'),
    path('landing/', landing_page, name='landing_page_alt'),
    path('debug/', debug_routing, name='debug'),
    path('debug-app/', debug_app, name='debug_app'),
    path('admin/', admin.site.urls),
    path('superadmin/', include('superadmin.urls')),
    path('smart-login/', smart_login_redirect, name='smart_login'),
    path('accounts/login/', RedirectView.as_view(url='/login/', permanent=False), name='accounts_login'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', custom_logout, name='logout'),
    path('accounts/logout/', custom_logout, name='accounts_logout'),
    path("login-redirect/", smart_login_redirect, name="smart_login_redirect"),
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='digitallibrary/password_reset.html', email_template_name='digitallibrary/password_reset_email.html', success_url='/password-reset/done/'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='digitallibrary/password_reset_done.html'), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='digitallibrary/password_reset_confirm.html', success_url='/password-reset-complete/'), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='digitallibrary/password_reset_complete.html'), name='password_reset_complete'),
    path('mpesa/', include('mpesa.urls')),
    path('robots.txt/', robots_txt, name='robots'),
]

# Tenant routes
urlpatterns += [
    path('tenant/<str:tenant_schema>/', tenant_home, name='tenant_home'),
    path('tenant/<str:tenant_schema>/app/', include(('digitallibrary.urls', 'digitallibrary'), namespace='tenant_app')),
    path('tenant/<str:tenant_schema>/library/', include(('digitallibrary.urls', 'digitallibrary'), namespace='tenant_lib')),
]

# Dynamic redirects
urlpatterns += [
    path('app/', dynamic_app_redirect, name='app_redirect'),
    path('app/<path:remainder>', dynamic_app_catchall, name='app_catchall'),
    path('library/', include(('digitallibrary.urls', 'digitallibrary'), namespace='digitallibrary_alias')),
    path('tenants/', include('tenants.urls')),
]

# Utility routes
urlpatterns += [
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
    path('manifest.json/', TemplateView.as_view(template_name='manifest.json', content_type='application/json'), name='manifest'),
    path('service-worker.js/', TemplateView.as_view(template_name='service-worker.js', content_type='application/javascript'), name='service_worker'),
    path('app/admin/', lambda request: redirect('/admin/'), name='app_admin_redirect'),
]

# Static files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    from django.contrib.staticfiles.views import serve as serve_static
    def favicon(request):
        return serve_static(request, 'favicon.ico')
    urlpatterns += [path('favicon.ico/', favicon)]
    
    def catch_all(request, path):
        logger.warning(f"Catch-all triggered for path: {path}")
        return HttpResponse(f"<h1>Page not found</h1><p>Path: {path}</p>", status=404)
    urlpatterns += [re_path(r'^(?P<path>.*)/$', catch_all)]
