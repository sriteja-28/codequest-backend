from django.urls import path
from .views import (
    AIAnalyzeComplexityView,
    AIChatView,
    AIExplainSolutionView,
    AIHintView,
)

urlpatterns = [
    path("hint/", AIHintView.as_view(), name="ai-hint"),
    path("chat/", AIChatView.as_view(), name="ai-chat"),
    path("explain-solution/", AIExplainSolutionView.as_view(), name="ai-explain-solution"),
    path("analyze-complexity/", AIAnalyzeComplexityView.as_view(), name="ai-analyze-complexity"),
]
