"""
Production settings.

Select with DJANGO_SETTINGS_MODULE=config.settings.production.
Every security-relevant value must come from the environment; the process
refuses to start with development defaults (fail fast instead of running
insecurely).
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import (
    INSECURE_DEFAULT_JUDGE_KEY,
    JUDGE_INTERNAL_API_KEY,
    SIMPLE_JWT,
    Csv,
    config,
)

DEBUG = False

# Public sign-in is Google/GitHub only. Staff may still use Django's password
# form at /django-admin/ (ModelBackend is the default backend).
DEV_PASSWORD_AUTH = False

# Required: no defaults on purpose (decouple raises UndefinedValueError if unset).
SECRET_KEY = config("SECRET_KEY")
if SECRET_KEY.startswith("dev-insecure") or len(SECRET_KEY) < 32:
    raise ImproperlyConfigured("SECRET_KEY must be a random value of at least 32 characters.")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv())
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must list the API host name(s); '*' is not allowed.")

if JUDGE_INTERNAL_API_KEY == INSECURE_DEFAULT_JUDGE_KEY or len(JUDGE_INTERNAL_API_KEY) < 24:
    raise ImproperlyConfigured(
        "JUDGE_INTERNAL_API_KEY must be set to a random value (>= 24 chars) shared with the judge worker."
    )

# Public URLs. Recommended deployment is same-origin (reverse proxy serves the
# frontend and /api on one domain), so BACKEND_PUBLIC_URL defaults to FRONTEND_URL.
FRONTEND_URL = config("FRONTEND_URL").rstrip("/")
BACKEND_PUBLIC_URL = config("BACKEND_PUBLIC_URL", default=FRONTEND_URL).rstrip("/")
for _name, _url in (("FRONTEND_URL", FRONTEND_URL), ("BACKEND_PUBLIC_URL", BACKEND_PUBLIC_URL)):
    if not _url.startswith("https://"):
        raise ImproperlyConfigured(
            f"{_name} must be an https:// URL in production (auth cookies are Secure-only)."
        )

# Frontend origin(s) for CORS; defaults to FRONTEND_URL (same-origin needs no CORS at all).
CORS_ALLOWED_ORIGINS = config("CORS_ORIGINS", default=FRONTEND_URL, cast=Csv())
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default=",".join(dict.fromkeys([*CORS_ALLOWED_ORIGINS, BACKEND_PUBLIC_URL])),
    cast=Csv(),
)
CORS_ALLOW_ALL_ORIGINS = False
WS_ALLOWED_ORIGINS = config("WS_ALLOWED_ORIGINS", default=",".join(CORS_ALLOWED_ORIGINS), cast=Csv())

# Cookies only over HTTPS.
SIMPLE_JWT["AUTH_COOKIE_SECURE"] = True
SIMPLE_JWT["AUTH_COOKIE_SAMESITE"] = config("AUTH_COOKIE_SAMESITE", default="Lax")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# TLS is normally terminated at a reverse proxy / load balancer that sets
# X-Forwarded-Proto. Disable with USE_X_FORWARDED_PROTO=false if not proxied.
if config("USE_X_FORWARDED_PROTO", default=True, cast=bool):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False, cast=bool)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Redis is mandatory in production (cache-backed sessions, throttling, Channels
# across multiple ASGI processes). No in-memory fallback here.
