from django.db import models


class AIInteraction(models.Model):
    """Track AI hint and chat interactions for usage tracking."""
    INTERACTION_TYPE_HINT = "HINT"
    INTERACTION_TYPE_CHAT = "CHAT"
    INTERACTION_CHOICES = [
        (INTERACTION_TYPE_HINT, "Hint"),
        (INTERACTION_TYPE_CHAT, "Chat"),
    ]
    
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="ai_interactions"
    )
    problem = models.ForeignKey(
        "problems.Problem", on_delete=models.CASCADE, null=True, blank=True
    )
    
    interaction_type = models.CharField(
        max_length=20, choices=INTERACTION_CHOICES
    )
    query = models.TextField()
    response = models.TextField()
    tokens_used = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ai_interactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["interaction_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.interaction_type}"
