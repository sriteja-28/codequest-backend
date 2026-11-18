from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """Top-level course grouping shown on the courses catalog."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True, db_index=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    order_index = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "course_categories"
        ordering = ["order_index", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Course(models.Model):
    class Difficulty(models.TextChoices):
        BEGINNER = "BEGINNER", "Beginner"
        INTERMEDIATE = "INTERMEDIATE", "Intermediate"
        ADVANCED = "ADVANCED", "Advanced"

    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="courses"
    )
    slug = models.SlugField(max_length=140, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=240, blank=True)
    description_md = models.TextField(blank=True)
    difficulty = models.CharField(
        max_length=20, choices=Difficulty.choices, default=Difficulty.BEGINNER
    )
    cover_icon = models.CharField(max_length=50, blank=True)
    estimated_minutes = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True, db_index=True)
    order_index = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "courses"
        ordering = ["order_index", "title"]

    def __str__(self):
        return self.title


class Chapter(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="chapters")
    title = models.CharField(max_length=200)
    description_md = models.TextField(blank=True)
    order_index = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "course_chapters"
        ordering = ["order_index", "id"]
        unique_together = [("course", "title")]

    def __str__(self):
        return f"{self.course.title} — {self.title}"


class Lesson(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="lessons")
    slug = models.SlugField(max_length=160, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    content_md = models.TextField(blank=True)
    problem = models.ForeignKey(
        "problems.Problem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="course_lessons",
    )
    estimated_minutes = models.PositiveSmallIntegerField(default=10)
    is_published = models.BooleanField(default=True, db_index=True)
    order_index = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "course_lessons"
        ordering = ["order_index", "id"]

    def __str__(self):
        return self.title


class LessonProgress(models.Model):
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="lesson_progress"
    )
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="progress_records"
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "course_lesson_progress"
        ordering = ["-completed_at"]
        unique_together = [("user", "lesson")]

    def __str__(self):
        return f"{self.user_id} ✓ {self.lesson.slug}"
