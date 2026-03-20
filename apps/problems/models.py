from django.db import models
from django.utils.text import slugify


class Section(models.Model):
    """Top-level grouping: Arrays, Graphs, DP, etc."""
    class Name(models.TextChoices):
        ARRAY = "ARRAY", "Array"
        STRING = "STRING", "String"
        LINKED_LIST = "LINKED_LIST", "Linked List"
        TREE = "TREE", "Tree"
        GRAPH = "GRAPH", "Graph"
        DYNAMIC_PROGRAMMING = "DP", "Dynamic Programming"
        BACKTRACKING = "BACKTRACKING", "Backtracking"
        BINARY_SEARCH = "BINARY_SEARCH", "Binary Search"
        HEAP = "HEAP", "Heap / Priority Queue"
        STACK = "STACK", "Stack"
        QUEUE = "QUEUE", "Queue"
        HASH_MAP = "HASH_MAP", "Hash Map / Set"
        TWO_POINTERS = "TWO_POINTERS", "Two Pointers"
        SLIDING_WINDOW = "SLIDING_WINDOW", "Sliding Window"
        BIT_MANIPULATION = "BIT_MANIPULATION", "Bit Manipulation"
        MATH = "MATH", "Math & Geometry"
        GREEDY = "GREEDY", "Greedy"
        INTERVALS = "INTERVALS", "Intervals"
        OTHER = "OTHER", "Other"

    name = models.CharField(max_length=30, choices=Name.choices, unique=True)
    display_name = models.CharField(max_length=60)
    order_index = models.PositiveSmallIntegerField(default=0)
    icon = models.CharField(max_length=50, blank=True, help_text="Emoji or icon class")

    class Meta:
        db_table = "sections"
        ordering = ["order_index"]

    def __str__(self):
        return self.display_name


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

    # Starter code templates — shown in the editor when a user opens the problem.
    # Must include stdin reading boilerplate to work with the judge.
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