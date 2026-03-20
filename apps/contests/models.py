from django.db import models
from django.utils import timezone


class Contest(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    description_md = models.TextField(blank=True)
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField(db_index=True)
    is_public = models.BooleanField(default=True)
    is_rated = models.BooleanField(default=False)
    max_participants = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contests"
        ordering = ["-start_at"]

    def __str__(self):
        return self.name

    @property
    def status(self):
        now = timezone.now()
        if now < self.start_at:
            return "upcoming"
        if now > self.end_at:
            return "ended"
        return "live"

    @property
    def duration_minutes(self):
        return int((self.end_at - self.start_at).total_seconds() / 60)


class ContestProblem(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="contest_problems")
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE)
    order_index = models.PositiveSmallIntegerField(default=0)
    score = models.PositiveIntegerField(default=100, help_text="Max score for this problem")

    class Meta:
        db_table = "contest_problems"
        ordering = ["order_index"]
        unique_together = [("contest", "problem")]

    def __str__(self):
        return f"{self.contest.slug} — {self.problem.slug}"


class ContestParticipant(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="contest_participations")
    registered_at = models.DateTimeField(auto_now_add=True)
    is_disqualified = models.BooleanField(default=False)
    disqualified_reason = models.TextField(blank=True)
    final_score = models.IntegerField(default=0)
    rank = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "contest_participants"
        unique_together = [("contest", "user")]
        ordering = ["rank", "-final_score"]

    def __str__(self):
        return f"{self.user.username} @ {self.contest.slug}"