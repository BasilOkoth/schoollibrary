# schoollibrary/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.http import HttpResponse


# ============================================================
# HEALTH CHECKS
# ============================================================

def health_check(request):
    return HttpResponse(
        "OK",
        content_type="text/plain"
    )


# ============================================================
# TENANT HOME REDIRECT
# ============================================================

def tenant_home(request, tenant_schema):
    """
    Redirect to tenant dashboard
    """
    return redirect(
        f"/tenant/{tenant_schema}/app/"
    )


# ============================================================
# URL PATTERNS
# ============================================================

urlpatterns = [

    # ========================================================
    # HEALTH CHECKS
    # ========================================================

    path(
        "healthz/",
        health_check
    ),

    path(
        "health/",
        health_check
    ),

    # ========================================================
    # ROOT REDIRECT
    # ========================================================

    path(
        "",
        lambda request: redirect("/admin/")
    ),

    # ========================================================
    # PUBLIC ADMIN
    # ========================================================

    path(
        "admin/",
        admin.site.urls
    ),

    # ========================================================
    # AUTHENTICATION
    # ========================================================

    path(
        "accounts/",
        include("django.contrib.auth.urls")
    ),

    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="digitallibrary/login.html"
        ),
        name="login"
    ),

    # ========================================================
    # TENANT ROUTES
    # ========================================================

    # Tenant root
    path(
        "tenant/<str:tenant_schema>/",
        tenant_home,
        name="tenant_home"
    ),

    # Tenant application
    path(
        "tenant/<str:tenant_schema>/app/",
        include(
            (
                "digitallibrary.urls",
                "digitallibrary"
            ),
            namespace="digitallibrary"
        )
    ),

    # Tenant library alias
    path(
        "tenant/<str:tenant_schema>/library/",
        include(
            (
                "digitallibrary.urls",
                "digitallibrary"
            ),
            namespace="digitallibrary_alias"
        )
    ),

    # ========================================================
    # OPTIONAL LEGACY ROUTES
    # ========================================================

    # These can help during transition/testing

    path(
        "app/",
        include(
            (
                "digitallibrary.urls",
                "digitallibrary"
            ),
            namespace="digitallibrary_legacy"
        )
    ),

    path(
        "library/",
        include(
            (
                "digitallibrary.urls",
                "digitallibrary"
            ),
            namespace="digitallibrary_library_legacy"
        )
    ),

    # ========================================================
    # PWA / OFFLINE SUPPORT
    # ========================================================

    path(
        "offline/",
        TemplateView.as_view(
            template_name="offline.html"
        ),
        name="offline"
    ),

    path(
        "manifest.json/",
        TemplateView.as_view(
            template_name="manifest.json",
            content_type="application/json"
        ),
        name="manifest"
    ),
]


# ============================================================
# STATIC FILES
# ============================================================

urlpatterns += static(
    settings.STATIC_URL,
    document_root=settings.STATIC_ROOT
)


# ============================================================
# MEDIA FILES
# ============================================================

urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)