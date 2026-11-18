from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone
from datetime import timedelta



class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra):
        extra.setdefault("role", User.Role.ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, username, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        USER = "USER", "User"
        MODERATOR = "MODERATOR", "Moderator"
        ADMIN = "ADMIN", "Admin"

    class Plan(models.TextChoices):
        FREE = "FREE", "Free"
        PRO = "PRO", "Pro"

    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=50, unique=True, db_index=True)
    display_name = models.CharField(max_length=100, blank=True)
    avatar_url = models.URLField(blank=True)
    bio = models.TextField(blank=True)

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.USER, db_index=True
    )
    plan = models.CharField(
        max_length=10, choices=Plan.choices, default=Plan.FREE, db_index=True
    )
    plan_expires_at = models.DateTimeField(null=True, blank=True)

    # Stats (denormalized for performance)
    problems_solved = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    # adding best streak tracking
    best_streak = models.PositiveIntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_banned = models.BooleanField(default=False)
    banned_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["plan", "is_active"]),
            models.Index(fields=["role", "is_active"]),
        ]

    def __str__(self):
        return f"{self.username} ({self.email})"

    @property
    def is_pro(self):
        if self.plan != self.Plan.PRO:
            return False
        if self.plan_expires_at and self.plan_expires_at < timezone.now():
            return False
        return True

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    def get_ai_hint_limit(self):
        # Runtime quota (admin settings), falling back to AI_HINTS_*_DAILY.
        from apps.core.site import hint_quota

        return hint_quota(pro=self.is_pro)

    def get_ai_chat_limit(self):
        from django.conf import settings

        return (
            settings.AI_CHAT_PRO_DAILY if self.is_pro else settings.AI_CHAT_FREE_DAILY
        )



    def update_streak(self):
        today = timezone.now().date()

        # first solve ever
        if not self.last_active_date:
            self.current_streak = 1

        # solved yesterday → increment streak
        elif self.last_active_date == today - timedelta(days=1):
            self.current_streak += 1

        # solved today again → do nothing
        elif self.last_active_date == today:
            return

        # gap → reset streak
        else:
            self.current_streak = 1

        # updating best streak
        if self.current_streak > self.best_streak:
            self.best_streak = self.current_streak

        self.last_active_date = today
        self.save(update_fields=["current_streak", "best_streak", "last_active_date"])


class SocialIdentity(models.Model):
    """
    A Google or GitHub account that signs in as `user`.

    Matched on the provider's permanent account id (`subject`: Google's `sub`,
    GitHub's numeric user id), never on email, which can change or be reused.
    A user has at most one identity per provider.
    """

    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"
        GITHUB = "github", "GitHub"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="identities")
    provider = models.CharField(max_length=16, choices=Provider.choices)
    subject = models.CharField(max_length=255)
    # As reported by the provider at the last sign-in (informational only).
    email = models.EmailField(blank=True)
    email_verified = models.BooleanField(default=False)
    display_name = models.CharField(max_length=150, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user_social_identities"
        ordering = ["provider"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "subject"], name="uniq_identity_provider_subject"),
            models.UniqueConstraint(fields=["user", "provider"], name="uniq_identity_user_provider"),
        ]

    def __str__(self):
        return f"{self.get_provider_display()} sign-in for user {self.user_id}"


class UserSolvedProblem(models.Model):
    """Track which problems a user has solved (for dashboard / stats)."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="solved_problems"
    )
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE)
    solved_at = models.DateTimeField(auto_now_add=True)
    best_runtime_ms = models.PositiveIntegerField(null=True, blank=True)
    best_memory_kb = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "user_solved_problems"
        unique_together = [("user", "problem")]


class UserDailyActivity(models.Model):
    """Per-day attempt counters used by the home/profile heatmap.

    A row is written for every judged (non-sample, non-infrastructure) attempt,
    accepted or not. `date` is UTC, matching the streak calculation.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="daily_activity"
    )
    date = models.DateField(db_index=True)
    submissions = models.PositiveIntegerField(default=0)
    accepted = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "user_daily_activity"
        ordering = ["-date"]
        unique_together = [("user", "date")]
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.user_id} {self.date}: {self.submissions}/{self.accepted}"
