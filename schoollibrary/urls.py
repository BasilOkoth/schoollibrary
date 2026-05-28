# schoollibrary/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.db.models import Sum
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.shortcuts import redirect, render
from django.views.generic import TemplateView, RedirectView
from django.views.static import serve
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import logout
import logging
import os
import re as _re

logger = logging.getLogger(__name__)


def health_check(request):
    return HttpResponse("OK", content_type="text/plain")


def tenant_home(request, tenant_schema):
    """Redirect to the app for a specific tenant"""
    return redirect(f'/tenant/{tenant_schema}/app/')


def smart_login_redirect(request):
    """
    Smart login redirector used as LOGIN_URL.
    When @login_required fires for a tenant view, ?next= contains /tenant/<schema>/...
    We redirect to that tenant's own login page instead of the public one.
    """
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


def debug_routing(request):
    """Debug view to check what's happening with routing"""
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
    """Debug view to check app routing"""
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


def landing_page(request):
    """
    Public landing page with safe platform metrics.
    """
    from django.core.cache import cache
    from django.http import JsonResponse
    from django.shortcuts import render
    from django_tenants.utils import schema_context

    metrics = cache.get("landing_page_metrics")

    if not metrics:
        metrics = {
            "total_schools": 0,
            "total_teachers": 0,
            "total_students": 0,
            "total_resources": 0,
            "total_views": 0,
            "total_accessed": 0,
        }

        try:
            from tenants.models import School

            with schema_context("public"):
                schools = School.objects.filter(is_active=True)
                metrics["total_schools"] = schools.count()

                for school in schools:
                    try:
                        with schema_context(school.schema_name):
                            from digitallibrary.models import UserProfile, Student, Resource

                            metrics["total_teachers"] += UserProfile.objects.filter(
                                role="teacher",
                                is_approved=True,
                            ).count()

                            metrics["total_students"] += Student.objects.filter(
                                is_active=True,
                            ).count()

                            metrics["total_resources"] += Resource.objects.count()

                            resource_views = Resource.objects.aggregate(
                                total_views=Sum("views")
                            )["total_views"] or 0

                            metrics["total_views"] += resource_views
                            metrics["total_accessed"] += resource_views

                    except Exception as tenant_error:
                        logger.warning(
                            f"Skipping metrics for tenant {school.schema_name}: {tenant_error}"
                        )

        except Exception as e:
            logger.error(f"Error getting landing page metrics: {str(e)}")

            metrics = {
                "total_schools": 0,
                "total_teachers": 0,
                "total_students": 0,
                "total_resources": 0,
                "total_views": 0,
                "total_accessed": 0,
            }

        cache.set("landing_page_metrics", metrics, 3600)

    if (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.GET.get("format") == "json"
    ):
        return JsonResponse(metrics)

    return render(
        request,
        "digitallibrary/landing_page.html",
        {
            "metrics": metrics,
        },
    )


def custom_logout(request):
    """Custom logout that works with GET and POST"""
    logout(request)
    return redirect('/login/')


# ========== URL PATTERNS - ORDER IS CRITICAL! ==========
urlpatterns = [
    path('', RedirectView.as_view(url='/app/', permanent=False), name='root'),

    path('landing/', landing_page, name='landing_page'),

    path('healthz/', health_check, name='healthz'),
    path('health/', health_check, name='health'),

    path('debug/', debug_routing, name='debug'),
    path('debug-app/', debug_app, name='debug_app'),

    path('admin/', admin.site.urls),

    path('superadmin/', include('superadmin.urls')),

    # ========== SMART LOGIN REDIRECTOR ==========
    path('smart-login/', smart_login_redirect, name='smart_login'),

    path('accounts/login/', RedirectView.as_view(url='/login/', permanent=False), name='accounts_login'),
    path('login/', auth_views.LoginView.as_view(
        template_name='digitallibrary/login.html',
        redirect_authenticated_user=True
    ), name='login'),

    path('logout/', custom_logout, name='logout'),
    path('accounts/logout/', custom_logout, name='accounts_logout'),

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

    path('mpesa/', include('mpesa.urls')),
]

urlpatterns += [
    path('tenant/<str:tenant_schema>/', tenant_home, name='tenant_home'),
    path('tenant/<str:tenant_schema>/app/', include(('digitallibrary.urls', 'digitallibrary'), namespace='tenant_app')),
    path('tenant/<str:tenant_schema>/library/', include(('digitallibrary.urls', 'digitallibrary'), namespace='tenant_lib')),
    path('app/', include(('digitallibrary.urls', 'digitallibrary'), namespace='digitallibrary')),
    path('library/', include(('digitallibrary.urls', 'digitallibrary'), namespace='digitallibrary_alias')),
    path('tenants/', include('tenants.urls')),
]

urlpatterns += [
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
    path('manifest.json/', TemplateView.as_view(template_name='manifest.json', content_type='application/json'), name='manifest'),
    path('service-worker.js/', TemplateView.as_view(template_name='service-worker.js', content_type='application/javascript'), name='service_worker'),
    path('app/admin/', lambda request: redirect('/admin/'), name='app_admin_redirect'),
]

if settings.DEBUG:
    def catch_all(request, path):
        logger.warning(f"Catch-all triggered for path: {path} on host: {request.get_host()}")
        return HttpResponse(f"<h1>Page not found</h1><p>Path: {path}</p><p>Host: {request.get_host()}</p>", status=404)

    urlpatterns += [
        re_path(r'^(?P<path>.*)/$', catch_all),
    ]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


def robots_txt(request):
    lines = [
        "User-Agent: *",
        "Disallow: /admin/",
        "Disallow: /superadmin/",
        "Disallow: /app/",
        "Allow: /",
        "Sitemap: https://shulehub.org/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

urlpatterns += [
    path('robots.txt/', robots_txt, name='robots'),
]

if settings.DEBUG:
    from django.contrib.staticfiles.views import serve as serve_static

    def favicon(request):
        return serve_static(request, 'favicon.ico')

    urlpatterns += [
        path('favicon.ico/', favicon),
    ]
