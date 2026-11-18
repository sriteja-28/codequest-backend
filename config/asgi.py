"""
ASGI config — Django + Channels
Handles both HTTP (Django) and WebSocket (Channels) connections.

Run:  uvicorn config.asgi:application --port 8000
      daphne  config.asgi:application -p 8000
"""

import os

import django

# config.settings is a package of modules (base/development/production/test);
# it has no settings of its own, so the default must name a concrete module.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.conf import settings  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

# Initialise the Django HTTP app before importing consumers (they import models).
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import OriginValidator  # noqa: E402
from django.urls import path  # noqa: E402

from apps.contests.consumers import LeaderboardConsumer  # noqa: E402
from apps.submissions.consumers import SubmissionStatusConsumer  # noqa: E402
from apps.users.ws_auth import JWTCookieAuthMiddleware  # noqa: E402

websocket_urlpatterns = [
    # slug converter: Channels group names only allow [A-Za-z0-9_.-]
    path("ws/contests/<slug:contest_slug>/leaderboard/", LeaderboardConsumer.as_asgi()),
    path("ws/submissions/<uuid:submission_id>/", SubmissionStatusConsumer.as_asgi()),
]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # Origin check first (browser CSWSH protection), then authenticate the
        # handshake with the same HTTP-only JWT cookie the REST API uses.
        "websocket": OriginValidator(
            JWTCookieAuthMiddleware(URLRouter(websocket_urlpatterns)),
            settings.WS_ALLOWED_ORIGINS,
        ),
    }
)
