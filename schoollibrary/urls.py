from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect
from django.views.generic import TemplateView


# Home page redirects to the main app
def home(request):
    return redirect('/app/')


urlpatterns = [
    # Home page redirects to the app
    path('', home, name='home'),
    
    # Admin
    path("admin/", admin.site.urls),
    
    # Auth
    path("accounts/", include("django.contrib.auth.urls")),
    path("login/", auth_views.LoginView.as_view(template_name="digitallibrary/login.html"), name="login"),
    
    # Your main app under /app/ prefix
    path("app/", include(("digitallibrary.urls", "digitallibrary"), namespace="digitallibrary")),
    
    # ========== ALIAS FOR /library/ ==========
    # This makes /library/ work the same as /app/
    path("library/", include(("digitallibrary.urls", "digitallibrary"), namespace="digitallibrary")),
    
    # ========== PWA / OFFLINE SUPPORT ==========
    # Offline page - must be at root level for Service Worker
    path("offline/", TemplateView.as_view(template_name="offline.html"), name="offline"),
    
    # Manifest file for PWA
    path("manifest.json", TemplateView.as_view(template_name="manifest.json", content_type="application/json"), name="manifest"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)