# schoollibrary/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.http import HttpResponse


def health_check(request):
    return HttpResponse("OK", content_type="text/plain")


def root_handler(request):
    """Root URL handler - redirects to admin"""
    return redirect('/admin/')


urlpatterns = [
    # Health checks
    path('healthz/', health_check, name='health_check'),
    path('health/', health_check, name='health_alt'),
    
    # Root - now redirects to admin (FIXES THE 404)
    path('', root_handler, name='home'),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # Auth
    path('accounts/', include("django.contrib.auth.urls")),
    path('login/', auth_views.LoginView.as_view(template_name="digitallibrary/login.html"), name='login'),
    
    # App routes
    path('app/', include(("digitallibrary.urls", "digitallibrary"), namespace='digitallibrary')),
    path('library/', include(("digitallibrary.urls", "digitallibrary"), namespace='digitallibrary_alias')),
    
    # PWA
    path('offline/', TemplateView.as_view(template_name="offline.html"), name='offline'),
    path('manifest.json/', TemplateView.as_view(template_name="manifest.json", content_type="application/json"), name='manifest'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)