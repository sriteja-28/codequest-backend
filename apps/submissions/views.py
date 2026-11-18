import hmac
import logging

from django.conf import settings
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from config.pagination import LargePagination

from .models import Submission
from .publisher import publish_submission_job
from .queue import can_accept_submission, get_queue_depth
from .serializers import (
    JudgeCallbackSerializer,
    RunCodeSerializer,
    SubmissionCreateSerializer,
    SubmissionListSerializer,
    SubmissionSerializer,
)
from .services import ACTIVE_STATUSES, InvalidCallback, apply_judge_callback, reap_stale_submissions
from .throttles import BurstThrottle, RunThrottle, SubmitThrottle

logger = logging.getLogger(__name__)

PUBLISH_FAILED_MESSAGE = "The judge queue is unavailable right now. Please try again shortly."


MAINTENANCE_MESSAGE = "CodeQuest is under maintenance: running and submitting code is paused for now."


def _enqueue(request, serializer, *, sample_run: bool):
    """Shared create + publish flow for Run and Submit."""
    from apps.core.site import maintenance

    state = maintenance()
    if state["enabled"] and not request.user.is_admin:
        message = state["message"] or MAINTENANCE_MESSAGE
        return None, Response({"detail": message, "code": "maintenance"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    allowed, reason = can_accept_submission(request.user)
    if not allowed:
        return None, Response(
            {"detail": reason, "error": reason, "queue_depth": get_queue_depth()},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    data = serializer.validated_data
    with transaction.atomic():
        contest = data.get("contest")
        if contest:
            from apps.contests.access import submission_block_reason
            from apps.contests.models import Contest
            from apps.problems.models import Problem
            from apps.users.models import User

            # Same lock order as verdict processing, before the FK insert.
            # Serializing against finalization also closes the validation/create race.
            Problem.objects.select_for_update().get(pk=data["problem"].pk)
            User.objects.select_for_update().get(pk=request.user.pk)
            contest = Contest.objects.select_for_update().get(pk=contest.pk)
            reason = submission_block_reason(contest, request.user)
            if reason:
                return None, Response({"detail": reason}, status=status.HTTP_403_FORBIDDEN)
        submission = Submission.objects.create(
            user=request.user,
            problem=data["problem"],
            language=data["language"],
            code=data["code"],
            contest=contest,
            is_sample_run=sample_run,
            status=Submission.Status.QUEUED,
        )
        if contest and submission.created_at > contest.end_at:
            submission.delete()
            return None, Response({"detail": "This contest has ended."}, status=status.HTTP_403_FORBIDDEN)

    # The row is committed before publishing, so the worker can
    # never receive a job for a submission that does not exist yet.
    published = publish_submission_job(
        submission_id=str(submission.id),
        problem_id=submission.problem_id,
        language=submission.language,
        code=submission.code,
        run_sample=sample_run,
    )
    if not published:
        submission.status = Submission.Status.INTERNAL_ERROR
        submission.error_message = PUBLISH_FAILED_MESSAGE
        submission.save(update_fields=["status", "error_message"])
        return None, Response(
            {"detail": PUBLISH_FAILED_MESSAGE, "error": PUBLISH_FAILED_MESSAGE},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    logger.info(
        "%s %s by %s (plan=%s, problem=%s, lang=%s)",
        "Run" if sample_run else "Submission", submission.id, request.user.username,
        request.user.plan, submission.problem_id, submission.language,
    )
    return submission, None


class SubmissionCreateView(APIView):
    """
    POST /api/submissions/
    Body: {problem_slug, language, code, contest?}
    Validates, stores the submission (QUEUED) and enqueues it for the judge.
    Problem counters are updated when the verdict arrives (services.finalize_submission).
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [SubmitThrottle, BurstThrottle]

    def post(self, request):
        serializer = SubmissionCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        submission, error = _enqueue(request, serializer, sample_run=False)
        if error is not None:
            return error
        return Response(
            {"submission_id": str(submission.id), "status": submission.status},
            status=status.HTTP_201_CREATED,
        )


class RunCodeView(APIView):
    """
    POST /api/submissions/run-code/
    Body: {problem_slug, language, code}
    Runs the code against the problem's *sample* test cases only. The result is
    stored as a submission with is_sample_run=True (hidden from history and
    never counted toward stats, streaks or contests).
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [RunThrottle, BurstThrottle]

    def post(self, request):
        serializer = RunCodeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        submission, error = _enqueue(request, serializer, sample_run=True)
        if error is not None:
            return error
        return Response({"submission_id": str(submission.id), "status": submission.status})


class SubmissionDetailView(generics.RetrieveAPIView):
    """
    GET /api/submissions/{id}/
    Returns submission status and per-testcase results.
    Only the submitting user or an admin can view. Hidden test data is
    withheld from non-admins.
    """

    serializer_class = SubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        qs = Submission.objects.select_related("problem", "user").prefetch_related("results__test_case")
        if user.is_admin:
            return qs
        return qs.filter(user=user)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["reveal_hidden"] = bool(self.request.user.is_admin)
        return ctx

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status in ACTIVE_STATUSES and reap_stale_submissions(submission_ids=[instance.id]):
            instance = self.get_object()
        return Response(self.get_serializer(instance).data)


class UserSubmissionListView(generics.ListAPIView):
    """
    GET /api/submissions/history/[?problem_slug=...]
    The current user's judged submissions (sample runs excluded), newest first.
    Supports ?page_size= up to 1000 for activity charts.
    """

    serializer_class = SubmissionListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = LargePagination

    def get_queryset(self):
        qs = Submission.objects.filter(user=self.request.user, is_sample_run=False)
        slug = self.kwargs.get("problem_slug") or self.request.query_params.get("problem_slug")
        if slug:
            qs = qs.filter(problem__slug=slug)
        return qs.select_related("problem").order_by("-created_at")


def _judge_key_valid(request) -> bool:
    supplied = request.headers.get("X-Judge-Api-Key", "")
    expected = settings.JUDGE_INTERNAL_API_KEY or ""
    return bool(supplied) and bool(expected) and hmac.compare_digest(supplied.encode(), expected.encode())


class _JudgeInternalView(APIView):
    """Base for judge-only endpoints: shared-key auth, no JWT, no throttling
    (all judge traffic originates from a few worker IPs)."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = []

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not _judge_key_valid(request):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Forbidden.")


class JudgeCallbackView(_JudgeInternalView):
    """
    POST /api/submissions/{id}/judge-callback/
    Internal endpoint called by the judge worker to write back results.
    Idempotent: duplicate or out-of-order callbacks return 200 with applied=false.
    """

    def post(self, request, submission_id):
        serializer = JudgeCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            outcome = apply_judge_callback(submission_id, serializer.validated_data)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except InvalidCallback as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"ok": True, **outcome})


class JudgeTestCasesView(_JudgeInternalView):
    """
    GET /api/submissions/judge/problems/{problem_id}/testcases/[?sample_only=1]
    Internal endpoint: the judge fetches test cases here (instead of needing
    direct database credentials).
    """

    def get(self, request, problem_id):
        from apps.problems.models import Problem, TestCase

        problem = Problem.objects.filter(pk=problem_id).first()
        if problem is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        sample_only = request.query_params.get("sample_only") in ("1", "true", "True")
        qs = TestCase.objects.filter(problem_id=problem_id)
        if sample_only:
            qs = qs.filter(is_sample=True)
        test_cases = [
            {
                "id": tc.id,
                "input_data": tc.input_data,
                "expected_output": tc.expected_output,
                "is_hidden": tc.is_hidden,
                "is_sample": tc.is_sample,
            }
            for tc in qs.order_by("order_index", "id")
        ]
        return Response({
            "problem_id": problem_id,
            # Function-only judging: the judge generates the harness from this.
            "function_signature": problem.function_signature or None,
            "compare_mode": problem.compare_mode,
            "float_tolerance": problem.float_tolerance,
            "test_cases": test_cases,
        })
