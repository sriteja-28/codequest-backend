from django.db.models import Max
from rest_framework import serializers

from apps.problems.models import Problem

from .models import Category, Chapter, Course, Lesson


def published_lessons(course):
    """Published lessons in display order (uses prefetched rows when present)."""
    return [
        lesson
        for chapter in course.chapters.all()
        for lesson in chapter.lessons.all()
        if lesson.is_published
    ]


class CategorySerializer(serializers.ModelSerializer):
    course_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "icon", "order_index", "course_count"]

    def get_course_count(self, obj):
        annotated = getattr(obj, "published_course_count", None)
        if annotated is not None:
            return annotated
        return obj.courses.filter(is_published=True).count()


class LessonSerializer(serializers.ModelSerializer):
    is_completed = serializers.SerializerMethodField()
    problem = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            "id", "slug", "title", "content_md", "estimated_minutes",
            "order_index", "is_completed", "problem",
        ]

    def get_is_completed(self, obj):
        return obj.id in (self.context.get("completed_lesson_ids") or set())

    def get_problem(self, obj):
        if not obj.problem_id or not obj.problem.is_published:
            return None
        return {
            "slug": obj.problem.slug,
            "title": obj.problem.title,
            "number": obj.problem.number,
            "difficulty": obj.problem.difficulty,
        }


class ChapterSerializer(serializers.ModelSerializer):
    lessons = serializers.SerializerMethodField()
    lesson_count = serializers.SerializerMethodField()
    completed_count = serializers.SerializerMethodField()

    class Meta:
        model = Chapter
        fields = [
            "id", "title", "description_md", "order_index",
            "lesson_count", "completed_count", "lessons",
        ]

    def _lessons(self, obj):
        return [lesson for lesson in obj.lessons.all() if lesson.is_published]

    def get_lessons(self, obj):
        return LessonSerializer(self._lessons(obj), many=True, context=self.context).data

    def get_lesson_count(self, obj):
        return len(self._lessons(obj))

    def get_completed_count(self, obj):
        completed = self.context.get("completed_lesson_ids") or set()
        return sum(1 for lesson in self._lessons(obj) if lesson.id in completed)


class CourseListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    lesson_count = serializers.SerializerMethodField()
    completed_count = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "slug", "title", "subtitle", "description_md", "difficulty",
            "cover_icon", "estimated_minutes", "category", "lesson_count",
            "completed_count", "progress_percent", "order_index",
        ]

    def _lessons(self, obj):
        return published_lessons(obj)

    def get_lesson_count(self, obj):
        return len(self._lessons(obj))

    def get_completed_count(self, obj):
        completed = self.context.get("completed_lesson_ids") or set()
        return sum(1 for lesson in self._lessons(obj) if lesson.id in completed)

    def get_progress_percent(self, obj):
        total = self.get_lesson_count(obj)
        if not total:
            return 0.0
        return round(self.get_completed_count(obj) / total * 100, 1)


class CourseDetailSerializer(CourseListSerializer):
    chapters = serializers.SerializerMethodField()

    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + ["chapters"]

    def get_chapters(self, obj):
        return ChapterSerializer(obj.chapters.all(), many=True, context=self.context).data


# ─── Admin (apps/courses/admin_views.py) ──────────────────────────────────────

def _problem_summary(problem):
    if problem is None:
        return None
    return {
        "id": problem.id, "slug": problem.slug, "title": problem.title,
        "difficulty": problem.difficulty, "is_published": problem.is_published,
    }


class _SlugFromTitleMixin:
    """Blank slug on create -> unique slug from `slug_source`."""

    slug_source = "title"

    def validate(self, data):
        data = super().validate(data)
        if self.instance is None and not data.get("slug") and data.get(self.slug_source):
            from apps.core.slugs import unique_slug

            data["slug"] = unique_slug(self.Meta.model, data[self.slug_source])
        return data


class CategoryAdminSerializer(_SlugFromTitleMixin, serializers.ModelSerializer):
    slug_source = "name"
    course_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "icon", "order_index", "course_count"]
        extra_kwargs = {"slug": {"required": False}}


class LessonAdminSerializer(_SlugFromTitleMixin, serializers.ModelSerializer):
    problem_id = serializers.PrimaryKeyRelatedField(
        source="problem", queryset=Problem.objects.all(), allow_null=True, required=False,
    )
    problem = serializers.SerializerMethodField()
    completed_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Lesson
        fields = [
            "id", "chapter", "slug", "title", "content_md", "problem_id", "problem",
            "estimated_minutes", "is_published", "order_index", "completed_count",
        ]
        extra_kwargs = {"slug": {"required": False}}

    def get_problem(self, obj):
        return _problem_summary(obj.problem)

    def create(self, validated_data):
        if "order_index" not in self.initial_data:
            validated_data["order_index"] = _next_index(Lesson.objects.filter(chapter=validated_data["chapter"]))
        return super().create(validated_data)


def _next_index(queryset) -> int:
    """New rows go last."""
    last = queryset.aggregate(last=Max("order_index"))["last"]
    return 0 if last is None else last + 1


class ChapterAdminSerializer(serializers.ModelSerializer):
    lesson_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Chapter
        fields = ["id", "course", "title", "description_md", "order_index", "lesson_count"]

    def create(self, validated_data):
        if "order_index" not in self.initial_data:
            validated_data["order_index"] = _next_index(Chapter.objects.filter(course=validated_data["course"]))
        return super().create(validated_data)


class CourseAdminListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    chapter_count = serializers.IntegerField(read_only=True)
    lesson_count = serializers.IntegerField(read_only=True)
    learner_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = [
            "id", "slug", "title", "subtitle", "difficulty", "category", "is_published",
            "order_index", "chapter_count", "lesson_count", "learner_count", "updated_at",
        ]


class CourseAdminSerializer(_SlugFromTitleMixin, serializers.ModelSerializer):
    """Editable course plus its full outline (chapters -> lessons, unpublished included)."""

    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(), allow_null=True, required=False
    )
    category = CategorySerializer(read_only=True)
    chapters = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id", "slug", "title", "subtitle", "description_md", "difficulty", "cover_icon",
            "estimated_minutes", "is_published", "order_index", "category_id", "category",
            "chapters", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {"slug": {"required": False}}

    def get_chapters(self, obj):
        completed = self.context.get("completed_by_lesson") or {}
        chapters = []
        for chapter in obj.chapters.all():
            lessons = sorted(chapter.lessons.all(), key=lambda lesson: (lesson.order_index, lesson.id))
            chapters.append({
                "id": chapter.id,
                "title": chapter.title,
                "description_md": chapter.description_md,
                "order_index": chapter.order_index,
                "lessons": [
                    {
                        "id": lesson.id, "slug": lesson.slug, "title": lesson.title,
                        "estimated_minutes": lesson.estimated_minutes, "is_published": lesson.is_published,
                        "order_index": lesson.order_index, "problem": _problem_summary(lesson.problem),
                        "completed_count": completed.get(lesson.id, 0),
                    }
                    for lesson in lessons
                ],
            })
        return chapters


class OutlineChapterSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    lessons = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class CourseOutlineSerializer(serializers.Serializer):
    """POST .../outline/ {"chapters": [{"id": 3, "lessons": [7, 8]}, ...]} — full order."""

    chapters = OutlineChapterSerializer(many=True)
