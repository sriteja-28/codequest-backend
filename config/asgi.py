"""
ASGI config — Django + Channels
Handles both HTTP (Django) and WebSocket (Channels) connections.
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.contests.consumers import LeaderboardConsumer
from apps.submissions.consumers import SubmissionStatusConsumer
from django.urls import path

websocket_urlpatterns = [
    path("ws/contests/<str:contest_slug>/leaderboard/", LeaderboardConsumer.as_asgi()),
    # path("ws/submissions/<str:submission_id>/", SubmissionStatusConsumer.as_asgi()),
    path('ws/submissions/<uuid:submission_id>/', SubmissionStatusConsumer.as_asgi()),
]

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    }
)

