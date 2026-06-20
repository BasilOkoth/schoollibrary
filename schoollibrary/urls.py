from functools import wraps
import logging
from tenants import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView


logger = logging.getLogger(__name__)


def health_check(request):
    """
    Render health check endpoint.
    Must return 200 OK quickly.
    """
    return HttpResponse("OK", content_type="text/plain")


def home_redirect(request):
    """
    Public root redirect.
    This sends public visitors to the public app route.
    """
    return redirect("/app/")


def tenant_home(request, tenant_schema):
    """
    Redirect /tenant/<schema>/ to /tenant/<schema>/app/
    """
    return redirect(f"/tenant/{tenant_schema}/app/")


def smart_login_redirect(request):
    """
    Tenant-aware login redirect.

    If Django redirects a protected tenant page to LOGIN_URL=/smart-login/,
    this function reads the ?next= value and sends the user to the correct
    tenant login page.

    Super-admin pages go to the public login page and then return to
    /tenants/super-admin/.
    """
    next_url = request.GET.get("next", "")

    if next_url.startswith("/tenants/super-admin"):
        return redirect(f"/login/?next={next_url}")

    if next_url.startswith("/tenant/"):
        parts = next_url.strip("/").split("/")

        if len(parts) >= 2:
            tenant_schema = parts[1]

            return redirect(
                f"/tenant/{tenant_schema}/app/login/?next={next_url}"
            )

    return redirect(
        f"/login/?next={next_url}"
        if next_url
        else "/login/"
    )


class SuperAdminAwareLoginView(auth_views.LoginView):
    """
    Public login view with correct super-admin redirect.

    Without this, Django can use LOGIN_REDIRECT_URL and send the super user
    to /app/dashboard/, which your app treats as the public landing page.
    """

    template_name = "digitallibrary/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        next_url = self.get_redirect_url()

        if user.is_superuser or user.is_staff:
            if next_url and next_url.startswith("/tenants/super-admin"):
                return next_url

            return "/tenants/super-admin/"

        if next_url:
            return next_url

        tenant_schema = (
            self.request.session.get("tenant_schema")
            or self.request.POST.get("tenant_schema")
            or self.request.GET.get("tenant_schema")
        )

        if tenant_schema and tenant_schema != "public":
            return f"/tenant/{tenant_schema}/app/dashboard/"

        return "/app/"


def wrap_admin(view_func):
    """
    Force tenant admin wrapper to use public schema.
    """

    @wraps(view_func)
    def wrapper(request, tenant_schema=None, **kwargs):
        from django.db import connection

        connection.set_schema("public")

        return view_func(request, **kwargs)

    return wrapper


def debug_app(request):
    """
    Debug endpoint to inspect tenant/session/auth state.
    Remove or protect this later in production.
    """
    from django.db import connection

    tenant_info = "No tenant"

    try:
        if hasattr(request, "tenant") and request.tenant:
            tenant_info = {
                "schema": request.tenant.schema_name,
                "name": getattr(request.tenant, "name", ""),
            }
    except Exception as error:
        tenant_info = f"Error getting tenant: {error}"

    return JsonResponse(
        {
            "host": request.get_host(),
            "path": request.path,
            "method": request.method,
            "current_schema": connection.schema_name,
            "tenant_info": tenant_info,
            "is_authenticated": request.user.is_authenticated,
            "user": (
                str(request.user)
                if request.user.is_authenticated
                else "Anonymous"
            ),
            "session_key": request.session.session_key,
            "tenant_schema_in_session": request.session.get(
                "tenant_schema"
            ),
        },
        json_dumps_params={"indent": 2},
    )


urlpatterns = [
    # --------------------------------------------------
    # Health checks - keep these first for Render
    # --------------------------------------------------
    path("healthz/", health_check, name="healthz"),
    path("health/", health_check, name="health"),

    # --------------------------------------------------
    # Debug
    # --------------------------------------------------
    path("debug-app/", debug_app, name="debug_app"),

    # --------------------------------------------------
    # Root
    # --------------------------------------------------
    path("", home_redirect, name="home"),

    # --------------------------------------------------
    # Public admin
    # --------------------------------------------------
    path("admin/", admin.site.urls),

    # --------------------------------------------------
    # Other apps
    # --------------------------------------------------
    path("superadmin/", include("superadmin.urls")),
    path("mpesa/", include("mpesa.urls")),
    path("tenants/", include("tenants.urls")),
    path('tenants/<int:tenant_id>/fix-migrations/', views.fix_tenant_migrations, name='fix_tenant_migrations'),
    # --------------------------------------------------
    # Smart login for tenant-safe login persistence
    # --------------------------------------------------
    path("smart-login/", smart_login_redirect, name="smart_login"),

    # --------------------------------------------------
    # Global auth fallback
    # --------------------------------------------------
    path(
        "accounts/login/",
        RedirectView.as_view(
            url="/login/",
            permanent=False,
        ),
        name="accounts_login",
    ),
    path(
        "login/",
        SuperAdminAwareLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="/login/"),
        name="logout",
    ),

    # --------------------------------------------------
    # Password reset
    # --------------------------------------------------
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

    # --------------------------------------------------
    # Tenant-specific routes
    # --------------------------------------------------
    path(
        "tenant/<str:tenant_schema>/",
        tenant_home,
        name="tenant_home",
    ),

    # --------------------------------------------------
    # Tenant backup dashboard
    # IMPORTANT:
    # This must come before tenant/<schema>/app/ because otherwise
    # digitallibrary.urls may catch the request first and return 404.
    # --------------------------------------------------
    path(
        "tenant/<str:tenant_schema>/app/tenant-backups/",
        include(
            ("tenantbackups.urls", "tenantbackups"),
            namespace="tenantbackups_tenant",
        ),
    ),

    path(
        "tenant/<str:tenant_schema>/app/",
        include(
            ("digitallibrary.urls", "digitallibrary"),
            namespace="tenant_app",
        ),
    ),
    path(
        "tenant/<str:tenant_schema>/admin/",
        wrap_admin(admin.site.urls),
    ),
    path(
        "tenant/<str:tenant_schema>/library/",
        include(
            ("digitallibrary.urls", "digitallibrary"),
            namespace="tenant_lib",
        ),
    ),

    # --------------------------------------------------
    # Old/public backup URLs
    # --------------------------------------------------
    # These routes must not open TenantBackup in public schema.
    # They are kept only as safe redirects for old browser links.
    path(
        "app/tenant-backups/",
        RedirectView.as_view(
            url="/tenant/nyandago/app/tenant-backups/",
            permanent=False,
        ),
        name="tenantbackups_public_redirect",
    ),
    path(
        "app/backup/",
        RedirectView.as_view(
            url="/tenant/nyandago/app/tenant-backups/",
            permanent=False,
        ),
        name="old_backup_redirect",
    ),

    # --------------------------------------------------
    # Public/default app routes
    # --------------------------------------------------
    path(
        "app/",
        include(
            ("digitallibrary.urls", "digitallibrary"),
            namespace="digitallibrary",
        ),
    ),

    path(
        "library/",
        include(
            ("digitallibrary.urls", "digitallibrary"),
            namespace="digitallibrary_alias",
        ),
    ),

    # --------------------------------------------------
    # PWA
    # --------------------------------------------------
    path(
        "offline/",
        TemplateView.as_view(template_name="offline.html"),
        name="offline",
    ),
    path(
        "manifest.json/",
        TemplateView.as_view(
            template_name="manifest.json",
            content_type="application/json",
        ),
        name="manifest",
    ),
]


urlpatterns += static(
    settings.STATIC_URL,
    document_root=settings.STATIC_ROOT,
)

if hasattr(settings, "MEDIA_URL"):
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=getattr(settings, "MEDIA_ROOT", None),
    )
