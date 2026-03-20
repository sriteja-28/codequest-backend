from .base import *

DEBUG = True

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

# Disable secure cookie in dev (HTTP)
SIMPLE_JWT["AUTH_COOKIE_SECURE"] = False