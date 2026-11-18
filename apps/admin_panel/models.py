from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class AdminLog(models.Model):
    """Audit trail of staff changes: admin dashboard API, Django admin and system jobs.

    Written by apps.admin_panel.audit; read-only everywhere else.
    """

    ACTION_CHOICES = [
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("APPROVE", "Approve"),
        ("REJECT", "Reject"),
        ("BAN", "Ban"),
        ("UNBAN", "Unban"),
    ]
    SOURCE_CHOICES = [
        ("api", "Admin dashboard"),
        ("django", "Django admin"),
        ("system", "System"),
    ]

    # Empty for system actions (e.g. contest finalization by the scheduler).
    admin = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="admin_logs")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=50)  # e.g. "problem", "contest", "platform_settings"
    # Text, so UUID primary keys (and Django admin's string ids) fit too.
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    # {"field": [old, new]} for updates (values shortened); empty otherwise.
    changes = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="api")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "admin_logs"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["admin", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self):
        actor = self.admin.username if self.admin else "system"
        return f"{actor} - {self.action} ({self.object_type})"


class PlatformSettings(models.Model):
    """Site-wide runtime settings: a single row (pk=1), edited in the admin
    dashboard or Django admin and served (cached) by GET /api/config/."""

    SINGLETON_PK = 1

    class AnnouncementLevel(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        SUCCESS = "success", "Success"

    site_name = models.CharField(max_length=100, default="CodeQuest")
    site_description = models.TextField(blank=True)

    announcement_text = models.CharField(
        max_length=300, blank=True, help_text="Shown in a banner on every page while set."
    )
    announcement_level = models.CharField(
        max_length=10, choices=AnnouncementLevel.choices, default=AnnouncementLevel.INFO
    )

    maintenance_mode = models.BooleanField(
        default=False,
        help_text="Shows the maintenance banner and pauses Run/Submit for everyone except admins.",
    )
    maintenance_message = models.TextField(blank=True)

    # Blank = the AI_HINTS_*_DAILY environment defaults.
    ai_hints_free_daily = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(10_000)],
        help_text="Hints per day on the Free plan. Leave blank for the server default.",
    )
    ai_hints_pro_daily = models.PositiveIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(10_000)],
        help_text="Hints per day on the Pro plan. Leave blank for the server default.",
    )

    contest_recent_days = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Ended contests are listed under 'Recent' for this many days, then move to the archive.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_settings"
        verbose_name = "platform settings"
        verbose_name_plural = "platform settings"
        constraints = [models.CheckConstraint(check=models.Q(pk=1), name="platform_settings_singleton")]

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        # There is exactly one settings row.
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Platform settings cannot be deleted; edit them instead.")

    @classmethod
    def load(cls):
        """The settings row, created with defaults on first use."""
        obj, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return obj
