from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect
from django.views.generic import TemplateView, RedirectView
from django.http import HttpResponse, JsonResponse
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def health_check(request):
    return HttpResponse("OK", content_type="text/plain")


def home_redirect(request):
    return redirect("/app/")


def tenant_home(request, tenant_schema):
    return redirect(f"/tenant/{tenant_schema}/app/")


def wrap_admin(view_func):
    @wraps(view_func)
    def wrapper(request, tenant_schema=None, **kwargs):
        from django.db import connection
        connection.set_schema("public")
        return view_func(request, **kwargs)
    return wrapper


def debug_app(request):
    from django.db import connection

    tenant_info = "No tenant"
    try:
        if hasattr(request, "tenant") and request.tenant:
            tenant_info = {
                "schema": request.tenant.schema_name,
                "name": getattr(request.tenant, "name", ""),
            }
    except Exception as e:
        tenant_info = f"Error getting tenant: {str(e)}"

    return JsonResponse({
        "host": request.get_host(),
        "path": request.path,
        "method": request.method,
        "current_schema": connection.schema_name,
        "tenant_info": tenant_info,
        "is_authenticated": request.user.is_authenticated,
        "user": str(request.user) if request.user.is_authenticated else "Anonymous",
        "session_key": request.session.session_key,
    }, json_dumps_params={"indent": 2})


urlpatterns = [
    # Health checks
    path("healthz/", health_check, name="healthz"),
    path("health/", health_check, name="health"),

    # Debug
    path("debug-app/", debug_app, name="debug_app"),

    # Root
    path("", home_redirect, name="home"),

    # Public admin
    path("admin/", admin.site.urls),

    # Other apps
    path("superadmin/", include("superadmin.urls")),
    path("mpesa/", include("mpesa.urls")),
    path("tenants/", include("tenants.urls")),

    # Global auth fallback
    path("accounts/login/", RedirectView.as_view(url="/login/", permanent=False), name="accounts_login"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="digitallibrary/login.html",
            redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="/login/"), name="logout"),

    # Password reset
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="digitallibrary/password_reset.html",
            email_template_name="digitallibrary/password_reset_email.html",
            success_url="/password-reset/done/",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="digitallibrary/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="digitallibrary/password_reset_confirm.html",
            success_url="/password-reset-complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="digitallibrary/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),

    # Tenant-specific routes
    path("tenant/<str:tenant_schema>/", tenant_home, name="tenant_home"),

    path(
        "tenant/<str:tenant_schema>/app/",
        include(("digitallibrary.urls", "digitallibrary"), namespace="tenant_app"),
    ),

    path(
        "tenant/<str:tenant_schema>/admin/",
        wrap_admin(admin.site.urls),
    ),

    path(
        "tenant/<str:tenant_schema>/library/",
        include(("digitallibrary.urls", "digitallibrary"), namespace="tenant_lib"),
    ),

    # Public/default app routes
    path(
        "app/",
        include(("digitallibrary.urls", "digitallibrary"), namespace="digitallibrary"),
    ),

    path(
        "library/",
        include(("digitallibrary.urls", "digitallibrary"), namespace="digitallibrary_alias"),
    ),

    # PWA
    path("offline/", TemplateView.as_view(template_name="offline.html"), name="offline"),
    path(
        "manifest.json/",
        TemplateView.as_view(
            template_name="manifest.json",
            content_type="application/json",
        ),
        name="manifest",
    ),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
