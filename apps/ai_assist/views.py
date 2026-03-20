from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ObjectDoesNotExist

from apps.problems.models import Problem
from .serializers import (
    AIHintRequestSerializer,
    AIHintResponseSerializer,
    AIChatRequestSerializer,
    AIChatResponseSerializer,
)


class AIHintView(APIView):
    """
    POST /api/ai/hint/
    Generate an AI hint for a problem based on user's plan/level.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIHintRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check rate limit based on user's plan
        if hasattr(request.user, "get_ai_hint_limit"):
            limit = request.user.get_ai_hint_limit()
        else:
            limit = 20  # Free tier default

        # Placeholder: In production, integrate with OpenAI or similar
        hint_data = {
            "hint": "Consider using a hash map to store previously computed values.",
            "level": 1,
        }

        response_serializer = AIHintResponseSerializer(hint_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class AIChatView(APIView):
    """
    POST /api/ai/chat/
    Chat with AI about a problem or general coding questions.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AIChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check rate limit based on user's plan
        if hasattr(request.user, "get_ai_chat_limit"):
            limit = request.user.get_ai_chat_limit()
        else:
            limit = 20  # Free tier default

        # Placeholder: In production, integrate with OpenAI or similar
        response_data = {
            "response": "This is a complex algorithmic problem. I suggest breaking it into steps...",
            "tokens_used": 150,
        }

        response_serializer = AIChatResponseSerializer(response_data)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
