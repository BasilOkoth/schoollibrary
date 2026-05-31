# schoollibrary/settings.py

from pathlib import Path
import os
import warnings

from decouple import config
import dj_database_url
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# =========================
# CORE SETTINGS
# =========================
SECRET_KEY = config("SECRET_KEY", default="unsafe-secret-key-for-dev")
DEBUG = config("DEBUG", default=True, cast=bool)
ON_RENDER = ("RENDER" in os.environ or "DATABASE_URL" in os.environ) and not DEBUG

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".localhost",
    "schoollibrary-1.onrender.com",
    ".onrender.com",
    ".render.com",
    "shulehub.org",
    "www.shulehub.org",
    ".shulehub.org",
    "miyuga.localhost",
    "oluti.localhost",
    "daraja.localhost",
    "orero.localhost",
    "oriwo.localhost",
    "testserver",
]

PUBLIC_DOMAIN = "shulehub.org"

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
    "http://*.localhost:8000",
    "https://*.onrender.com",
    "https://*.render.com",
    "https://shulehub.org",
    "https://www.shulehub.org",
    "https://*.shulehub.org",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# =========================
# MULTI-TENANT APPS
# =========================
PUBLIC_SCHEMA_APPS = [
    "django_tenants",
    "corsheaders",
    "tenants.apps.TenantsConfig",
    "superadmin",
    "storages",
    "django_daraja",
    "dbbackup",
    "rest_framework",
    "cloudinary_storage",
    "cloudinary",
]

SHARED_APPS = PUBLIC_SCHEMA_APPS + [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

TENANT_APPS = [
    "digitallibrary.apps.LibraryConfig",
    "mpesa",
]

INSTALLED_APPS = list(SHARED_APPS) + [
    app for app in TENANT_APPS if app not in SHARED_APPS
]

TENANT_MODEL = "tenants.School"
TENANT_DOMAIN_MODEL = "tenants.Domain"
PUBLIC_SCHEMA_NAME = "public"
PUBLIC_SCHEMA_URLCONF = "schoollibrary.urls"

# =========================
# DATABASE
# =========================
if "DATABASE_URL" in os.environ:
    DATABASES = {
        "default": dj_database_url.config(
            conn_max_age=600,
            conn_health_checks=True,
            engine="django_tenants.postgresql_backend",
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django_tenants.postgresql_backend",
            "NAME": config("DB_NAME", default="schoollibrary_db"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD", default="miyuga0852"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }


class SuperAdminRouter:
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        schema = hints.get("schema_name")
        if app_label == "superadmin":
            return schema == "public"
        if app_label.startswith("django.contrib."):
            return schema == "public"
        return True


DATABASE_ROUTERS = [
    "schoollibrary.settings.SuperAdminRouter",
    "django_tenants.routers.TenantSyncRouter",
]

# =========================
# MIDDLEWARE
# =========================
MIDDLEWARE = [
    "digitallibrary.middleware.ProgrammingErrorMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "digitallibrary.middleware.PublicAdminMiddleware",
    "digitallibrary.middleware.StripTenantSchemaMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "digitallibrary.middleware.ForceSessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

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
                "digitallibrary.context_processors.school_settings",
                "digitallibrary.context_processors.tenant_context",
            ],
        },
    },
]

# =========================
# AUTH
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/app/dashboard/"

# =========================
# LANGUAGE / TIME
# =========================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# STATIC FILES
# =========================
STATIC_URL = "/static/"
STATIC_ROOT = str(BASE_DIR / "staticfiles")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

STATICFILES_DIRS = [
    str(BASE_DIR / "static"),
] if (BASE_DIR / "static").exists() else []

# =========================
# MEDIA / STORAGE
# =========================
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="shulehub-media-okoth")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="eu-north-1")
CLOUDFRONT_DOMAIN = config("CLOUDFRONT_DOMAIN", default="")

AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = False
AWS_QUERYSTRING_EXPIRE = 3600
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_ADDRESSING_STYLE = "virtual"
AWS_S3_USE_SSL = True
AWS_S3_VERIFY = True
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME:
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    if CLOUDFRONT_DOMAIN:
        MEDIA_URL = f"https://{CLOUDFRONT_DOMAIN}/"
    else:
        MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/"
else:
    if config("CLOUDINARY_CLOUD_NAME", default=""):
        DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"
        MEDIA_URL = "/media/"
    else:
        DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
        MEDIA_URL = "/media/"
        MEDIA_ROOT = str(BASE_DIR / "media")

os.environ["DJANGO_DEFAULT_FILE_STORAGE"] = DEFAULT_FILE_STORAGE

# =========================
# STORAGES / BACKUPS
# =========================
BACKUP_ROOT = BASE_DIR / "backups"
DATABASE_BACKUP_DIR = BACKUP_ROOT / "database"
MEDIA_BACKUP_DIR = BACKUP_ROOT / "media"

DATABASE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

STORAGES = {
    "default": {"BACKEND": DEFAULT_FILE_STORAGE},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    "dbbackup": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(DATABASE_BACKUP_DIR)},
    },
    "dbbackup_media": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(MEDIA_BACKUP_DIR)},
    },
}

if not DEBUG and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME:
    STORAGES["dbbackup"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "location": "backups/database/",
            "default_acl": "private",
        },
    }
    STORAGES["dbbackup_media"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "location": "backups/media/",
            "default_acl": "private",
        },
    }

DBBACKUP_CLEANUP_KEEP = config("DBBACKUP_CLEANUP_KEEP", default=7, cast=int)
DBBACKUP_FILENAME_TEMPLATE = "{databasename}-{servername}-{datetime}.{extension}"
DBBACKUP_MEDIA_FILENAME_TEMPLATE = "{mediaroot}-{servername}-{datetime}.{extension}"
DBBACKUP_SEND_EMAIL = True

# =========================
# SESSION / CSRF / SECURITY
# =========================
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "sessionid"
SESSION_COOKIE_AGE = 1209600
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_PATH = "/"
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_NAME = "csrftoken"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_PATH = "/"
CSRF_USE_SESSIONS = False
CSRF_COOKIE_AGE = 31449600

if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_DOMAIN = None
    CSRF_COOKIE_DOMAIN = None
    SECURE_HSTS_SECONDS = 0
else:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_DOMAIN = None
    CSRF_COOKIE_DOMAIN = None
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# =========================
# SMS / EMAIL
# =========================
AFRICASTALKING_USERNAME = config("AFRICASTALKING_USERNAME", default="sandbox")
AFRICASTALKING_API_KEY = config("AFRICASTALKING_API_KEY", default="")
AFRICASTALKING_SENDER_ID = config("AFRICASTALKING_SENDER_ID", default=None)
MOCK_SMS_MODE = config("MOCK_SMS_MODE", default=True, cast=bool)

EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="School Feedback <noreply@school.com>")

ADMIN_EMAIL = config("ADMIN_EMAIL", default="")
ADMINS = [("Admin", config("ADMIN_EMAIL", default="admin@shulehub.com"))]

if DEBUG and not EMAIL_HOST_USER:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# =========================
# CACHE / LOGGING
# =========================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-somazone-cache",
    }
}

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "file": {
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "shulehub.log",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
}

# =========================
# ADMIN BRANDING
# =========================
ADMIN_TEMPLATE = "admin/custom_admin.html"
SUPERADMIN_SITE_HEADER = "ShuleHub Super Admin Panel"
SUPERADMIN_SITE_TITLE = "Super Admin Dashboard"
SUPERADMIN_INDEX_TITLE = "Welcome to ShuleHub Super Admin Portal"

warnings.filterwarnings("ignore", message="Model .* was already registered")
