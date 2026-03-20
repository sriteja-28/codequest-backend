from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DiscussionThread, DiscussionComment
from .serializers import (
    DiscussionThreadSerializer,
    DiscussionThreadDetailSerializer,
    DiscussionCommentSerializer,
)


class DiscussionThreadListView(generics.ListAPIView):
    """
    GET /api/discuss/threads/
    List all discussion threads, optionally filtered by problem.
    """
    serializer_class = DiscussionThreadSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        qs = DiscussionThread.objects.select_related("author", "problem")
        problem_id = self.request.query_params.get("problem_id")
        if problem_id:
            qs = qs.filter(problem_id=problem_id)
        return qs.order_by("-created_at")


class DiscussionThreadDetailView(generics.RetrieveAPIView):
    """
    GET /api/discuss/threads/{id}/
    Retrieve a specific discussion thread with all comments.
    """
    serializer_class = DiscussionThreadDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "id"
    queryset = DiscussionThread.objects.select_related("author", "problem").prefetch_related("comments")


class DiscussionThreadCreateView(APIView):
    """
    POST /api/discuss/threads/create/
    Create a new discussion thread.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = DiscussionThreadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        thread = DiscussionThread.objects.create(
            author=request.user,
            **serializer.validated_data,
        )
        
        return Response(
            DiscussionThreadDetailSerializer(thread).data,
            status=status.HTTP_201_CREATED,
        )


class DiscussionCommentCreateView(APIView):
    """
    POST /api/discuss/comments/create/
    Create a new comment on a discussion thread.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        thread_id = request.data.get("thread")
        if not thread_id:
            return Response(
                {"detail": "thread ID is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            thread = DiscussionThread.objects.get(id=thread_id)
        except DiscussionThread.DoesNotExist:
            return Response(
                {"detail": "Thread not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DiscussionCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment = DiscussionComment.objects.create(
            author=request.user,
            thread=thread,
            content=serializer.validated_data.get("content"),
        )

        return Response(
            DiscussionCommentSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )
