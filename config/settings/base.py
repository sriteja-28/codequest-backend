"""
CodeQuest – Base Django Settings
Shared across all environments. Override in development.py / production.py.
"""

import os
from pathlib import Path
from decouple import config, Csv
from datetime import timedelta
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-insecure-key-change-in-production")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# ─────────────────────────────────────────────
# Application definition
# ─────────────────────────────────────────────
DJANGO_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "channels",
]

LOCAL_APPS = [
    "apps.core",
    "apps.users",
    "apps.billing",
    "apps.content",
    "apps.problems",
    "apps.submissions",
    "apps.contests",
    "apps.courses",
    "apps.discussions",
    "apps.ai_assist",
    "apps.admin_panel",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
                "apps.users.context_processors.admin_login",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ─────────────────────────────────────────────
# Public URLs (browser-facing). Local dev: two origins on localhost.
# Production: one origin behind the reverse proxy (both values identical).
# Always use "localhost" locally, never 127.0.0.1: cookies are per host name.
# ─────────────────────────────────────────────
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000").rstrip("/")
BACKEND_PUBLIC_URL = config("BACKEND_PUBLIC_URL", default="http://localhost:8000").rstrip("/")

# ─────────────────────────────────────────────
# Database
# Defaults match the local dev stack (infra/docker-compose.dev.yml, port 5433).
# ─────────────────────────────────────────────
DATABASES = {
    "default": dj_database_url.config(
        default=config(
            "DATABASE_URL",
            default="postgresql://codequest:codequest_dev@127.0.0.1:5433/codequest",
        ),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ─────────────────────────────────────────────
# Redis / Channels (dev stack default: port 6380)
# ─────────────────────────────────────────────
REDIS_URL = config("REDIS_URL", default="redis://127.0.0.1:6380/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

# Cache (throttle counters, queue-depth cache, cache-backed sessions).
# Defaults to the same Redis server as Channels; override with REDIS_CACHE_URL.
REDIS_CACHE_URL = config("REDIS_CACHE_URL", default=REDIS_URL)

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Dashboard/profile aggregate cache. Invalidated after every judged submission.
PROGRESS_CACHE_TTL = config("PROGRESS_CACHE_TTL", default=300, cast=int)

# ─────────────────────────────────────────────
# RabbitMQ
# ─────────────────────────────────────────────
RABBITMQ_URL = config("RABBITMQ_URL", default="amqp://codequest:codequest_dev@127.0.0.1:5673/")
JUDGE_QUEUE_NAME = config("JUDGE_QUEUE_NAME", default="code_submissions")

# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─────────────────────────────────────────────
# JWT (HTTP-only cookies)
# ─────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_COOKIE": "access_token",
    "AUTH_COOKIE_REFRESH": "refresh_token",
    "AUTH_COOKIE_SECURE": not DEBUG,
    "AUTH_COOKIE_HTTP_ONLY": True,
    "AUTH_COOKIE_SAMESITE": "Lax",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ─────────────────────────────────────────────
# Sign-in: Google / GitHub OAuth. There is no public password sign-up or
# sign-in. A provider is offered by the UI only when both its client id and
# secret are present in the environment.
#
# Local multi-user testing uses seeded accounts through DEV_PASSWORD_AUTH,
# which development settings enable and production forces off.
# ─────────────────────────────────────────────
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", default="")
GITHUB_CLIENT_ID = config("GITHUB_CLIENT_ID", default="")
GITHUB_CLIENT_SECRET = config("GITHUB_CLIENT_SECRET", default="")
# Seconds a sign-in attempt (state/PKCE/nonce) stays valid.
OAUTH_STATE_MAX_AGE = config("OAUTH_STATE_MAX_AGE", default=600, cast=int)
# Email + password sign-in for seeded local accounts only. Never enable in
# production; production.py pins this to False.
DEV_PASSWORD_AUTH = config("DEV_PASSWORD_AUTH", default=False, cast=bool)

# ─────────────────────────────────────────────
# DRF
# ─────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.users.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    # PageNumberPagination + optional ?page_size= (capped, see config/pagination.py)
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    # Throttle counters live in the default cache. Development falls back to an
    # in-process cache when Redis is unreachable (see development.py), so these
    # stay enabled everywhere instead of being silently disabled.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    # Rates use DRF syntax "<n>/<period>"; the submission throttles additionally
    # accept a period multiplier such as "3/10s" (apps/submissions/throttles.py).
    # Anonymous visitors make several API calls per page view (me, refresh,
    # problems, sections, tags), so the anon budget is sized for browsing.
    "DEFAULT_THROTTLE_RATES": {
        "anon": config("THROTTLE_ANON", default="1000/hour"),
        "user": config("THROTTLE_USER", default="5000/hour"),
        "login": config("THROTTLE_LOGIN", default="10/minute"),
        "oauth": config("THROTTLE_OAUTH", default="20/minute"),
        "run_free": config("THROTTLE_RUN_FREE", default="10/minute"),
        "run_pro": config("THROTTLE_RUN_PRO", default="30/minute"),
        "submit_free": config("THROTTLE_SUBMIT_FREE", default="3/minute"),
        "submit_pro": config("THROTTLE_SUBMIT_PRO", default="10/minute"),
        "burst": config("THROTTLE_BURST", default="3/10s"),
    },
    # Number of trusted reverse proxies in front of Django. Leave unset when
    # clients connect directly; set to 1 behind a single proxy/load balancer so
    # anonymous throttles key on the real client IP (X-Forwarded-For).
    "NUM_PROXIES": config("NUM_PROXIES", default=None, cast=lambda v: int(v) if v not in (None, "") else None),
}

# ─────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = config(
    "CORS_ORIGINS",
    default=FRONTEND_URL,
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

# Origins allowed to POST forms with a session (Django admin). Defaults to the
# CORS origins plus the backend's own public URL.
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default=",".join(dict.fromkeys([*CORS_ALLOWED_ORIGINS, BACKEND_PUBLIC_URL])),
    cast=Csv(),
)

# Browser origins allowed to open WebSockets (checked by channels OriginValidator
# in config/asgi.py). Defaults to the CORS origins, i.e. the frontend URL(s).
WS_ALLOWED_ORIGINS = config(
    "WS_ALLOWED_ORIGINS",
    default=",".join(CORS_ALLOWED_ORIGINS),
    cast=Csv(),
)

# ─────────────────────────────────────────────
# Internationalization
# ─────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ─────────────────────────────────────────────
# Static / Media
# ─────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─────────────────────────────────────────────
# Judge internal security
# ─────────────────────────────────────────────
INSECURE_DEFAULT_JUDGE_KEY = "judge-secret-key-change-me"
JUDGE_INTERNAL_API_KEY = config(
    "JUDGE_INTERNAL_API_KEY", default=INSECURE_DEFAULT_JUDGE_KEY
)

# A submission still QUEUED/RUNNING after this many seconds is marked
# INTERNAL_ERROR (lost job / crashed worker). See apps/submissions/services.py
# and `manage.py reap_stuck_submissions`.
JUDGE_STALE_SUBMISSION_SECONDS = config("JUDGE_STALE_SUBMISSION_SECONDS", default=900, cast=int)

# An ended contest is finalized (final standings frozen, problems released) once
# its in-window submissions are judged, or at the latest this many seconds after
# the end. See apps/contests/finalize.py and `manage.py finalize_contests`.
CONTEST_FINALIZE_GRACE_SECONDS = config(
    "CONTEST_FINALIZE_GRACE_SECONDS", default=JUDGE_STALE_SUBMISSION_SECONDS, cast=int
)

# Largest accepted source file for run/submit (bytes, UTF-8).
MAX_CODE_BYTES = config("MAX_CODE_BYTES", default=65536, cast=int)

# ─────────────────────────────────────────────
# AI Assist limits (per user per UTC day)
# ─────────────────────────────────────────────
AI_HINTS_FREE_DAILY = config("AI_HINTS_FREE_DAILY", default=5, cast=int)
AI_HINTS_PRO_DAILY = config("AI_HINTS_PRO_DAILY", default=50, cast=int)
AI_CHAT_FREE_DAILY = config("AI_CHAT_FREE_DAILY", default=10, cast=int)
AI_CHAT_PRO_DAILY = config("AI_CHAT_PRO_DAILY", default=200, cast=int)


# Queue limits (circuit breaker in apps/submissions/queue.py)
JUDGE_QUEUE_SOFT_LIMIT = config("JUDGE_QUEUE_SOFT_LIMIT", default=500, cast=int)
JUDGE_QUEUE_HARD_LIMIT = config("JUDGE_QUEUE_HARD_LIMIT", default=1000, cast=int)

# ─────────────────────────────────────────────
# Logging (console). development.py / production.py may override.
# ─────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": config("LOG_LEVEL", default="INFO")},
}
