from pathlib import Path
import os
from decouple import config
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# =========================
# CORE SETTINGS
# =========================
SECRET_KEY = config('SECRET_KEY', default='unsafe-secret-key-for-dev')
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = ['*']  # Allow all hosts for now

CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    'https://*.render.com',
    'http://localhost:8000',
]

# =========================
# DETECT RENDER ENVIRONMENT
# =========================
ON_RENDER = 'RENDER' in os.environ or 'DATABASE_URL' in os.environ
ON_RENDER = ON_RENDER and not DEBUG  # Not in development mode

# =========================
# MULTI-TENANT CONFIG
# =========================
SHARED_APPS = [
    "django_tenants",
    "corsheaders",
    "tenants.apps.TenantsConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
]

TENANT_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "digitallibrary.apps.LibraryConfig",
]

INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]

# =========================
# DATABASE - POSTGRESQL
# =========================
if 'DATABASE_URL' in os.environ:
    DATABASES = {
        'default': dj_database_url.config(
            conn_max_age=600,
            conn_health_checks=True,
            engine='django_tenants.postgresql_backend'
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django_tenants.postgresql_backend",
            "NAME": config('DB_NAME', default='schoollibrary_db'),
            "USER": config('DB_USER', default='postgres'),
            "PASSWORD": config('DB_PASSWORD', default='miyuga0852'),
            "HOST": config('DB_HOST', default='localhost'),
            "PORT": config('DB_PORT', default='5432'),
        }
    }

DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)

TENANT_MODEL = "tenants.School"
TENANT_DOMAIN_MODEL = "tenants.Domain"
PUBLIC_SCHEMA_NAME = "public"
PUBLIC_SCHEMA_URLCONF = "schoollibrary.urls"

# =========================
# MIDDLEWARE (Correct Order)
# =========================
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django_tenants.middleware.main.TenantMainMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "digitallibrary.middleware.ProgrammingErrorMiddleware",  # After auth to access user
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# =========================
# CORS
# =========================
CORS_ALLOW_ALL_ORIGINS = True

# =========================
# URL CONFIG
# =========================
ROOT_URLCONF = "schoollibrary.urls"
WSGI_APPLICATION = "schoollibrary.wsgi.application"

# =========================
# TEMPLATES
# =========================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                'digitallibrary.context_processors.school_settings',
            ],
        },
    },
]

# =========================
# PASSWORD VALIDATION
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =========================
# INTERNATIONALIZATION
# =========================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# =========================
# STATIC FILES
# =========================
STATIC_URL = "/static/"
STATIC_ROOT = str(BASE_DIR / "staticfiles")
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STATICFILES_DIRS = [
    str(BASE_DIR / "static"),
] if (BASE_DIR / "static").exists() else []

# =========================
# MEDIA FILES
# =========================
MEDIA_URL = "/media/"
MEDIA_ROOT = str(BASE_DIR / "media")

# =========================
# SECURITY
# =========================
if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
else:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# =========================
# DEFAULT PK
# =========================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# LOGIN
# =========================
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "digitallibrary:home"
LOGOUT_REDIRECT_URL = "digitallibrary:home"

# =========================
# SMS CONFIG
# =========================
AFRICASTALKING_USERNAME = config('AFRICASTALKING_USERNAME', default='sandbox')
AFRICASTALKING_API_KEY = config('AFRICASTALKING_API_KEY', default='')
AFRICASTALKING_SENDER_ID = config('AFRICASTALKING_SENDER_ID', default=None)
MOCK_SMS_MODE = config('MOCK_SMS_MODE', default=True, cast=bool)

# =========================
# EMAIL CONFIG
# =========================
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='School Feedback <noreply@school.com>')

ADMIN_EMAIL = config('ADMIN_EMAIL', default='')
ADMIN_EMAILS = config('ADMIN_EMAILS', default='').split(',') if config('ADMIN_EMAILS', default='') else [ADMIN_EMAIL] if ADMIN_EMAIL else ['admin@example.com']

if DEBUG and not EMAIL_HOST_USER:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    print("Email backend set to console mode (development)")

# =========================
# CACHING
# =========================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-somazone-cache',
    }
}

# =========================
# AUTO-CREATE TENANT ON RENDER (UPDATED)
# =========================
import sys

def create_tenant_if_not_exists():
    """Automatically create the default tenant for Render deployment"""
    if not ON_RENDER:
        return  # Only run on production Render
    
    print("🔧 Checking tenant setup...", file=sys.stderr)
    
    try:
        from tenants.models import School, Domain
        from django.db import connection, ProgrammingError
        
        # Ensure database connection works
        connection.ensure_connection()
        
        # Check if tables exist
        cursor = connection.cursor()
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='tenants_school');")
        tables_exist = cursor.fetchone()[0]
        
        if not tables_exist:
            print("⚠️ Tables not ready yet. Tenant creation will happen after migrations.", file=sys.stderr)
            return
        
        # Check if any tenant exists
        if School.objects.exists():
            print(f"✅ Tenant already exists. Found {School.objects.count()} tenant(s).", file=sys.stderr)
            return
        
        print("🔧 No tenant found. Creating default tenant...", file=sys.stderr)
        
        # Create the main tenant
        school = School.objects.create(
            name='Main School Library',
            schema_name='public',
            paid_until='2029-12-31',
            on_trial=False,
            created_on='2024-01-01',
            is_active=True
        )
        
        # Get the current domain from environment
        current_domain = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'schoollibrary.onrender.com')
        
        # Remove protocol if present
        current_domain = current_domain.replace('https://', '').replace('http://', '')
        
        # Add domain for this tenant
        Domain.objects.create(
            tenant=school,
            domain=current_domain,
            is_primary=True
        )
        
        print(f"✅ Tenant created successfully!", file=sys.stderr)
        print(f"   School: {school.name}", file=sys.stderr)
        print(f"   Domain: {current_domain}", file=sys.stderr)
        
        # Also add subdomain pattern if domain has dots
        if '.' in current_domain and not current_domain.startswith('*'):
            Domain.objects.create(
                tenant=school,
                domain=f'*.{current_domain}',
                is_primary=False
            )
            print(f"   Wildcard: *.{current_domain}", file=sys.stderr)
        
        print("✅ Tenant setup complete!", file=sys.stderr)
        
    except ProgrammingError as e:
        print(f"⚠️ Tables not ready yet: {e}", file=sys.stderr)
        print("Tenant will be created on next startup.", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ Tenant check failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

# Run tenant creation (only on Render, after migrations)
if ON_RENDER:
    create_tenant_if_not_exists()

# =========================
# HEALTH CHECK
# =========================
from django.http import HttpResponse

def health_check(request):
    return HttpResponse("OK", content_type="text/plain")

# =========================
# CLEAN WARNINGS
# =========================
import warnings
warnings.filterwarnings('ignore', message='Model .* was already registered')