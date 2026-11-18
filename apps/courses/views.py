from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import filters, generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.features import FeatureEnabled
from config.pagination import LargePagination

from .models import Category, Course, Lesson, LessonProgress
from .serializers import CategorySerializer, CourseDetailSerializer, CourseListSerializer


def completed_lesson_ids(user):
    if not user or not user.is_authenticated:
        return set()
    return set(
        LessonProgress.objects.filter(user=user).values_list("lesson_id", flat=True)
    )


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    permission_classes = [FeatureEnabled("courses")]
    pagination_class = LargePagination

    def get_queryset(self):
        return Category.objects.annotate(
            published_course_count=Count(
                "courses", filter=Q(courses__is_published=True), distinct=True
            )
        ).order_by("order_index", "name")


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """Published course catalog. Detail includes chapters, lessons and progress."""

    lookup_field = "slug"
    permission_classes = [FeatureEnabled("courses")]
    pagination_class = LargePagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["title", "subtitle", "description_md"]

    def get_queryset(self):
        qs = (
            Course.objects.filter(is_published=True)
            .select_related("category")
            .prefetch_related("chapters__lessons__problem")
            .order_by("order_index", "title")
        )
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__slug=category)
        difficulty = self.request.query_params.get("difficulty")
        if difficulty:
            qs = qs.filter(difficulty=difficulty.upper())
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CourseDetailSerializer
        return CourseListSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["completed_lesson_ids"] = completed_lesson_ids(self.request.user)
        return ctx


class LessonCompleteView(APIView):
    """POST marks a lesson complete, DELETE clears it. Auth required."""

    permission_classes = [permissions.IsAuthenticated, FeatureEnabled("courses")]

    def _lesson(self, pk):
        return get_object_or_404(
            Lesson.objects.select_related("chapter__course"),
            pk=pk,
            is_published=True,
            chapter__course__is_published=True,
        )

    def _payload(self, request, lesson, completed):
        course = lesson.chapter.course
        lesson_ids = Lesson.objects.filter(
            chapter__course=course, is_published=True
        ).values_list("id", flat=True)
        total = len(lesson_ids)
        done = LessonProgress.objects.filter(
            user=request.user, lesson_id__in=lesson_ids
        ).count()
        return {
            "lesson_id": lesson.id,
            "completed": completed,
            "course": {
                "slug": course.slug,
                "lesson_count": total,
                "completed_count": done,
                "progress_percent": round(done / total * 100, 1) if total else 0.0,
            },
        }

    def post(self, request, pk):
        lesson = self._lesson(pk)
        LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)
        return Response(self._payload(request, lesson, True), status=status.HTTP_200_OK)

    def delete(self, request, pk):
        lesson = self._lesson(pk)
        LessonProgress.objects.filter(user=request.user, lesson=lesson).delete()
        return Response(self._payload(request, lesson, False), status=status.HTTP_200_OK)
