from django.urls import path
from .views import (
    DiscussionThreadListView,
    DiscussionThreadDetailView,
    DiscussionThreadCreateView,
    DiscussionCommentCreateView,
)

urlpatterns = [
    path("threads/", DiscussionThreadListView.as_view(), name="discussion-thread-list"),
    path("threads/create/", DiscussionThreadCreateView.as_view(), name="discussion-thread-create"),
    path("threads/<int:id>/", DiscussionThreadDetailView.as_view(), name="discussion-thread-detail"),
    path("comments/create/", DiscussionCommentCreateView.as_view(), name="discussion-comment-create"),
]
