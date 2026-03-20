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


class DiscussionComment(models.Model):
    """Comment on a discussion thread."""
    thread = models.ForeignKey(
        DiscussionThread, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="discussion_comments"
    )
    content = models.TextField()
    
    upvotes = models.PositiveIntegerField(default=0)
    is_accepted_answer = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discussion_comments"
        ordering = ["-is_accepted_answer", "-upvotes", "created_at"]
        indexes = [
            models.Index(fields=["thread", "-created_at"]),
            models.Index(fields=["author", "-created_at"]),
        ]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.thread.title}"
