"""
Test settings — fully isolated: in-memory SQLite, local-memory cache, in-memory
channel layer, no Redis/RabbitMQ/Postgres required. Selected by pytest.ini.
"""

from .base import *  # noqa: F401,F403

DEBUG = False
SIMPLE_JWT["AUTH_COOKIE_SECURE"] = False  # test client speaks http
DEV_PASSWORD_AUTH = True
AUTHENTICATION_BACKENDS = ["apps.users.backends.DevPasswordBackend"]
SECRET_KEY = "test-secret-key-not-for-production-use-0123456789"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "codequest-tests",
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.db"
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Deterministic sign-in tests: no real provider credentials from a local .env.
GOOGLE_CLIENT_ID = ""
GOOGLE_CLIENT_SECRET = ""
GITHUB_CLIENT_ID = ""
GITHUB_CLIENT_SECRET = ""

JUDGE_INTERNAL_API_KEY = "test-judge-key-0123456789abcdef"
# Unroutable on purpose: tests patch the publisher; nothing may reach a broker.
RABBITMQ_URL = "amqp://guest:guest@127.0.0.1:1/"

CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]
WS_ALLOWED_ORIGINS = ["http://localhost:3000"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "WARNING"},
}
