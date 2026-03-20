from rest_framework import viewsets, generics, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.users.models import UserSolvedProblem
from .models import Problem, Section, Tag, TestCase, Solution
from .serializers import (
    ProblemListSerializer, ProblemDetailSerializer, ProblemAdminSerializer,
    SectionSerializer, TagSerializer, TestCaseAdminSerializer, SolutionSerializer,
)
from .filters import ProblemFilter


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class ProblemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public-facing problem endpoints.
    GET /api/problems/          — paginated list with filters
    GET /api/problems/{slug}/   — full detail
    GET /api/problems/{slug}/solutions/ — editorial solutions
    """
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ProblemFilter
    ordering_fields = ["number", "difficulty", "acceptance_rate", "title"]
    ordering = ["number"]

    def get_queryset(self):
        qs = Problem.objects.filter(is_published=True).select_related("section").prefetch_related("tags")
        # PRO-only problems hidden from free users unless they're pro
        if self.request.user.is_authenticated and self.request.user.is_pro:
            return qs
        return qs  # For now show all; individual solution content gating is in serializer

    def _solved_ids(self):
        if self.request.user.is_authenticated:
            return set(
                UserSolvedProblem.objects.filter(user=self.request.user)
                .values_list("problem_id", flat=True)
            )
        return set()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProblemDetailSerializer
        return ProblemListSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["solved_ids"] = self._solved_ids()
        return ctx

    @action(detail=True, url_path="solutions", methods=["get"])
    def solutions(self, request, slug=None):
        problem = self.get_object()
        qs = problem.solutions.all()
        serializer = SolutionSerializer(qs, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


class SectionListView(generics.ListAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [permissions.AllowAny]


class TagListView(generics.ListAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["tag_type"]
    search_fields = ["name"]


# ─────────────────────────────────────────────
# Admin CRUD ViewSets
# ─────────────────────────────────────────────

class AdminProblemViewSet(viewsets.ModelViewSet):
    queryset = Problem.objects.all().select_related("section").prefetch_related("tags")
    serializer_class = ProblemAdminSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "slug"]
    ordering_fields = ["number", "title", "difficulty", "created_at"]


class AdminTestCaseViewSet(viewsets.ModelViewSet):
    serializer_class = TestCaseAdminSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return TestCase.objects.filter(problem__slug=self.kwargs["problem_slug"])

    def perform_create(self, serializer):
        problem = Problem.objects.get(slug=self.kwargs["problem_slug"])
        serializer.save(problem=problem)


class AdminSectionViewSet(viewsets.ModelViewSet):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [IsAdminUser]


class AdminTagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["tag_type"]
    search_fields = ["name"]


class AdminSolutionViewSet(viewsets.ModelViewSet):
    serializer_class = SolutionSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return Solution.objects.filter(problem__slug=self.kwargs["problem_slug"])

    def perform_create(self, serializer):
        problem = Problem.objects.get(slug=self.kwargs["problem_slug"])
        serializer.save(problem=problem)