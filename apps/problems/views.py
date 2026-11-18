from django.db.models import Case, Count, ExpressionWrapper, F, FloatField, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_panel.audit import AuditedViewSetMixin
from apps.users.models import UserSolvedProblem
from config.pagination import LargePagination

from .filters import ProblemFilter
from .models import DailyProblem, Problem, ProblemList, Section, Solution, Star, Tag, TestCase
from .serializers import (
    AdminPracticeListSerializer,
    DailyProblemAdminSerializer,
    DailyProblemSerializer,
    PracticeListDetailSerializer,
    PracticeListSerializer,
    ProblemAdminListSerializer,
    ProblemAdminSerializer,
    ProblemDetailSerializer,
    ProblemListSerializer,
    SectionAdminSerializer,
    SectionSerializer,
    SolutionSerializer,
    TagAdminSerializer,
    TagSerializer,
    TestCaseAdminSerializer,
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


def user_can_view_problem(user, problem) -> bool:
    if problem.visibility != Problem.Visibility.PRO:
        return True
    return bool(user and user.is_authenticated and (user.is_pro or user.is_admin))


def pro_required_response(problem):
    return Response(
        {
            "detail": "This problem is available on the Pro plan.",
            "code": "pro_required",
            "slug": problem.slug,
            "title": problem.title,
            "difficulty": problem.difficulty,
            "visibility": problem.visibility,
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def problem_in_live_contest(problem) -> bool:
    from apps.contests.models import ContestProblem

    now = timezone.now()
    return ContestProblem.objects.filter(
        problem=problem, contest__start_at__lte=now, contest__end_at__gte=now,
        contest__finalized_at__isnull=True,
    ).exists()


class ProblemOrderingFilter(filters.OrderingFilter):
    """Map public ordering names to annotated columns:
    acceptance_rate → computed ratio (not a DB column; ordering on it used to 500),
    difficulty → EASY < MEDIUM < HARD (not alphabetical)."""

    aliases = {"acceptance_rate": "acceptance_rate_sort", "difficulty": "difficulty_rank"}

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if not ordering:
            return ordering
        mapped = []
        for term in ordering:
            desc = term.startswith("-")
            name = self.aliases.get(term.lstrip("-"), term.lstrip("-"))
            mapped.append(f"-{name}" if desc else name)
        return mapped


def annotate_for_ordering(qs):
    return qs.annotate(
        acceptance_rate_sort=Case(
            When(total_submissions=0, then=Value(0.0)),
            default=ExpressionWrapper(
                F("accepted_submissions") * 100.0 / F("total_submissions"), output_field=FloatField()
            ),
            output_field=FloatField(),
        ),
        difficulty_rank=Case(
            When(difficulty="EASY", then=Value(1)),
            When(difficulty="MEDIUM", then=Value(2)),
            When(difficulty="HARD", then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        ),
    )


class ProblemViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public-facing problem endpoints.
    GET /api/problems/          — paginated list with filters (?page_size= up to 1000)
    GET /api/problems/{slug}/   — full detail (PRO problems: 403 code=pro_required for non-Pro users)
    GET /api/problems/{slug}/solutions/ — editorial solutions
    POST /api/problems/{slug}/star/     — toggle the current user's bookmark
    The list includes PRO problems (with visibility="PRO") so the UI can show a lock.
    """

    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, ProblemOrderingFilter]
    filterset_class = ProblemFilter
    ordering_fields = ["number", "difficulty", "acceptance_rate", "title"]
    ordering = ["number"]
    pagination_class = LargePagination
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Problem.objects.filter(is_published=True).select_related("section").prefetch_related("tags")
        return annotate_for_ordering(qs)

    def _solved_ids(self):
        if self.request.user.is_authenticated:
            return set(
                UserSolvedProblem.objects.filter(user=self.request.user)
                .values_list("problem_id", flat=True)
            )
        return set()

    def _starred_ids(self):
        if self.request.user.is_authenticated:
            return set(
                Star.objects.filter(user=self.request.user).values_list("problem_id", flat=True)
            )
        return set()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProblemDetailSerializer
        return ProblemListSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["solved_ids"] = self._solved_ids()
        ctx["starred_ids"] = self._starred_ids()
        return ctx

    def retrieve(self, request, *args, **kwargs):
        problem = self.get_object()
        if not user_can_view_problem(request.user, problem):
            return pro_required_response(problem)
        return Response(self.get_serializer(problem).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="star",
        permission_classes=[permissions.IsAuthenticated],
    )
    def star(self, request, slug=None):
        problem = self.get_object()
        star, created = Star.objects.get_or_create(user=request.user, problem=problem)
        if not created:
            star.delete()
        return Response({"slug": problem.slug, "starred": created})

    @action(detail=True, url_path="solutions", methods=["get"])
    def solutions(self, request, slug=None):
        problem = self.get_object()
        if not user_can_view_problem(request.user, problem):
            return pro_required_response(problem)
        ctx = self.get_serializer_context()
        # Editorials stay locked while the problem is part of a running contest.
        ctx["contest_locked"] = not request.user.is_authenticated or not request.user.is_admin
        ctx["contest_locked"] = ctx["contest_locked"] and problem_in_live_contest(problem)
        serializer = SolutionSerializer(problem.solutions.all(), many=True, context=ctx)
        return Response(serializer.data)


class SectionListView(generics.ListAPIView):
    serializer_class = SectionSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = LargePagination

    def get_queryset(self):
        return (
            Section.objects.annotate(
                published_problem_count=Count(
                    "problems", filter=Q(problems__is_published=True), distinct=True
                )
            )
            .prefetch_related("prerequisites")
            .order_by("order_index", "display_name")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        user = self.request.user
        if user.is_authenticated:
            rows = (
                UserSolvedProblem.objects.filter(
                    user=user, problem__is_published=True
                )
                .values("problem__section_id")
                .annotate(count=Count("id"))
            )
            ctx["solved_by_section"] = {
                row["problem__section_id"]: row["count"] for row in rows
            }
        return ctx


class PracticeListViewSet(viewsets.ReadOnlyModelViewSet):
    """Curated practice lists (NeetCode-style study paths)."""

    lookup_field = "slug"
    permission_classes = [permissions.AllowAny]
    pagination_class = LargePagination

    def get_queryset(self):
        return (
            ProblemList.objects.filter(is_published=True)
            .prefetch_related("items__problem__section", "items__problem__tags")
            .order_by("order_index", "title")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PracticeListDetailSerializer
        return PracticeListSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.user.is_authenticated:
            ctx["solved_ids"] = set(
                UserSolvedProblem.objects.filter(user=self.request.user)
                .values_list("problem_id", flat=True)
            )
        return ctx


class DailyProblemView(APIView):
    """Today's featured problem. Auto-picks one when staff haven't scheduled it."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        today = timezone.now().date()
        slot = DailyProblem.objects.select_related("problem").filter(date=today).first()
        if slot is None:
            candidates = Problem.objects.filter(is_published=True).order_by("id")
            count = candidates.count()
            if not count:
                return Response(
                    {"detail": "No published problems yet."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            picked = candidates[today.toordinal() % count]
            slot, _ = DailyProblem.objects.get_or_create(
                date=today, defaults={"problem": picked}
            )
            slot = DailyProblem.objects.select_related("problem").get(pk=slot.pk)

        ctx = {"request": request}
        if request.user.is_authenticated:
            ctx["solved_ids"] = set(
                UserSolvedProblem.objects.filter(user=request.user)
                .values_list("problem_id", flat=True)
            )
        return Response(DailyProblemSerializer(slot, context=ctx).data)


class StarredProblemsView(generics.ListAPIView):
    serializer_class = ProblemListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = LargePagination

    def get_queryset(self):
        return (
            Problem.objects.filter(stars__user=self.request.user, is_published=True)
            .select_related("section")
            .prefetch_related("tags")
            .order_by("-stars__created_at")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["solved_ids"] = set(
            UserSolvedProblem.objects.filter(user=self.request.user)
            .values_list("problem_id", flat=True)
        )
        return ctx


class TagListView(generics.ListAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = LargePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["tag_type"]
    search_fields = ["name"]


# ─────────────────────────────────────────────
# Admin CRUD ViewSets (every change is audited, see apps.admin_panel.audit)
# ─────────────────────────────────────────────

class ProblemInUse(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "in_use"


class AdminProblemViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    """
    /api/problems/admin/problems/          light rows; ?search= ?difficulty= ?is_published=
                                           ?visibility= ?section=<id> ?ordering=
    /api/problems/admin/problems/{slug}/   full editable problem
    Deleting a problem with submissions or contest entries answers 409 in_use:
    unpublish it instead (its history stays intact).
    """

    permission_classes = [IsAdminUser]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, ProblemOrderingFilter]
    filterset_fields = ["difficulty", "is_published", "visibility", "section"]
    search_fields = ["title", "slug"]
    ordering_fields = ["number", "title", "difficulty", "acceptance_rate", "total_submissions", "updated_at"]
    ordering = ["number"]
    pagination_class = LargePagination

    def get_queryset(self):
        qs = Problem.objects.select_related("section").prefetch_related("tags")
        if self.action == "list":
            qs = annotate_for_ordering(qs).annotate(test_case_total=Count("test_cases", distinct=True))
        return qs

    def get_serializer_class(self):
        return ProblemAdminListSerializer if self.action == "list" else ProblemAdminSerializer

    def perform_destroy(self, instance):
        from apps.contests.models import ContestProblem

        submissions = instance.submissions.count()
        contests = ContestProblem.objects.filter(problem=instance).count()
        if submissions or contests:
            raise ProblemInUse({
                "detail": (
                    f"'{instance.title}' has {submissions} submission(s) and appears in {contests} contest(s). "
                    "Unpublish it instead of deleting it."
                ),
                "code": "in_use",
                "submissions": submissions,
                "contests": contests,
            })
        super().perform_destroy(instance)


class _ProblemChildViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    """Rows that belong to the problem in the URL (/admin/problems/<slug>/...)."""

    permission_classes = [IsAdminUser]
    pagination_class = LargePagination
    model = None

    def problem(self):
        if not hasattr(self, "_problem"):
            self._problem = get_object_or_404(Problem, slug=self.kwargs["problem_slug"])
        return self._problem

    def get_queryset(self):
        return self.model.objects.filter(problem=self.problem()).order_by("order_index", "id")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["problem"] = self.problem()
        return ctx

    def create_kwargs(self):
        return {"problem": self.problem()}


class AdminTestCaseViewSet(_ProblemChildViewSet):
    serializer_class = TestCaseAdminSerializer
    model = TestCase


class AdminSolutionViewSet(_ProblemChildViewSet):
    serializer_class = SolutionSerializer
    model = Solution


class AdminSectionViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = SectionAdminSerializer
    permission_classes = [IsAdminUser]
    pagination_class = LargePagination

    def get_queryset(self):
        return (
            Section.objects.annotate(problem_count=Count("problems", distinct=True))
            .prefetch_related("prerequisites")
            .order_by("order_index", "display_name")
        )


class AdminPracticeListViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = AdminPracticeListSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "slug"
    pagination_class = LargePagination

    def get_queryset(self):
        return ProblemList.objects.prefetch_related("items__problem").order_by("order_index", "title")

    def audit_snapshot(self, instance):
        data = super().audit_snapshot(instance)
        data["problems"] = list(instance.items.order_by("order_index", "id").values_list("problem_id", flat=True))
        return data


class AdminDailyProblemViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    """Scheduled daily problems, newest date first; ?from=YYYY-MM-DD limits to that date onward."""

    serializer_class = DailyProblemAdminSerializer
    permission_classes = [IsAdminUser]
    pagination_class = LargePagination

    def get_queryset(self):
        qs = DailyProblem.objects.select_related("problem__section").prefetch_related("problem__tags").order_by("-date")
        start = self.request.query_params.get("from")
        if start:
            from datetime import date
            from rest_framework.exceptions import ValidationError
            try:
                start = date.fromisoformat(start)
            except ValueError:
                raise ValidationError({"from": "Use a YYYY-MM-DD date."}) from None
            qs = qs.filter(date__gte=start)
        return qs


class AdminTagViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TagAdminSerializer
    permission_classes = [IsAdminUser]
    pagination_class = LargePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["tag_type"]
    search_fields = ["name"]

    def get_queryset(self):
        return Tag.objects.annotate(problem_count=Count("problem", distinct=True)).order_by("name")
