import logging
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets

from .models import Contest, ContestParticipant, ContestProblem
from .serializers import (
    ContestListSerializer, ContestDetailSerializer,
    LeaderboardEntrySerializer, ContestAdminSerializer
)

logger = logging.getLogger(__name__)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class ContestListView(generics.ListAPIView):
    serializer_class = ContestListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Contest.objects.filter(is_public=True)


class ContestDetailView(generics.RetrieveAPIView):
    serializer_class = ContestDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"
    queryset = Contest.objects.filter(is_public=True)


class ContestRegisterView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug):
        try:
            contest = Contest.objects.get(slug=slug, is_public=True)
        except Contest.DoesNotExist:
            return Response({"detail": "Contest not found."}, status=status.HTTP_404_NOT_FOUND)

        if contest.status == "ended":
            return Response({"detail": "Contest has ended."}, status=status.HTTP_400_BAD_REQUEST)

        if contest.max_participants:
            count = contest.participants.count()
            if count >= contest.max_participants:
                return Response({"detail": "Contest is full."}, status=status.HTTP_400_BAD_REQUEST)

        _, created = ContestParticipant.objects.get_or_create(
            contest=contest, user=request.user
        )
        if not created:
            return Response({"detail": "Already registered."}, status=status.HTTP_200_OK)

        return Response({"detail": "Registered successfully."}, status=status.HTTP_201_CREATED)


class ContestLeaderboardView(generics.ListAPIView):
    serializer_class = LeaderboardEntrySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return ContestParticipant.objects.filter(
            contest__slug=self.kwargs["slug"],
            is_disqualified=False,
        ).select_related("user").order_by("rank", "-final_score")


class AdminContestViewSet(viewsets.ModelViewSet):
    queryset = Contest.objects.all()
    serializer_class = ContestAdminSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "slug"

    def perform_update(self, serializer):
        serializer.save()


class AdminContestParticipantView(APIView):
    """Admin: disqualify / update score / remove participant."""
    permission_classes = [IsAdminUser]

    def patch(self, request, slug, user_id):
        try:
            participant = ContestParticipant.objects.get(contest__slug=slug, user_id=user_id)
        except ContestParticipant.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        for field in ["is_disqualified", "disqualified_reason", "final_score", "rank"]:
            if field in request.data:
                setattr(participant, field, request.data[field])
        participant.save()

        # Broadcast leaderboard update
        _broadcast_leaderboard(slug)
        return Response({"ok": True})

    def delete(self, request, slug, user_id):
        ContestParticipant.objects.filter(contest__slug=slug, user_id=user_id).delete()
        _broadcast_leaderboard(slug)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _broadcast_leaderboard(contest_slug: str):
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    participants = ContestParticipant.objects.filter(
        contest__slug=contest_slug, is_disqualified=False
    ).select_related("user").order_by("rank", "-final_score")[:50]

    entries = LeaderboardEntrySerializer(participants, many=True).data
    channel_layer = get_channel_layer()
    try:
        async_to_sync(channel_layer.group_send)(
            f"leaderboard_{contest_slug}",
            {"type": "leaderboard_update", "entries": list(entries)},
        )
    except Exception as e:
        logger.warning(f"Leaderboard broadcast failed: {e}")