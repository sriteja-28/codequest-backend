from django.db import models


class AdminLog(models.Model):
    """Audit log for admin actions."""
    ACTION_CHOICES = [
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("APPROVE", "Approve"),
        ("REJECT", "Reject"),
        ("BAN", "Ban"),
        ("UNBAN", "Unban"),
    ]
    
    admin = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, related_name="admin_logs")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=50)  # e.g., "user", "problem", "comment"
    object_id = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "admin_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["admin", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.admin.username} - {self.action} ({self.object_type})"


class PlatformSettings(models.Model):
    """Global platform settings."""
    site_name = models.CharField(max_length=100, default="CodeQuest")
    site_description = models.TextField(blank=True)
    
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    
    max_problem_limit = models.PositiveIntegerField(default=500)
    max_submission_size_kb = models.PositiveIntegerField(default=1024)
    
    ai_hints_free_daily = models.PositiveIntegerField(default=20)
    ai_chat_free_daily = models.PositiveIntegerField(default=20)
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_settings"

    def __str__(self):
        return self.site_name
