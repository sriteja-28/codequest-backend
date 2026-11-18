import socket
import sys
from urllib.parse import urlparse

from .base import *  # noqa: F401,F403
from .base import REDIS_URL, SIMPLE_JWT, config

DEBUG = True
# Local dev runs over http://localhost: Secure cookies would never be sent back.
SIMPLE_JWT["AUTH_COOKIE_SECURE"] = False

# Seeded local accounts can sign in with a password for multi-role testing.
# Set DEV_PASSWORD_AUTH=false to test the production sign-in path locally.
DEV_PASSWORD_AUTH = config("DEV_PASSWORD_AUTH", default=True, cast=bool)
AUTHENTICATION_BACKENDS = ["apps.users.backends.DevPasswordBackend"]

ALLOWED_HOSTS = ["*"]

# More verbose logging in dev
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "colored": {
            "format": "\033[36m[{levelname}]\033[0m {name}: {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "colored",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "judge": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}

# Allow all CORS in dev
CORS_ALLOW_ALL_ORIGINS = True

# Any origin may open a WebSocket in dev (production restricts to the frontend).
WS_ALLOWED_ORIGINS = ["*"]

# Disable secure cookie in dev (HTTP)
SIMPLE_JWT["AUTH_COOKIE_SECURE"] = False


# ─────────────────────────────────────────────
# Redis fallback (development only)
#
# USE_REDIS=auto (default): use Redis when REDIS_URL accepts a TCP connection,
#   otherwise fall back to in-process backends so the API still works without
#   `docker compose up` (throttling, sessions and WebSockets keep working in a
#   single uvicorn/daphne process).
# USE_REDIS=true  : always use Redis (errors surface if it is down).
# USE_REDIS=false : never use Redis.
# Production never falls back — see production.py.
# ─────────────────────────────────────────────
def _redis_reachable(url: str, timeout: float = 0.3) -> bool:
    try:
        parsed = urlparse(url)
        with socket.create_connection((parsed.hostname or "localhost", parsed.port or 6379), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


_use_redis = str(config("USE_REDIS", default="auto")).strip().lower()
if _use_redis == "auto":
    USE_REDIS = _redis_reachable(REDIS_URL)
else:
    USE_REDIS = _use_redis in ("1", "true", "yes", "on")

if not USE_REDIS:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "codequest-dev",
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.db"
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    sys.stderr.write(
        "[codequest] Redis not in use (USE_REDIS=%s, REDIS_URL=%s): using in-memory cache, "
        "DB sessions and InMemoryChannelLayer. Run a single ASGI process.\n" % (_use_redis, REDIS_URL)
    )
