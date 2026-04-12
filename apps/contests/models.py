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

        if self.start_at is None:
            return "draft"

        if self.end_at is None:
            if now < self.start_at:
                return "upcoming"
            return "live"

        if now < self.start_at:
            return "upcoming"

        if now > self.end_at:
            return "ended"

        return "live"

    @property
    def duration_minutes(self):
        return int((self.end_at - self.start_at).total_seconds() / 60)


class ContestProblem(models.Model):
    contest = models.ForeignKey(
        Contest, on_delete=models.CASCADE, related_name="contest_problems"
    )
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE)
    order_index = models.PositiveSmallIntegerField(default=0)
    score = models.PositiveIntegerField(
        default=100, help_text="Max score for this problem"
    )

    class Meta:
        db_table = "contest_problems"
        ordering = ["order_index"]
        unique_together = [("contest", "problem")]

    def __str__(self):
        return f"{self.contest.slug} — {self.problem.slug}"


class ContestParticipant(models.Model):
    contest = models.ForeignKey(
        Contest, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="contest_participations"
    )
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


# tracks per-problem progress per user in a contest
class ContestSubmissionStat(models.Model):
    """Tracks each participant's status on each problem."""

    participant = models.ForeignKey(
        ContestParticipant, on_delete=models.CASCADE, related_name="problem_stats"
    )
    contest_problem = models.ForeignKey(
        ContestProblem, on_delete=models.CASCADE, related_name="stats"
    )
    is_solved = models.BooleanField(default=False)
    wrong_attempts = models.IntegerField(default=0)
    solve_time_minutes = models.IntegerField(
        null=True, blank=True
    )  # minutes from contest start
    score_awarded = models.IntegerField(default=0)
    first_solved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "contest_submission_stats"
        unique_together = [("participant", "contest_problem")]
