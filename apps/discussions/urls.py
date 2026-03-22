"""
apps/discussions/urls.py

URL patterns for discussion API endpoints.
"""

from django.urls import path
from .views import (
    ThreadListView, ProblemThreadListView, ThreadDetailView, ThreadCreateView,
    CommentListView, CommentCreateView,
    upvote_thread, upvote_comment, mark_accepted_answer
)

urlpatterns = [
    # Thread endpoints
    path('threads/', ThreadListView.as_view(), name='thread-list'),  # GET /api/discuss/threads/
    path('threads/<int:id>/', ThreadDetailView.as_view(), name='thread-detail'),  # GET /api/discuss/threads/{id}/
    path('threads/<int:thread_id>/upvote/', upvote_thread, name='thread-upvote'),  # POST /api/discuss/threads/{id}/upvote/
    
    # Problem-specific threads
    path('problems/<slug:slug>/threads/', ProblemThreadListView.as_view(), name='problem-threads'),  # GET /api/discuss/problems/{slug}/threads/
    path('problems/<slug:slug>/threads/create/', ThreadCreateView.as_view(), name='thread-create'),  # POST /api/discuss/problems/{slug}/threads/create/
    
    # Comment endpoints
    path('threads/<int:thread_id>/comments/', CommentListView.as_view(), name='comment-list'),  # GET /api/discuss/threads/{id}/comments/
    path('threads/<int:thread_id>/comments/create/', CommentCreateView.as_view(), name='comment-create'),  # POST /api/discuss/threads/{id}/comments/create/
    path('comments/<int:comment_id>/upvote/', upvote_comment, name='comment-upvote'),  # POST /api/discuss/comments/{id}/upvote/
    path('comments/<int:comment_id>/accept/', mark_accepted_answer, name='comment-accept'),  # POST /api/discuss/comments/{id}/accept/
]