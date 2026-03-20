from django.urls import path
from .views import (
    AIHintView,
    AIChatView,
)

urlpatterns = [
    path("hint/", AIHintView.as_view(), name="ai-hint"),
    path("chat/", AIChatView.as_view(), name="ai-chat"),
]
