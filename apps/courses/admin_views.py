"""Course administration API (admin only; every change is audited).

    /api/courses/admin/categories/               CRUD (by id)
    /api/courses/admin/courses/                  CRUD (by slug); detail = editable course + outline
    /api/courses/admin/courses/{slug}/outline/   POST the full chapter/lesson order (moves lessons too)
    /api/courses/admin/chapters/                 CRUD (?course=<slug>)
    /api/courses/admin/lessons/                  CRUD (?chapter=<id> | ?course=<slug>)

Deleting a course, chapter or lesson that learners have completed answers 409
in_use with the number of completions unless ?force=true (they are deleted too).
"""

from django.db import transaction
from django.db.models import Count, Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from apps.admin_panel.audit import AuditedViewSetMixin, record
from config.pagination import LargePagination

from .models import Category, Chapter, Course, Lesson, LessonProgress
from .serializers import (
    CategoryAdminSerializer,
    ChapterAdminSerializer,
    CourseAdminListSerializer,
    CourseAdminSerializer,
    CourseOutlineSerializer,
    LessonAdminSerializer,
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class InUse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "in_use"


class _ProgressGuardMixin:
    """Refuse to delete rows learners have completed unless ?force=true."""

    def progress_count(self, instance) -> int:
        raise NotImplementedError

    def perform_destroy(self, instance):
        count = self.progress_count(instance)
        forced = self.request.query_params.get("force", "").lower() in ("1", "true", "yes")
        if count and not forced:
            raise InUse({
                "detail": f"Learners completed lessons here {count} time(s); those records would be deleted. "
                          "Unpublish it instead, or confirm to delete anyway.",
                "code": "in_use",
                "completions": count,
            })
        super().perform_destroy(instance)


class AdminCategoryViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CategoryAdminSerializer
    permission_classes = [IsAdminUser]
    pagination_class = LargePagination

    def get_queryset(self):
        return Category.objects.annotate(course_count=Count("courses", distinct=True)).order_by("order_index", "name")


class AdminCourseViewSet(_ProgressGuardMixin, AuditedViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    lookup_field = "slug"
    pagination_class = LargePagination

    def get_queryset(self):
        qs = Course.objects.select_related("category")
        if self.action == "list":
            qs = qs.annotate(
                chapter_count=Count("chapters", distinct=True),
                lesson_count=Count("chapters__lessons", distinct=True),
                learner_count=Count("chapters__lessons__progress_records__user", distinct=True),
            )
            params = self.request.query_params
            search = params.get("search", "").strip()
            if search:
                qs = qs.filter(Q(title__icontains=search) | Q(slug__icontains=search))
            if params.get("category"):
                qs = qs.filter(category__slug=params["category"])
        else:
            qs = qs.prefetch_related("chapters__lessons__problem")
        return qs.order_by("order_index", "title")

    def get_serializer_class(self):
        return CourseAdminListSerializer if self.action == "list" else CourseAdminSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        slug = self.kwargs.get("slug")
        if slug:
            rows = (
                LessonProgress.objects.filter(lesson__chapter__course__slug=slug)
                .values("lesson_id").annotate(total=Count("id"))
            )
            ctx["completed_by_lesson"] = {row["lesson_id"]: row["total"] for row in rows}
        return ctx

    def progress_count(self, instance):
        return LessonProgress.objects.filter(lesson__chapter__course=instance).count()

    @action(detail=True, methods=["post"])
    def outline(self, request, slug=None):
        course = self.get_object()
        serializer = CourseOutlineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entries = serializer.validated_data["chapters"]
        chapter_ids = [entry["id"] for entry in entries]
        lesson_ids = [lesson_id for entry in entries for lesson_id in entry["lessons"]]
        own_chapters = set(course.chapters.values_list("id", flat=True))
        own_lessons = set(Lesson.objects.filter(chapter__course=course).values_list("id", flat=True))
        if len(chapter_ids) != len(own_chapters) or set(chapter_ids) != own_chapters:
            return Response({"chapters": ["List every chapter of this course exactly once."]},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(lesson_ids) != len(own_lessons) or set(lesson_ids) != own_lessons:
            return Response({"chapters": ["List every lesson of this course exactly once."]},
                            status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            for chapter_index, entry in enumerate(entries):
                Chapter.objects.filter(pk=entry["id"]).update(order_index=chapter_index)
                for lesson_index, lesson_id in enumerate(entry["lessons"]):
                    Lesson.objects.filter(pk=lesson_id).update(chapter_id=entry["id"], order_index=lesson_index)
            record(actor=request.user, action="UPDATE", obj=course,
                   description=f"Reordered the outline of course '{course}'")
        fresh = self.get_queryset().get(pk=course.pk)
        return Response(CourseAdminSerializer(fresh, context=self.get_serializer_context()).data)


class AdminChapterViewSet(_ProgressGuardMixin, AuditedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ChapterAdminSerializer
    permission_classes = [IsAdminUser]
    pagination_class = LargePagination

    def get_queryset(self):
        qs = (
            Chapter.objects.select_related("course")
            .annotate(lesson_count=Count("lessons", distinct=True))
            .order_by("course_id", "order_index", "id")
        )
        course = self.request.query_params.get("course")
        return qs.filter(course__slug=course) if course else qs

    def progress_count(self, instance):
        return LessonProgress.objects.filter(lesson__chapter=instance).count()


class AdminLessonViewSet(_ProgressGuardMixin, AuditedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = LessonAdminSerializer
    permission_classes = [IsAdminUser]
    pagination_class = LargePagination

    def get_queryset(self):
        qs = (
            Lesson.objects.select_related("chapter__course", "problem")
            .annotate(completed_count=Count("progress_records", distinct=True))
            .order_by("chapter__course_id", "chapter__order_index", "order_index", "id")
        )
        params = self.request.query_params
        if params.get("chapter", "").isdigit():
            qs = qs.filter(chapter_id=int(params["chapter"]))
        if params.get("course"):
            qs = qs.filter(chapter__course__slug=params["course"])
        return qs

    def progress_count(self, instance):
        return instance.progress_records.count()
