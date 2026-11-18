"""
Hints and AI assistance.

* POST /api/ai/hint/ returns the problem's *authored* progressive hints
  (Problem.hints_md, separated by '---'), one level at a time, metered by the
  per-plan daily quota (admin settings, else AI_HINTS_FREE_DAILY / AI_HINTS_PRO_DAILY).
  Free users get level 0 (matching the problem detail payload); Pro users get
  every level. Switched off with the "ai_hints" feature flag (503 feature_disabled).
* Chat, solution explanation and complexity analysis need an LLM provider,
  which is not integrated: these endpoints answer 501 code=coming_soon (features
  ai_chat / ai_explain / ai_complexity) rather than returning canned text.
  Integrating one requires provider credentials, an outbound network policy,
  timeouts and per-user quotas (AIInteraction already records usage).
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.features import FeatureEnabled, coming_soon_response
from apps.problems.models import Problem
from apps.users.models import User

from .models import AIInteraction
from .serializers import (
    AIChatRequestSerializer,
    AICodeRequestSerializer,
    AIHintRequestSerializer,
    AIHintResponseSerializer,
)


def _resolve_problem(data, user):
    qs = Problem.objects.all() if user.is_admin else Problem.objects.filter(is_published=True)
    if data.get("problem_slug"):
        return qs.filter(slug=data["problem_slug"]).first()
    return qs.filter(pk=data["problem_id"]).first()


def _used_today(user, interaction_type) -> int:
    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return AIInteraction.objects.filter(user=user, interaction_type=interaction_type, created_at__gte=start).count()


class AIHintView(APIView):
    """
    POST /api/ai/hint/   {problem_slug | problem_id, hint_level?: 0-based, user_code?}
    -> {hint, level, has_more, used_today, daily_limit, source: "authored"}
    403 pro_required for Pro-only levels/problems, 404 if no hint at that level,
    429 when the daily quota is used up.
    """
    permission_classes = [IsAuthenticated, FeatureEnabled("ai_hints")]

    def post(self, request):
        serializer = AIHintRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user

        contest = None
        if data.get("contest"):
            from apps.submissions.serializers import resolve_contest_problem

            contest, problem = resolve_contest_problem(data["contest"], data["problem_slug"], user)
        else:
            problem = _resolve_problem(data, user)
        if problem is None:
            return Response({"detail": "Problem not found."}, status=status.HTTP_404_NOT_FOUND)
        privileged = user.is_pro or user.is_admin
        if problem.visibility == Problem.Visibility.PRO and not privileged and not (contest and contest.status == "live"):
            return Response({"detail": "This problem requires a Pro plan.", "code": "pro_required"},
                            status=status.HTTP_403_FORBIDDEN)

        hints = problem.get_hints()
        level = data["hint_level"]
        if level >= len(hints):
            return Response({"detail": "No more hints for this problem.", "code": "no_more_hints"},
                            status=status.HTTP_404_NOT_FOUND)
        if level > 0 and not privileged:
            return Response({"detail": "Further hints are available on the Pro plan.", "code": "pro_required"},
                            status=status.HTTP_403_FORBIDDEN)

        limit = user.get_ai_hint_limit()
        with transaction.atomic():
            # Serialise per-user so concurrent requests cannot exceed the quota.
            User.objects.select_for_update().filter(pk=user.pk).first()
            used = _used_today(user, AIInteraction.INTERACTION_TYPE_HINT)
            if used >= limit:
                return Response(
                    {"detail": f"Daily hint limit reached ({limit}/day).", "code": "quota_exceeded",
                     "used_today": used, "daily_limit": limit},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            AIInteraction.objects.create(
                user=user, problem=problem, interaction_type=AIInteraction.INTERACTION_TYPE_HINT,
                query=f"hint_level={level}", response=hints[level], tokens_used=0,
            )

        has_more = level + 1 < len(hints)
        payload = {
            "hint": hints[level],
            "level": level,
            "has_more": has_more,
            "next_requires_pro": has_more and not privileged,
            "used_today": used + 1,
            "daily_limit": limit,
            "source": "authored",
        }
        return Response(AIHintResponseSerializer(payload).data, status=status.HTTP_200_OK)


class _ComingSoonView(APIView):
    """Validates the request, then answers 501 coming_soon for `feature`."""

    permission_classes = [IsAuthenticated]
    request_serializer = None
    feature = ""

    def post(self, request):
        self.request_serializer(data=request.data).is_valid(raise_exception=True)
        return coming_soon_response(self.feature)


class AIChatView(_ComingSoonView):
    """POST /api/ai/chat/ — coming soon (needs an LLM provider)."""
    request_serializer = AIChatRequestSerializer
    feature = "ai_chat"


class AIExplainSolutionView(_ComingSoonView):
    """POST /api/ai/explain-solution/ — coming soon (needs an LLM provider)."""
    request_serializer = AICodeRequestSerializer
    feature = "ai_explain"


class AIAnalyzeComplexityView(_ComingSoonView):
    """POST /api/ai/analyze-complexity/ — coming soon (needs an LLM provider)."""
    request_serializer = AICodeRequestSerializer
    feature = "ai_complexity"
