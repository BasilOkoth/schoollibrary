from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.http import HttpResponse


def health_check(request):
    """Health check endpoint for Render"""
    return HttpResponse("OK", content_type="text/plain")


def root_redirect(request):
    """Redirect root URL to admin panel"""
    return redirect('/admin/')


urlpatterns = [
    # Health checks
    path('healthz/', health_check, name='health_check'),
    path('health/', health_check, name='health_alt'),
    
    # Root URL - THIS FIXES THE 404
    path('', root_redirect, name='home'),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # Authentication
    path('accounts/', include("django.contrib.auth.urls")),
    path('login/', auth_views.LoginView.as_view(template_name="digitallibrary/login.html"), name='login'),
    
    # Main app
    path('app/', include(("digitallibrary.urls", "digitallibrary"), namespace='digitallibrary')),
    path('library/', include(("digitallibrary.urls", "digitallibrary"), namespace='digitallibrary_alias')),
    
    # PWA / Offline
    path('offline/', TemplateView.as_view(template_name="offline.html"), name='offline'),
    path('manifest.json/', TemplateView.as_view(template_name="manifest.json", content_type="application/json"), name='manifest'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)