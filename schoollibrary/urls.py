from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.http import HttpResponse


# Simple health check for Render
def health_check(request):
    return HttpResponse("OK", content_type="text/plain")


def home(request):
    return redirect('/app/')

def root_redirect(request):
    return redirect('/admin/')  # or '/select-tenant/'
urlpatterns = [
    path('healthz/', health_check, name='health_check'),
    path('health/', health_check, name='health_alt'),
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('', root_redirect, name='root'),
    path('accounts/', include("django.contrib.auth.urls")),
    path('login/', auth_views.LoginView.as_view(template_name="digitallibrary/login.html"), name='login'),
    path('app/', include(("digitallibrary.urls", "digitallibrary"), namespace='digitallibrary')),
    path('library/', include(("digitallibrary.urls", "digitallibrary"), namespace='digitallibrary_alias')),
    path('offline/', TemplateView.as_view(template_name="offline.html"), name='offline'),
    path('manifest.json', TemplateView.as_view(template_name="manifest.json", content_type="application/json"), name='manifest'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)