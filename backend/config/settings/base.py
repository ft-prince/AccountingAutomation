import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR.parent / ".env")
# .env.example ships every key blank; a blank value means "unset", not "empty string".
for _key in [k for k, v in os.environ.items() if v == ""]:
    os.environ.pop(_key)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "backend"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "django_celery_beat",
    "apps.core",
    "apps.accounts",
    "apps.parties",
    "apps.documents",
    "apps.invoices",
    "apps.gst",
    "apps.payments",
    "apps.reconciliation",
    "apps.reporting",
    "apps.mail",
    "apps.forecasting",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.CurrentOrgMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTH_USER_MODEL = "accounts.User"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://nexren:nexren@localhost:5432/nexren")
}

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_TASK_ACKS_LATE = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:3000"])

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "COERCE_DECIMAL_TO_STRING": True,
    "EXCEPTION_HANDLER": "apps.core.api.problem_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultCursorPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {
        "upload": env("RATE_UPLOAD", default="600/hour"),
        "extraction": env("RATE_EXTRACTION", default="300/hour"),
        "drafting": env("RATE_DRAFTING", default="120/hour"),
        "forecast": env("RATE_FORECAST", default="12/hour"),
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Nexren Finance API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

from decimal import Decimal  # noqa: E402

ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-opus-5")
# Pricing is DATA: override via env when it changes. USD per million tokens.
ANTHROPIC_PRICE_USD_PER_MTOK = {
    "input": Decimal(env("ANTHROPIC_PRICE_INPUT", default="5.00")),
    "output": Decimal(env("ANTHROPIC_PRICE_OUTPUT", default="25.00")),
}
USD_INR_RATE = Decimal(env("USD_INR_RATE", default="84.00"))

# --- LLM provider -----------------------------------------------------------
# "anthropic" (default) or "groq". Groq speaks the OpenAI wire format; the adapter in
# apps/core/llm.py translates, so no extra SDK is needed.
LLM_PROVIDER = env("LLM_PROVIDER", default="anthropic")
GROQ_API_KEY = env("GROQ_API_KEY", default="")
GROQ_BASE_URL = env("GROQ_BASE_URL", default="https://api.groq.com/openai/v1")
# Verify against GET /v1/models for your account; availability differs per plan.
GROQ_MODEL = env("GROQ_MODEL", default="openai/gpt-oss-120b")
# Scans (images, PDFs without a text layer) may go to a different provider than text PDFs:
# Groq's free tier caps its vision model at 1,000 tokens per request, below one page image.
# Empty means "same as LLM_PROVIDER".
EXTRACTION_SCAN_PROVIDER = env("EXTRACTION_SCAN_PROVIDER", default="")
# Groq models are text-in; a scanned PDF needs a vision-capable model or it is refused.
GROQ_VISION_MODEL = env("GROQ_VISION_MODEL", default="")
# USD per million tokens. Groq's free tier is 0; set these when you move to a paid plan,
# otherwise spend is recorded as zero and any cost report under-reports.
# Celery rate limit for email classification, matched to the provider's tokens-per-minute
# budget (Groq's free tier is 8k TPM and one classification costs roughly 3-4k).
CLASSIFY_RATE_LIMIT = env("CLASSIFY_RATE_LIMIT", default="2/m")
# First sync after connecting a mailbox: only the newest messages, so a fresh connection does
# not queue hundreds of classifications at once. Later syncs are incremental (new mail only)
# and each thread is classified one at a time under CLASSIFY_RATE_LIMIT.
MAIL_FIRST_SYNC_DAYS = env.int("MAIL_FIRST_SYNC_DAYS", default=2)
MAIL_FIRST_SYNC_LIMIT = env.int("MAIL_FIRST_SYNC_LIMIT", default=50)
# One extraction is ~5-8k tokens; Groq's free tier allows 8k per minute, so one a minute is
# the honest default there. Raise it on a paid tier or on Anthropic.
EXTRACTION_RATE_LIMIT = env(
    "EXTRACTION_RATE_LIMIT", default="1/m" if LLM_PROVIDER == "groq" else "30/m"
)

GROQ_PRICE_USD_PER_MTOK = {
    "input": Decimal(env("GROQ_PRICE_INPUT", default="0")),
    "output": Decimal(env("GROQ_PRICE_OUTPUT", default="0")),
}

# --- Backups ----------------------------------------------------------------
BACKUP_BUCKET = env("BACKUP_BUCKET", default="")
BACKUP_STALE_HOURS = env.int("BACKUP_STALE_HOURS", default=48)

AWS_S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", default="")
AWS_ACCESS_KEY_ID = env("S3_ACCESS_KEY", default="")
AWS_SECRET_ACCESS_KEY = env("S3_SECRET_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("S3_BUCKET", default="nexren")

# --- Mail (Phase 14/15). OAuth apps + field encryption key; all blank by default.
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")
MICROSOFT_OAUTH_CLIENT_ID = env("MICROSOFT_OAUTH_CLIENT_ID", default="")
MICROSOFT_OAUTH_CLIENT_SECRET = env("MICROSOFT_OAUTH_CLIENT_SECRET", default="")
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")  # Fernet key (urlsafe base64)
OAUTH_REDIRECT_BASE = env("OAUTH_REDIRECT_BASE", default="")  # e.g. http://localhost:8000
