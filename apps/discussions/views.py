"""
apps/discussions/views.py

Discussion views with:
- Public viewing (no auth required)
- Auth required for posting
- Anonymous posting support
- Upvoting system
"""

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Count

from .models import DiscussionThread, DiscussionComment, ThreadUpvote, CommentUpvote
from .serializers import (
    ThreadListSerializer, ThreadDetailSerializer, ThreadCreateSerializer,
    DiscussionCommentSerializer, CommentCreateSerializer
)
from apps.problems.models import Problem

# importing serializers for validation errors
from rest_framework import serializers


class ThreadListView(generics.ListAPIView):
    """
    List all discussion threads (public - no auth required).
    GET /api/discuss/threads/
    """
    permission_classes = [AllowAny]
    serializer_class = ThreadListSerializer
    
    def get_queryset(self):
        """Return all threads with comment counts."""
        return DiscussionThread.objects.select_related(
            'problem', 'author'
        ).annotate(
            comment_count=Count('comments')
        ).order_by('-is_pinned', '-updated_at')
    
    # adding serializer context
    def get_serializer_context(self):
        return {"request": self.request}


class ProblemThreadListView(generics.ListAPIView):
    """
    List threads for a specific problem (public).
    GET /api/discuss/problems/{slug}/threads/
    """
    permission_classes = [AllowAny]
    serializer_class = ThreadListSerializer
    
    def get_queryset(self):
        """Return threads for specific problem."""
        problem_slug = self.kwargs['slug']
        problem = get_object_or_404(Problem, slug=problem_slug)
        
        return DiscussionThread.objects.filter(
            problem=problem
        ).select_related(
            'problem', 'author'
        ).annotate(
            comment_count=Count('comments'),
            # adding upvote count to avoid n+1 queries
            upvote_count=Count('upvotes')
        ).order_by('-is_pinned', '-updated_at')
    
    # adding serializer context
    def get_serializer_context(self):
        return {"request": self.request}


class ThreadDetailView(generics.RetrieveAPIView):
    """
    Get single thread with comments (public).
    GET /api/discuss/threads/{id}/
    """
    permission_classes = [AllowAny]
    serializer_class = ThreadDetailSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        """Return thread with related data."""
        return DiscussionThread.objects.select_related(
            'problem', 'author'
        ).prefetch_related(
            'comments__author', 'comments__upvotes'
        ).annotate(
            comment_count=Count('comments')
        )
    
    def retrieve(self, request, *args, **kwargs):
        """Increment view count when thread is viewed."""
        instance = self.get_object()
        # instance.view_count += 1
        # instance.save(update_fields=['view_count'])

        # safely incrementing view count
        from django.db.models import F

        DiscussionThread.objects.filter(id=instance.id).update(
            view_count=F('view_count') + 1
        )
        instance.view_count += 1

        # refreshing instance to get updated value
        instance.refresh_from_db()

        # serializing updated data
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    # adding serializer context
    def get_serializer_context(self):
        return {"request": self.request}


class ThreadCreateView(generics.CreateAPIView):
    """
    Create new thread (requires authentication).
    POST /api/discuss/problems/{slug}/threads/
    Body: { "title": "...", "content": "...", "is_anonymous": false }
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ThreadCreateSerializer
    
    def perform_create(self, serializer):
        """Set problem and author."""
        problem_slug = self.kwargs['slug']
        problem = get_object_or_404(Problem, slug=problem_slug)
        serializer.save(problem=problem, author=self.request.user)
    
    # adding serializer context
    def get_serializer_context(self):
        return {"request": self.request}


class CommentListView(generics.ListAPIView):
    """
    List comments for a thread (public).
    GET /api/discuss/threads/{thread_id}/comments/
    """
    permission_classes = [AllowAny]
    serializer_class = DiscussionCommentSerializer
    
    def get_queryset(self):
        """Return top-level comments for thread."""
        thread_id = self.kwargs['thread_id']
        thread = get_object_or_404(DiscussionThread, id=thread_id)
        
        return DiscussionComment.objects.filter(
            thread=thread,
            parent=None,  # Only top-level comments
            is_hidden=False
        ).select_related(
            'author', 'thread'
        ).prefetch_related(
            'upvotes', 'replies__author', 'replies__upvotes'
        ).order_by('-is_accepted_answer', '-created_at')
    # adding serializer context
    def get_serializer_context(self):
        return {"request": self.request}


class CommentCreateView(generics.CreateAPIView):
    """
    Create new comment (requires authentication).
    POST /api/discuss/threads/{thread_id}/comments/
    Body: { "body_md": "...", "parent": null, "is_anonymous": false }
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CommentCreateSerializer
    
    def perform_create(self, serializer):
        """Set thread and author."""
        thread_id = self.kwargs['thread_id']
        thread = get_object_or_404(DiscussionThread, id=thread_id)
        
        # Check if thread is locked
        if thread.is_locked:
            raise serializers.ValidationError("Cannot comment on locked thread")
        
        serializer.save(thread=thread, author=self.request.user)

    # adding serializer context
    def get_serializer_context(self):
        return {"request": self.request}

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upvote_thread(request, thread_id):
    """
    Upvote or remove upvote from thread.
    POST /api/discuss/threads/{thread_id}/upvote/
    
    Toggles upvote: if already upvoted, removes it; otherwise adds it.
    """
    thread = get_object_or_404(DiscussionThread, id=thread_id)
    user = request.user
    
    # Check if already upvoted
    upvote = ThreadUpvote.objects.filter(thread=thread, user=user).first()
    
    if upvote:
        # Remove upvote
        upvote.delete()
        action = 'removed'
    else:
        # Add upvote
        ThreadUpvote.objects.create(thread=thread, user=user)
        action = 'added'

    # refresh correct count from DB
    upvote_count = thread.upvotes.count()
    
    return Response({
        'action': action,
        # 'upvote_count': thread.upvote_count,
        'upvote_count': upvote_count,
        'has_upvoted': action == 'added'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upvote_comment(request, comment_id):
    """
    Upvote or remove upvote from comment.
    POST /api/discuss/comments/{comment_id}/upvote/
    
    Toggles upvote: if already upvoted, removes it; otherwise adds it.
    """
    comment = get_object_or_404(DiscussionComment, id=comment_id)
    user = request.user
    
    # Check if already upvoted
    upvote = CommentUpvote.objects.filter(comment=comment, user=user).first()
    
    if upvote:
        # Remove upvote
        upvote.delete()
        action = 'removed'
    else:
        # Add upvote
        CommentUpvote.objects.create(comment=comment, user=user)
        action = 'added'

    upvote_count = comment.upvotes.count()
    
    return Response({
        'action': action,
        'upvotes': upvote_count,
        # 'upvotes': comment.upvote_count,
        'has_upvoted': action == 'added'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_accepted_answer(request, comment_id):
    """
    Mark/unmark comment as accepted answer (thread author or admin only).
    POST /api/discuss/comments/{comment_id}/accept/
    """
    comment = get_object_or_404(DiscussionComment, id=comment_id)
    user = request.user
    
    # Only thread author or admins can mark accepted answer
    # if user != comment.thread.author and user.role not in ['ADMIN', 'MODERATOR']:
    # safely checking role
    if user != comment.thread.author and getattr(user, "role", None) not in ['ADMIN', 'MODERATOR']:
        return Response(
            {'error': 'Only thread author or admins can mark accepted answer'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Toggle accepted answer
    comment.is_accepted_answer = not comment.is_accepted_answer
    comment.save(update_fields=['is_accepted_answer'])
    
    return Response({
        'is_accepted_answer': comment.is_accepted_answer
    })