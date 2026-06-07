"""
Django settings for the Order Tracking Portal.

Configuration is driven by environment variables (12-factor) via django-environ,
so the same image runs in dev and on the production CentOS host next to Bitrix24.
"""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["*"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    SECURE_SSL_REDIRECT=(bool, False),
)

# Load .env if present (local dev). In Docker the vars come from the environment.
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "django_celery_beat",
    # Local
    "apps.accounts",
    "apps.directories",
    "apps.orders",
    "apps.files",
    "apps.backups",
    "apps.audit",
    "apps.integrations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Hard 45-minute absolute session cap + activity tracking.
    "apps.accounts.middleware.SessionTimeoutMiddleware",
    # Renders dates/times in DISPLAY_TIME_ZONE (storage stays UTC).
    "apps.accounts.middleware.TimezoneMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Stamps request.user / IP onto thread-local for history & audit logging.
    "apps.audit.middleware.CurrentRequestMiddleware",
]

ROOT_URLCONF = "config.urls"

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
                "apps.accounts.context_processors.user_permissions",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------- #
# Database — PostgreSQL (main store)
# --------------------------------------------------------------------------- #
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="portal"),
        "USER": env("POSTGRES_USER", default="portal"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="portal"),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Redis — sessions, cache, Celery broker (NOT the main store)
# --------------------------------------------------------------------------- #
REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "portal",
    }
}

# Sessions live in Redis but are persisted to DB as well (cached_db) so a Redis
# flush never silently logs everyone out and data is never lost.
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_CACHE_ALIAS = "default"

# --------------------------------------------------------------------------- #
# Session lifetime — 45 minutes (TЗ §1)
# --------------------------------------------------------------------------- #
SESSION_IDLE_TIMEOUT = timedelta(minutes=45)
# Sliding inactivity window: each request refreshes the cookie age.
SESSION_COOKIE_AGE = int(SESSION_IDLE_TIMEOUT.total_seconds())
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "orders:table"
LOGOUT_REDIRECT_URL = "accounts:login"

# Argon2 first for strong password hashing (TЗ §17 — hashed passwords only).
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------- #
# DRF — REST API, auth required everywhere (TЗ §17, amendment §10 API)
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DATETIME_FORMAT": "iso-8601",
}

# --------------------------------------------------------------------------- #
# Celery — background tasks (backups every 3h, retention, rclone, lookups)
# --------------------------------------------------------------------------- #
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60 * 30

# --------------------------------------------------------------------------- #
# Internationalisation — store UTC, render local (amendment §10 UTC)
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
# Timezone used to render dates/times in the UI. UTC stays the storage default;
# templates show local time via apps.accounts.middleware.TimezoneMiddleware.
DISPLAY_TIME_ZONE = env("DISPLAY_TIME_ZONE", default="Asia/Yekaterinburg")  # UTC+5
DATE_INPUT_FORMATS = ["%d.%m.%Y"]

# --------------------------------------------------------------------------- #
# Static & media
# --------------------------------------------------------------------------- #
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Order files (TЗ §6) — dedicated folder on a Docker volume, synced to Drive.
ORDER_FILES_ROOT = Path(env("ORDER_FILES_ROOT", default=str(BASE_DIR.parent / "data" / "orders")))
ORDER_FILES_URL = "/files/serve/"
# Internal nginx location used for protected X-Accel-Redirect delivery.
ORDER_FILES_INTERNAL_PREFIX = "/protected-files/"
FILE_UPLOAD_MAX_SIZE = env.int("FILE_UPLOAD_MAX_SIZE", default=25 * 1024 * 1024)  # 25 MB
FILE_UPLOAD_ALLOWED_EXTENSIONS = env.list(
    "FILE_UPLOAD_ALLOWED_EXTENSIONS",
    default=["pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png", "zip", "rar", "7z"],
)
DATA_UPLOAD_MAX_MEMORY_SIZE = FILE_UPLOAD_MAX_SIZE

# --------------------------------------------------------------------------- #
# Backups (TЗ §5)
# --------------------------------------------------------------------------- #
BACKUP_ROOT = Path(env("BACKUP_ROOT", default=str(BASE_DIR.parent / "data" / "backups")))
BACKUP_RETENTION_DAYS = env.int("BACKUP_RETENTION_DAYS", default=90)
BACKUP_INTERVAL_HOURS = env.int("BACKUP_INTERVAL_HOURS", default=3)
PG_DUMP_BIN = env("PG_DUMP_BIN", default="pg_dump")
PG_RESTORE_BIN = env("PG_RESTORE_BIN", default="pg_restore")
PSQL_BIN = env("PSQL_BIN", default="psql")

# --------------------------------------------------------------------------- #
# Organization data provider — INN lookup (TЗ §14)
# --------------------------------------------------------------------------- #
# One of: "dadata", "stub". Pluggable — see apps/integrations/providers.
ORG_PROVIDER = env("ORG_PROVIDER", default="stub")
DADATA_API_KEY = env("DADATA_API_KEY", default="")
DADATA_SECRET_KEY = env("DADATA_SECRET_KEY", default="")
ORG_LOOKUP_CACHE_TTL = env.int("ORG_LOOKUP_CACHE_TTL", default=60 * 60 * 24)

# --------------------------------------------------------------------------- #
# Google Drive sync via rclone (TЗ §6 / amendment)
# --------------------------------------------------------------------------- #
RCLONE_ENABLED = env.bool("RCLONE_ENABLED", default=False)
RCLONE_BIN = env("RCLONE_BIN", default="rclone")
RCLONE_REMOTE = env("RCLONE_REMOTE", default="gdrive:orders")
RCLONE_SYNC_INTERVAL_MINUTES = env.int("RCLONE_SYNC_INTERVAL_MINUTES", default=30)

# --------------------------------------------------------------------------- #
# Security (TЗ §17)
# --------------------------------------------------------------------------- #
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # needed by HTMX to read the token
X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_CONTENT_TYPE_NOSNIFF = True
if not DEBUG:
    SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
    CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
