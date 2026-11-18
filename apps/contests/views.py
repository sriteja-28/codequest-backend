import logging
import hashlib
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_panel.audit import AuditedViewSetMixin, diff, record, snapshot
from apps.core.features import FeatureEnabled
from config.pagination import LargePagination

from .access import ContestAccessError, contest_problem_for, participations_by_contest, visible_contest
from .finalize import finalize_due_lazily, maybe_finalize
from .models import Contest, ContestParticipant
from .serializers import (
    AdminParticipantSerializer,
    ContestAdminSerializer,
    ContestDetailSerializer,
    ContestListSerializer,
    LeaderboardEntrySerializer,
    ParticipantUpdateSerializer,
)

logger = logging.getLogger(__name__)

# Public contest endpoints answer 503 feature_disabled while an admin has
# switched contests off (admins keep access).
ContestsEnabled = FeatureEnabled("contests")


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


def leaderboard_queryset(contest_slug: str):
    return (
        ContestParticipant.objects.filter(contest__slug=contest_slug, is_disqualified=False)
        .select_related("user")
        .prefetch_related("problem_stats")
        .order_by(F("rank").asc(nulls_last=True), "-final_score", "registered_at")
    )


class ContestListView(generics.ListAPIView):
    """
    GET /api/contests/?bucket=&search=&page=&page_size=

    bucket=current   live + upcoming, soonest start first
    bucket=recent    ended within PlatformSettings.contest_recent_days, newest first
    bucket=archive   ended before that window, newest first
    bucket=ended     recent + archive
    (none/unknown)   every public contest, newest start first
    Overdue contests are finalized (bounded, lazily) before ended contests are listed.
    """

    serializer_class = ContestListSerializer
    permission_classes = [ContestsEnabled]

    def get_queryset(self):
        from apps.core.site import contest_recent_days

        now = timezone.now()
        qs = Contest.objects.filter(is_public=True).annotate(
            participant_total=Count("participants", distinct=True),
            problem_total=Count("contest_problems", distinct=True),
        )
        bucket = self.request.query_params.get("bucket", "")
        cutoff = now - timedelta(days=contest_recent_days())
        if bucket == "current":
            qs = qs.filter(end_at__gte=now).order_by("start_at", "id")
        elif bucket == "recent":
            qs = qs.filter(end_at__lt=now, end_at__gte=cutoff).order_by("-end_at", "-id")
        elif bucket == "archive":
            qs = qs.filter(end_at__lt=cutoff).order_by("-end_at", "-id")
        elif bucket == "ended":
            qs = qs.filter(end_at__lt=now).order_by("-end_at", "-id")
        else:
            # Explicit: Meta.ordering is ignored by GROUP BY (annotated) queries.
            qs = qs.order_by("-start_at", "-id")
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def list(self, request, *args, **kwargs):
        if request.query_params.get("bucket") != "current":
            finalize_due_lazily()
        return super().list(request, *args, **kwargs)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["participations"] = participations_by_contest(self.request.user)
        return ctx


class ContestDetailView(generics.RetrieveAPIView):
    """GET /api/contests/{slug}/ (an overdue contest is finalized on the way)."""

    serializer_class = ContestDetailSerializer
    permission_classes = [ContestsEnabled]
    lookup_field = "slug"
    queryset = Contest.objects.filter(is_public=True)

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_admin:
            return Contest.objects.all()
        return super().get_queryset()

    def retrieve(self, request, *args, **kwargs):
        contest = self.get_object()
        maybe_finalize(contest)
        # The serializer context (and the caller's rank) is built after finalizing.
        return Response(self.get_serializer(contest).data)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["participations"] = participations_by_contest(self.request.user)
        return ctx


class ContestProblemDetailView(APIView):
    """
    GET /api/contests/{slug}/problems/{problem_slug}/
    A contest problem opened through its contest, published or not (rules in
    apps/contests/access.py): 403 `contest_not_started` before the start, 404 when
    the problem is not in the contest, 403 `pro_required` after the end for Pro
    problems without Pro. Same body as GET /api/problems/{slug}/ plus
    `practice_available` (true once the problem is in the practice catalogue).
    """

    permission_classes = [ContestsEnabled]

    def get(self, request, slug, problem_slug):
        from apps.problems.models import Star
        from apps.problems.serializers import ProblemDetailSerializer
        from apps.problems.views import pro_required_response
        from apps.users.models import UserSolvedProblem

        contest = visible_contest(user=request.user, slug=slug)
        if contest is None:
            return Response({"detail": "Contest not found."}, status=status.HTTP_404_NOT_FOUND)
        maybe_finalize(contest)
        try:
            problem = contest_problem_for(contest, problem_slug, request.user)
        except ContestAccessError as exc:
            if exc.code == ContestAccessError.PRO_REQUIRED:
                return pro_required_response(exc.problem)
            code = (
                status.HTTP_404_NOT_FOUND
                if exc.code == ContestAccessError.NOT_IN_CONTEST
                else status.HTTP_403_FORBIDDEN
            )
            return Response({"detail": exc.message, "code": exc.code}, status=code)

        user = request.user
        signed_in = user.is_authenticated
        solved = signed_in and UserSolvedProblem.objects.filter(user=user, problem=problem).exists()
        starred = signed_in and Star.objects.filter(user=user, problem=problem).exists()
        context = {
            "request": request,
            "solved_ids": {problem.id} if solved else set(),
            "starred_ids": {problem.id} if starred else set(),
        }
        data = ProblemDetailSerializer(problem, context=context).data
        # Practice prev/next navigation does not apply inside a contest.
        data["next_slug"] = None
        data["prev_slug"] = None
        data["practice_available"] = problem.is_published
        return Response(data)


class ContestRegisterView(APIView):
    permission_classes = [permissions.IsAuthenticated, ContestsEnabled]

    def post(self, request, slug):
        with transaction.atomic():
            # Lock the contest row so concurrent registrations cannot exceed max_participants.
            contest = Contest.objects.select_for_update().filter(slug=slug, is_public=True).first()
            if contest is None:
                return Response({"detail": "Contest not found."}, status=status.HTTP_404_NOT_FOUND)

            if contest.status == "ended":
                return Response({"detail": "Contest has ended."}, status=status.HTTP_400_BAD_REQUEST)

            if ContestParticipant.objects.filter(contest=contest, user=request.user).exists():
                return Response({"detail": "Already registered."}, status=status.HTTP_200_OK)

            if contest.max_participants and contest.participants.count() >= contest.max_participants:
                return Response({"detail": "Contest is full."}, status=status.HTTP_400_BAD_REQUEST)

            ContestParticipant.objects.create(contest=contest, user=request.user)

        return Response({"detail": "Registered successfully."}, status=status.HTTP_201_CREATED)


class ContestLeaderboardView(generics.ListAPIView):
    """GET /api/contests/{slug}/leaderboard/ (final once the contest is finalized)."""

    serializer_class = LeaderboardEntrySerializer
    permission_classes = [ContestsEnabled]

    def list(self, request, *args, **kwargs):
        contest = visible_contest(user=request.user, slug=self.kwargs["slug"])
        if contest is None:
            return Response({"detail": "Contest not found."}, status=status.HTTP_404_NOT_FOUND)
        maybe_finalize(contest)
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        return leaderboard_queryset(self.kwargs["slug"])


class AdminContestViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    """
    GET/POST /api/contests/admin/contests/[?status=upcoming|live|ended&search=]
    GET/PATCH/DELETE .../{slug}/      (problem_entries locked once started; audited)
    GET  .../{slug}/participants/     every participant incl. disqualified (?search=)
    POST .../{slug}/finalize/         {force?: bool} finalize an ended contest now
    """

    serializer_class = ContestAdminSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "slug"
    pagination_class = LargePagination

    def get_queryset(self):
        qs = (
            Contest.objects.annotate(participant_total=Count("participants", distinct=True))
            .prefetch_related("contest_problems__problem")
            .order_by("-start_at", "-id")
        )
        params = self.request.query_params
        now = timezone.now()
        state = params.get("status", "")
        if state == "upcoming":
            qs = qs.filter(start_at__gt=now)
        elif state == "live":
            qs = qs.filter(start_at__lte=now, end_at__gte=now, finalized_at__isnull=True)
        elif state == "ended":
            qs = qs.filter(Q(end_at__lt=now) | Q(finalized_at__isnull=False))
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(slug__icontains=search))
        return qs

    def audit_snapshot(self, instance):
        data = super().audit_snapshot(instance)
        data["problems"] = [
            f"{problem_id}:{score}"
            for problem_id, score in instance.contest_problems.order_by("order_index", "id").values_list("problem_id", "score")
        ]
        return data

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            # Serialize with registrations, verdicts and finalization of this contest.
            Contest.objects.select_for_update().filter(slug=kwargs.get("slug")).first()
            return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def participants(self, request, slug=None):
        contest = self.get_object()
        qs = (
            contest.participants.select_related("user").prefetch_related("problem_stats")
            .order_by(F("rank").asc(nulls_last=True), "-final_score", "registered_at")
        )
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(user__username__icontains=search) | Q(user__email__icontains=search))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(AdminParticipantSerializer(page, many=True).data)

    @action(detail=True, methods=["post"])
    def finalize(self, request, slug=None):
        from .finalize import ALREADY, FINALIZED, NOT_ENDED, finalize_contest

        contest = self.get_object()
        force = str(request.data.get("force", "")).lower() in ("1", "true", "yes")
        result = finalize_contest(contest, force=force, actor=request.user)
        body = {
            "outcome": result.outcome, "released": result.released,
            "pending": result.pending, "participants": result.participants,
        }
        if result.outcome in (FINALIZED, ALREADY):
            return Response(body)
        body["detail"] = (
            "The contest has not ended yet." if result.outcome == NOT_ENDED
            else f"{result.pending} submission(s) are still being judged. Wait, or finalize without them."
        )
        return Response(body, status=status.HTTP_409_CONFLICT)


class AdminContestParticipantView(APIView):
    """Admin corrections before finalization (audited):
    PATCH  .../admin/contests/{slug}/participants/{user_id}/
           {is_disqualified?, disqualified_reason?, score_adjustment?, adjustment_reason?}
    DELETE .../admin/contests/{slug}/participants/{user_id}/   (unregister)
    Scores and ranks are recomputed; final standings (after finalization) are read-only."""

    permission_classes = [IsAdminUser]

    def patch(self, request, slug, user_id):
        from .scoring import recalculate_ranks, recalculate_score

        with transaction.atomic():
            contest = Contest.objects.select_for_update().filter(slug=slug).first()
            if contest is None:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            if contest.is_finalized:
                return Response({"detail": "Final standings are read-only."}, status=status.HTTP_409_CONFLICT)
            participant = contest.participants.select_related("user").filter(user_id=user_id).first()
            if participant is None:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            serializer = ParticipantUpdateSerializer(participant, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            before = snapshot(participant)
            serializer.save()
            recalculate_score(participant)
            recalculate_ranks(contest)
            contest.participants.filter(is_disqualified=True).update(rank=None)
            participant.refresh_from_db()
            changes = diff(before, snapshot(participant))
            if changes:
                name = participant.user.username
                if "is_disqualified" in changes:
                    verb = "Disqualified" if participant.is_disqualified else "Reinstated"
                    description = f"{verb} {name} in '{contest.name}'"
                else:
                    description = f"Adjusted {name}'s score in '{contest.name}' by {participant.score_adjustment:+d}"
                record(actor=request.user, action="UPDATE", obj=participant, changes=changes, description=description)
            transaction.on_commit(lambda: _broadcast_leaderboard(slug))
        return Response(AdminParticipantSerializer(participant).data)

    def delete(self, request, slug, user_id):
        from .scoring import recalculate_ranks

        with transaction.atomic():
            contest = Contest.objects.select_for_update().filter(slug=slug).first()
            if contest is None:
                return Response(status=status.HTTP_204_NO_CONTENT)  # idempotent delete
            if contest.is_finalized:
                return Response({"detail": "Final standings are read-only."}, status=status.HTTP_409_CONFLICT)
            participant = contest.participants.select_related("user").filter(user_id=user_id).first()
            if participant is not None:
                text, pk = str(participant), participant.pk
                participant.delete()
                record(actor=request.user, action="DELETE", object_type="contest_participant", object_id=pk,
                       object_repr=text, description=f"Removed {text}")
                recalculate_ranks(contest)
                transaction.on_commit(lambda: _broadcast_leaderboard(slug))
        return Response(status=status.HTTP_204_NO_CONTENT)


def leaderboard_group(contest_slug: str):
    # Channel group names are limited to 100 chars; contest slugs allow 120.
    return f"leaderboard_{hashlib.sha256(contest_slug.encode()).hexdigest()}"


def leaderboard_snapshot(contest):
    return {
        "type": "leaderboard_update",
        "entries": list(LeaderboardEntrySerializer(leaderboard_queryset(contest.slug)[:50], many=True).data),
        "finalized": contest.is_finalized,
        "status": contest.status,
    }


def _broadcast_leaderboard(contest_slug: str):
    from apps.core.channels import send_to_group

    try:
        contest = Contest.objects.filter(slug=contest_slug).first()
        if contest is None:
            return
        send_to_group(
            leaderboard_group(contest_slug),
            leaderboard_snapshot(contest),
        )
    except Exception as e:
        logger.warning(f"Leaderboard broadcast failed: {e}")
