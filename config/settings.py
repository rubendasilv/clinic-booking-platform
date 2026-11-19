"""Django settings. Every value that changes between laptop and server comes from .env."""

import os
from pathlib import Path

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=""):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# --- Core ---
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-insecure-key")
DEBUG = env_bool("DJANGO_DEBUG", False)
# Refuse to run in production with a placeholder or weak secret key
if not DEBUG and (SECRET_KEY in {"dev-only-insecure-key", "change-me"} or len(SECRET_KEY) < 40):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a real secret of at least 40 characters "
        "when DJANGO_DEBUG is False."
    )
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8000")
SITE_URL = env("SITE_URL", "http://localhost:8000").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "bookings",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "bookings.middleware.CampaignTrackingMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "bookings.context_processors.business",
            ],
        },
    },
]

# --- Database (PostgreSQL only: the double-booking guard uses a Postgres constraint) ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "booking"),
        "USER": env("POSTGRES_USER", "booking"),
        "PASSWORD": env("POSTGRES_PASSWORD", "booking"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Time & language ---
LANGUAGE_CODE = "en-gb"
TIME_ZONE = env("TIME_ZONE", "Europe/London")
USE_I18N = True
USE_TZ = True

# --- Static files (Nginx serves STATIC_ROOT in production) ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Email ---
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_TIMEOUT = 15
EMAIL_FILE_PATH = env("EMAIL_FILE_PATH", "/tmp/emails")  # only used by the file backend
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Clearline Laser Studio <bookings@example.com>")
OWNER_NOTIFICATION_EMAIL = env("OWNER_NOTIFICATION_EMAIL", "owner@example.com")

# --- Celery ---
CELERY_BROKER_URL = env("CELERY_BROKER_URL", env("REDIS_URL", "redis://localhost:6379/0"))
CELERY_RESULT_BACKEND = None
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_ACKS_LATE = True
CELERY_BEAT_SCHEDULE = {
    "send-due-reminders": {
        "task": "bookings.tasks.send_due_reminders",
        "schedule": crontab(minute="*/15"),
    },
    "expire-unpaid-bookings": {
        "task": "bookings.tasks.expire_unpaid_bookings",
        "schedule": crontab(minute="*/5"),
    },
}

# --- Payments (optional: leave blank and deposits are taken in clinic) ---
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET")

# --- Business rules and details shown on the site ---
BUSINESS = {
    "name": env("BUSINESS_NAME", "Clearline Laser Studio"),
    "tagline": "Laser tattoo removal and laser hair removal in London",
    "address": env("BUSINESS_ADDRESS", "Unit 4, 12 Example Street, London E1 0AA"),
    "phone": env("BUSINESS_PHONE", "020 0000 0000"),
    "email": env("BUSINESS_EMAIL", "hello@example.com"),
    "instagram": env("BUSINESS_INSTAGRAM", "https://instagram.com/"),
    "tiktok": env("BUSINESS_TIKTOK", "https://tiktok.com/"),
}
BOOKING_RULES = {
    "slot_step_minutes": int(env("SLOT_STEP_MINUTES", "15")),
    "min_notice_hours": int(env("MIN_NOTICE_HOURS", "12")),
    "max_days_ahead": int(env("MAX_DAYS_AHEAD", "60")),
    "cancellation_window_hours": int(env("CANCELLATION_WINDOW_HOURS", "48")),
    "unpaid_hold_minutes": int(env("UNPAID_HOLD_MINUTES", "30")),
    "manage_link_max_age_days": 180,
}

# --- Security (tightened automatically when DEBUG is off) ---
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env_bool("SECURE_COOKIES", True)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}

# --- Error monitoring (only switched on when a DSN is set) ---
SENTRY_DSN = env("SENTRY_DSN")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1, send_default_pii=False)
