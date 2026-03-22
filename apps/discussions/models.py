"""
apps/discussions/models.py

Discussion system with:
- Upvoting for threads and comments
- Anonymous posting (tracked by admins, hidden from users)
- View tracking
- Accepted answers
"""

from django.db import models
from django.utils import timezone


class DiscussionThread(models.Model):
    """Discussion thread on a specific problem."""
    problem = models.ForeignKey(
        "problems.Problem", on_delete=models.CASCADE, related_name="discussion_threads"
    )
    author = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="discussion_threads"
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Anonymous posting - author is tracked but hidden from users
    is_anonymous = models.BooleanField(default=False)
    
    view_count = models.PositiveIntegerField(default=0)
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discussion_threads"
        ordering = ["-is_pinned", "-updated_at"]
        indexes = [
            models.Index(fields=["problem", "-created_at"]),
            models.Index(fields=["author", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.title} (Problem: {self.problem.slug})"
    
    # @property
    # def comment_count(self):
    #     """Total number of comments on this thread."""
    #     return self.comments.count()
    
    # @property
    # def upvote_count(self):
    #     """Total upvotes for this thread."""
    #     return self.upvotes.count()


class DiscussionComment(models.Model):
    """Comment on a discussion thread."""
    thread = models.ForeignKey(
        DiscussionThread, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="discussion_comments"
    )
    content = models.TextField()
    
    # Anonymous posting
    is_anonymous = models.BooleanField(default=False)
    
    # Nested comments support
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    
    is_accepted_answer = models.BooleanField(default=False)
    is_flagged = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discussion_comments"
        ordering = ["-is_accepted_answer", "-created_at"]
        indexes = [
            models.Index(fields=["thread", "-created_at"]),
            models.Index(fields=["author", "-created_at"]),
        ]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.thread.title}"
    
    # @property
    # def upvote_count(self):
    #     """Total upvotes for this comment."""
    #     return self.upvotes.count()


class ThreadUpvote(models.Model):
    """Track user upvotes on threads."""
    thread = models.ForeignKey(
        DiscussionThread, on_delete=models.CASCADE, related_name="upvotes"
    )
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="thread_upvotes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "discussion_thread_upvotes"
        unique_together = ["thread", "user"]  # One upvote per user per thread
        indexes = [
            models.Index(fields=["thread", "user"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} upvoted {self.thread.title}"


class CommentUpvote(models.Model):
    """Track user upvotes on comments."""
    comment = models.ForeignKey(
        DiscussionComment, on_delete=models.CASCADE, related_name="upvotes"
    )
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="comment_upvotes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "discussion_comment_upvotes"
        unique_together = ["comment", "user"]  # One upvote per user per comment
        indexes = [
            models.Index(fields=["comment", "user"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} upvoted comment {self.comment.id}"