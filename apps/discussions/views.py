"""
apps/discussions/views.py

Discussion views with:
- Public viewing (no auth required)
- Auth required for posting
- Anonymous posting support
- Upvoting system
- Flagging (any user) and moderation (moderators/admins)
"""

from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import filters, generics, serializers, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.problems.models import Problem
from apps.admin_panel.audit import AuditedViewSetMixin, audited_update
from apps.core.features import FeatureEnabled

from .models import CommentUpvote, DiscussionComment, DiscussionThread, ThreadUpvote
from .serializers import (
    CommentCreateSerializer,
    DiscussionCommentSerializer,
    ThreadCreateSerializer,
    ThreadDetailSerializer,
    ThreadListSerializer,
    AdminThreadSerializer,
    AdminCommentSerializer,
)

DiscussionsEnabled = FeatureEnabled("discussions")


class IsModerator(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, "role", None) in ("ADMIN", "MODERATOR")


def thread_queryset():
    """Threads with correct counts. distinct=True is required: two Count()
    annotations over different joins otherwise multiply each other."""
    return (
        DiscussionThread.objects.select_related("problem", "author")
        .annotate(
            comment_count=Count("comments", filter=Q(comments__is_hidden=False), distinct=True),
            upvote_count=Count("upvotes", distinct=True),
        )
        .order_by("-is_pinned", "-updated_at")
    )


def visible_threads(user):
    qs = thread_queryset()
    if user.is_authenticated and user.is_admin:
        return qs
    from apps.contests.models import ContestProblem

    now = timezone.now()
    locked = ContestProblem.objects.filter(
        contest__start_at__lte=now, contest__end_at__gte=now,
        contest__finalized_at__isnull=True,
    ).values("problem_id")
    return qs.filter(problem__is_published=True).exclude(problem_id__in=locked)


def discussion_problem(slug, user):
    from apps.problems.views import problem_in_live_contest

    problem = get_object_or_404(Problem, slug=slug, is_published=True)
    if not (user.is_authenticated and user.is_admin) and problem_in_live_contest(problem):
        raise PermissionDenied({"detail": "Discussions open when the contest ends.", "code": "contest_locked"})
    return problem


def visible_comment(comment_id, user, **filters):
    return get_object_or_404(
        DiscussionComment.objects.filter(thread_id__in=visible_threads(user).values("pk")),
        id=comment_id, **filters,
    )


class _RequestContextMixin:
    def get_serializer_context(self):
        return {"request": self.request}


class ThreadListView(_RequestContextMixin, generics.ListAPIView):
    """
    List all discussion threads (public - no auth required).
    GET /api/discuss/threads/
    """
    permission_classes = [DiscussionsEnabled]
    serializer_class = ThreadListSerializer

    def get_queryset(self):
        return visible_threads(self.request.user)


class ProblemThreadListView(_RequestContextMixin, generics.ListAPIView):
    """
    List threads for a specific problem (public).
    GET /api/discuss/problems/{slug}/threads/
    """
    permission_classes = [DiscussionsEnabled]
    serializer_class = ThreadListSerializer

    def get_queryset(self):
        problem = discussion_problem(self.kwargs["slug"], self.request.user)
        return visible_threads(self.request.user).filter(problem=problem)


class ThreadDetailView(_RequestContextMixin, generics.RetrieveAPIView):
    """
    Get single thread with comments (public).
    GET /api/discuss/threads/{id}/
    """
    permission_classes = [DiscussionsEnabled]
    serializer_class = ThreadDetailSerializer
    lookup_field = "id"

    def get_queryset(self):
        return visible_threads(self.request.user).prefetch_related("comments__author", "comments__upvotes")

    def retrieve(self, request, *args, **kwargs):
        """Increment view count atomically, then serialize fresh data."""
        instance = self.get_object()
        DiscussionThread.objects.filter(id=instance.id).update(view_count=F("view_count") + 1)
        instance = self.get_object()
        return Response(self.get_serializer(instance).data)


class ThreadCreateView(_RequestContextMixin, generics.CreateAPIView):
    """
    Create new thread (requires authentication).
    POST /api/discuss/problems/{slug}/threads/create/
    Body: { "title": "...", "content": "...", "is_anonymous": false }
    """
    permission_classes = [IsAuthenticated, DiscussionsEnabled]
    serializer_class = ThreadCreateSerializer

    def perform_create(self, serializer):
        problem = discussion_problem(self.kwargs["slug"], self.request.user)
        serializer.save(problem=problem, author=self.request.user)


class CommentListView(_RequestContextMixin, generics.ListAPIView):
    """
    List comments for a thread (public).
    GET /api/discuss/threads/{thread_id}/comments/
    """
    permission_classes = [DiscussionsEnabled]
    serializer_class = DiscussionCommentSerializer

    def get_queryset(self):
        thread = get_object_or_404(visible_threads(self.request.user), id=self.kwargs["thread_id"])
        return DiscussionComment.objects.filter(
            thread=thread,
            parent=None,  # Only top-level comments
            is_hidden=False,
        ).select_related(
            "author", "thread"
        ).prefetch_related(
            "upvotes", "replies__author", "replies__upvotes"
        ).order_by("-is_accepted_answer", "-created_at")


class CommentCreateView(generics.CreateAPIView):
    """
    Create new comment (requires authentication).
    POST /api/discuss/threads/{thread_id}/comments/create/
    Body: { "body_md": "...", "parent": null, "is_anonymous": false }
    """
    permission_classes = [IsAuthenticated, DiscussionsEnabled]
    serializer_class = CommentCreateSerializer

    def _thread(self):
        if not hasattr(self, "_thread_obj"):
            self._thread_obj = get_object_or_404(visible_threads(self.request.user), id=self.kwargs["thread_id"])
        return self._thread_obj

    def get_serializer_context(self):
        return {"request": self.request, "thread": self._thread()}

    def perform_create(self, serializer):
        thread = self._thread()
        if thread.is_locked:
            raise serializers.ValidationError("Cannot comment on locked thread")
        serializer.save(thread=thread, author=self.request.user)
        # Bump the thread so "recent activity" ordering reflects the new comment.
        DiscussionThread.objects.filter(pk=thread.pk).update(updated_at=serializer.instance.created_at)


def _toggle(model, user, **target):
    """Toggle an upvote row; safe against double-clicks racing each other."""
    existing = model.objects.filter(user=user, **target).first()
    if existing:
        existing.delete()
        return "removed"
    try:
        with transaction.atomic():
            model.objects.create(user=user, **target)
    except IntegrityError:
        return "added"  # a concurrent request created it
    return "added"


@api_view(["POST"])
@permission_classes([IsAuthenticated, DiscussionsEnabled])
def upvote_thread(request, thread_id):
    """
    Upvote or remove upvote from thread (toggle).
    POST /api/discuss/threads/{thread_id}/upvote/
    """
    thread = get_object_or_404(visible_threads(request.user), id=thread_id)
    action = _toggle(ThreadUpvote, request.user, thread=thread)
    return Response({
        "action": action,
        "upvote_count": thread.upvotes.count(),
        "has_upvoted": action == "added",
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated, DiscussionsEnabled])
def upvote_comment(request, comment_id):
    """
    Upvote or remove upvote from comment (toggle).
    POST /api/discuss/comments/{comment_id}/upvote/
    """
    comment = visible_comment(comment_id, request.user)
    action = _toggle(CommentUpvote, request.user, comment=comment)
    return Response({
        "action": action,
        "upvotes": comment.upvotes.count(),
        "has_upvoted": action == "added",
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated, DiscussionsEnabled])
def mark_accepted_answer(request, comment_id):
    """
    Mark/unmark comment as accepted answer (thread author or admin only).
    POST /api/discuss/comments/{comment_id}/accept/
    """
    comment = visible_comment(comment_id, request.user)
    user = request.user

    if user != comment.thread.author and getattr(user, "role", None) not in ["ADMIN", "MODERATOR"]:
        return Response(
            {"error": "Only thread author or admins can mark accepted answer",
             "detail": "Only thread author or admins can mark accepted answer"},
            status=status.HTTP_403_FORBIDDEN,
        )

    comment.is_accepted_answer = not comment.is_accepted_answer
    comment.save(update_fields=["is_accepted_answer"])
    return Response({"is_accepted_answer": comment.is_accepted_answer})


@api_view(["POST"])
@permission_classes([IsAuthenticated, DiscussionsEnabled])
def flag_comment(request, comment_id):
    """
    Report a comment for moderator review.
    POST /api/discuss/comments/{comment_id}/flag/
    """
    comment = visible_comment(comment_id, request.user, is_hidden=False)
    if not comment.is_flagged:
        comment.is_flagged = True
        comment.save(update_fields=["is_flagged"])
    return Response({"ok": True, "is_flagged": True})


@api_view(["PATCH"])
@permission_classes([IsModerator])
def moderate_comment(request, comment_id):
    """
    Hide/unhide a comment or clear its flag (moderators and admins).
    PATCH /api/discuss/admin/comments/{comment_id}/moderate/
    Body: { "is_hidden"?: bool, "is_flagged"?: bool }
    """
    comment = get_object_or_404(DiscussionComment, id=comment_id)
    values = {}
    for field in ("is_hidden", "is_flagged"):
        if field in request.data:
            value = request.data[field]
            if not isinstance(value, bool):
                return Response({"detail": f"{field} must be a boolean."}, status=status.HTTP_400_BAD_REQUEST)
            values[field] = value
    if not values:
        return Response({"detail": "Provide is_hidden and/or is_flagged."}, status=status.HTTP_400_BAD_REQUEST)
    if values.get("is_hidden", comment.is_hidden):
        values["is_flagged"] = False

    def apply():
        for field, value in values.items():
            setattr(comment, field, value)
        comment.save(update_fields=list(values))

    audited_update(actor=request.user, instance=comment, apply=apply)
    return Response({"ok": True, "is_hidden": comment.is_hidden, "is_flagged": comment.is_flagged})


class AdminThreadViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    """Moderation: full thread CRUD, including pin/lock and unpublished problems."""
    queryset = DiscussionThread.objects.select_related("author", "problem").order_by("-updated_at", "-id")
    serializer_class = AdminThreadSerializer
    permission_classes = [IsModerator]
    filter_backends = [filters.SearchFilter]
    search_fields = ["title", "author__username", "problem__title"]

    def create_kwargs(self):
        return {"author": self.request.user}


class AdminCommentViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = AdminCommentSerializer
    permission_classes = [IsModerator]
    filter_backends = [filters.SearchFilter]
    search_fields = ["content", "author__username", "thread__title"]

    def get_queryset(self):
        qs = DiscussionComment.objects.select_related("author", "thread").order_by("-created_at", "-id")
        for name in ("is_flagged", "is_hidden"):
            if self.request.query_params.get(name) in ("true", "false"):
                qs = qs.filter(**{name: self.request.query_params[name] == "true"})
        if self.request.query_params.get("thread", "").isdigit():
            qs = qs.filter(thread_id=self.request.query_params["thread"])
        return qs

    def create_kwargs(self):
        return {"author": self.request.user}
