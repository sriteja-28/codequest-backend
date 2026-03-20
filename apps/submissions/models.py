import uuid
from django.db import models


class Submission(models.Model):
    class Language(models.TextChoices):
        PYTHON = "python", "Python 3"
        CPP = "cpp", "C++ 17"
        JAVA = "java", "Java 17"
        JAVASCRIPT = "javascript", "JavaScript (Node)"

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RUNNING = "RUNNING", "Running"
        ACCEPTED = "ACCEPTED", "Accepted"
        WRONG_ANSWER = "WRONG_ANSWER", "Wrong Answer"
        RUNTIME_ERROR = "RUNTIME_ERROR", "Runtime Error"
        TIME_LIMIT = "TIME_LIMIT", "Time Limit Exceeded"
        MEMORY_LIMIT = "MEMORY_LIMIT", "Memory Limit Exceeded"
        COMPILE_ERROR = "COMPILE_ERROR", "Compile Error"
        INTERNAL_ERROR = "INTERNAL_ERROR", "Internal Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="submissions")
    problem = models.ForeignKey("problems.Problem", on_delete=models.CASCADE, related_name="submissions")
    contest = models.ForeignKey(
        "contests.Contest", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="submissions"
    )

    language = models.CharField(max_length=20, choices=Language.choices)
    code = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)

    # Results (populated by judge)
    runtime_ms = models.PositiveIntegerField(null=True, blank=True)
    memory_kb = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Judge worker tracking
    judge_started_at = models.DateTimeField(null=True, blank=True)
    judge_finished_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "submissions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "problem", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["problem", "status"]),
        ]

    def __str__(self):
        return f"Sub {self.id} — {self.user.username} — {self.problem.slug} — {self.status}"


class SubmissionResult(models.Model):
    """Per-testcase result from the judge."""
    class Status(models.TextChoices):
        ACCEPTED = "ACCEPTED", "Accepted"
        WRONG_ANSWER = "WRONG_ANSWER", "Wrong Answer"
        RUNTIME_ERROR = "RUNTIME_ERROR", "Runtime Error"
        TIME_LIMIT = "TIME_LIMIT", "Time Limit Exceeded"
        MEMORY_LIMIT = "MEMORY_LIMIT", "Memory Limit Exceeded"

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="results")
    test_case = models.ForeignKey("problems.TestCase", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices)
    actual_output = models.TextField(blank=True)
    expected_output = models.TextField(blank=True)
    error_output = models.TextField(blank=True)
    time_ms = models.PositiveIntegerField(null=True, blank=True)
    memory_kb = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "submission_results"
        ordering = ["test_case__order_index"]

    def __str__(self):
        return f"Result sub={self.submission_id} tc={self.test_case_id} → {self.status}"