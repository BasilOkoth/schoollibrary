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


urlpatterns = [
    path('healthz/', health_check),
    path('health/', health_check),

    # Redirect homepage to app dashboard
    path('', lambda req: redirect('/app/')),

    # Admin
    path('admin/', admin.site.urls),

    # Authentication
    path('accounts/', include('django.contrib.auth.urls')),

    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='digitallibrary/login.html'
        ),
        name='login'
    ),

    # Main App
    path(
        'app/',
        include(
            ('digitallibrary.urls', 'digitallibrary'),
            namespace='digitallibrary'
        )
    ),

    # Alias URL
    path(
        'library/',
        include(
            ('digitallibrary.urls', 'digitallibrary'),
            namespace='digitallibrary_alias'
        )
    ),

    # Offline + PWA
    path(
        'offline/',
        TemplateView.as_view(template_name='offline.html'),
        name='offline'
    ),

    path(
        'manifest.json/',
        TemplateView.as_view(
            template_name='manifest.json',
            content_type='application/json'
        ),
        name='manifest'
    ),
]

# ALWAYS serve media files
urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)

# ALWAYS serve static files
urlpatterns += static(
    settings.STATIC_URL,
    document_root=settings.STATIC_ROOT
)