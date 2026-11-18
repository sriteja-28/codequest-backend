from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Section(models.Model):
    """Admin-managed grouping for the catalogue (arrays, graphs, DP, ...).

    Sections are deliberately not a fixed enum: staff can add a new section from
    Django admin or the admin dashboard without a code change. `name` stays the
    stable machine key used by seeds/filters, `slug` is the URL-friendly key.
    """

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True, db_index=True, blank=True)
    display_name = models.CharField(max_length=80)
    description_md = models.TextField(blank=True)
    order_index = models.PositiveSmallIntegerField(default=0)
    icon = models.CharField(max_length=50, blank=True, help_text="Emoji or icon class")
    prerequisites = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="unlocks",
        help_text="Sections a learner should finish first (used by the roadmap).",
    )

    class Meta:
        db_table = "sections"
        ordering = ["order_index", "display_name"]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Tag(models.Model):
    class TagType(models.TextChoices):
        TOPIC = "TOPIC", "Topic"
        COMPANY = "COMPANY", "Company"

    name = models.CharField(max_length=80, unique=True, db_index=True)
    slug = models.SlugField(max_length=80, unique=True, db_index=True)
    tag_type = models.CharField(max_length=10, choices=TagType.choices, db_index=True)

    class Meta:
        db_table = "tags"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.tag_type})"


class Problem(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "EASY", "Easy"
        MEDIUM = "MEDIUM", "Medium"
        HARD = "HARD", "Hard"

    class Visibility(models.TextChoices):
        FREE = "FREE", "Free"
        PRO = "PRO", "Pro Only"

    class CompareMode(models.TextChoices):
        EXACT = "EXACT", "Exact (JSON-aware text)"
        FLOAT = "FLOAT", "Floating point with tolerance"
        UNORDERED = "UNORDERED", "Unordered JSON array"

    # Identity
    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    number = models.PositiveIntegerField(null=True, blank=True, help_text="LeetCode-style problem number")

    # Content
    statement_md = models.TextField(help_text="Problem statement in Markdown")
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, db_index=True)
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.FREE)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="problems")
    tags = models.ManyToManyField(Tag, through="ProblemTag", blank=True)

    # Complexity metadata (canonical answers)
    time_complexity_best = models.CharField(max_length=40, blank=True, help_text="e.g. O(n)")
    time_complexity_average = models.CharField(max_length=40, blank=True, help_text="e.g. O(n log n)")
    time_complexity_worst = models.CharField(max_length=40, blank=True, help_text="e.g. O(n²)")
    space_complexity = models.CharField(max_length=40, blank=True, help_text="e.g. O(1)")
    complexity_notes_md = models.TextField(blank=True)

    # Hints (newline-separated, progressive)
    hints_md = models.TextField(blank=True, help_text="Hints separated by --- on its own line")

    # Function-only judging. When set, users write only their function/class and
    # the judge generates the input parsing and result printing. Leave blank for
    # legacy stdin/stdout problems.
    function_signature = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            'Function-only judge signature, e.g. {"name": "twoSum", '
            '"params": [{"name": "nums", "type": "int[]"}, '
            '{"name": "target", "type": "int"}], "return_type": "int[]"}. '
            "Leave blank for stdin/stdout problems."
        ),
    )
    compare_mode = models.CharField(
        max_length=12,
        choices=CompareMode.choices,
        default=CompareMode.EXACT,
        help_text="Use Unordered when any valid ordering of the returned array is accepted.",
    )
    float_tolerance = models.FloatField(
        default=1e-5,
        help_text="Absolute tolerance used by the Floating point compare mode.",
    )

    # Starter code templates — shown in the editor when a user opens the problem.
    # When blank and function_signature is set, the API generates them.
    starter_code_python     = models.TextField(blank=True, default="")
    starter_code_cpp        = models.TextField(blank=True, default="")
    starter_code_java       = models.TextField(blank=True, default="")
    starter_code_javascript = models.TextField(blank=True, default="")

    # Stats (denormalized)
    total_submissions = models.PositiveIntegerField(default=0)
    accepted_submissions = models.PositiveIntegerField(default=0)

    is_published = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "problems"
        ordering = ["number", "title"]
        indexes = [
            models.Index(fields=["difficulty", "is_published"]),
            models.Index(fields=["section", "is_published"]),
        ]

    def __str__(self):
        return f"#{self.number} {self.title}" if self.number else self.title

    def clean(self):
        super().clean()
        if not self.function_signature:
            return
        from .codegen import SignatureError, validate_signature

        try:
            self.function_signature = validate_signature(self.function_signature)
        except SignatureError as exc:
            raise ValidationError({"function_signature": str(exc)}) from exc

    @property
    def acceptance_rate(self):
        if self.total_submissions == 0:
            return 0.0
        return round(self.accepted_submissions / self.total_submissions * 100, 1)

    def get_hints(self):
        """Return list of hint strings."""
        return [h.strip() for h in self.hints_md.split("---") if h.strip()]


class ProblemTag(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        db_table = "problem_tags"
        unique_together = [("problem", "tag")]


class ProblemList(models.Model):
    """Curated practice list (for example a 12-problem warm-up path)."""

    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    title = models.CharField(max_length=160)
    description_md = models.TextField(blank=True)
    is_published = models.BooleanField(default=True, db_index=True)
    order_index = models.PositiveSmallIntegerField(default=0)
    problems = models.ManyToManyField(
        Problem, through="ProblemListItem", related_name="practice_lists", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "problem_lists"
        ordering = ["order_index", "title"]

    def __str__(self):
        return self.title


class ProblemListItem(models.Model):
    problem_list = models.ForeignKey(
        ProblemList, on_delete=models.CASCADE, related_name="items"
    )
    problem = models.ForeignKey(
        Problem, on_delete=models.CASCADE, related_name="list_items"
    )
    order_index = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "problem_list_items"
        ordering = ["order_index", "id"]
        unique_together = [("problem_list", "problem")]

    def __str__(self):
        return f"{self.problem_list.slug} — {self.problem.slug}"


class Star(models.Model):
    """A user's saved problem. Toggled from the problem page."""

    user = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="stars")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="stars")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stars"
        ordering = ["-created_at"]
        unique_together = [("user", "problem")]

    def __str__(self):
        return f"{self.user_id} ★ {self.problem.slug}"


class DailyProblem(models.Model):
    """The problem featured on the home page for one UTC date."""

    date = models.DateField(unique=True, db_index=True)
    problem = models.ForeignKey(
        Problem, on_delete=models.CASCADE, related_name="daily_slots"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "daily_problems"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date}: {self.problem.slug}"


class TestCase(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="test_cases")
    input_data = models.TextField()
    expected_output = models.TextField()
    explanation = models.TextField(blank=True, help_text="Explanation shown for sample test cases")
    is_sample = models.BooleanField(default=False, help_text="Shown to the user on problem page")
    is_hidden = models.BooleanField(default=True, help_text="Used by judge but not revealed")
    order_index = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "test_cases"
        ordering = ["order_index"]

    def __str__(self):
        return f"TC#{self.pk} for {self.problem.slug}"


class Solution(models.Model):
    """Official / editorial solutions with complexity breakdown."""
    class Visibility(models.TextChoices):
        FREE = "FREE", "Free"
        PRO = "PRO", "Pro Only"

    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="solutions")
    title = models.CharField(max_length=200, help_text="e.g. 'Approach 1: HashMap'")
    approach_summary_md = models.TextField(help_text="Step-by-step explanation in Markdown")
    code_python = models.TextField(blank=True)
    code_cpp = models.TextField(blank=True)
    code_java = models.TextField(blank=True)
    code_javascript = models.TextField(blank=True)

    time_complexity = models.CharField(max_length=40, blank=True)
    space_complexity = models.CharField(max_length=40, blank=True)
    complexity_explanation_md = models.TextField(blank=True)

    is_official = models.BooleanField(default=True)
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.FREE)
    order_index = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "solutions"
        ordering = ["order_index"]

    def __str__(self):
        return f"{self.problem.slug} — {self.title}"