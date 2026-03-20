import logging
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import UserSolvedProblem
from .models import Submission
from .serializers import (
    SubmissionSerializer, SubmissionCreateSerializer, SubmissionListSerializer
)
from .publisher import publish_submission_job

logger = logging.getLogger(__name__)


class SubmissionCreateView(APIView):
    """
    POST /api/submissions/
    Create a submission, enqueue it to RabbitMQ, return the submission ID.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        submission = Submission.objects.create(
            user=request.user,
            status=Submission.Status.QUEUED,
            **serializer.validated_data,
        )

        # Update problem submission counter
        submission.problem.total_submissions += 1
        submission.problem.save(update_fields=["total_submissions"])

        # Enqueue to RabbitMQ
        published = publish_submission_job(
            submission_id=str(submission.id),
            problem_id=submission.problem.id,
            language=submission.language,
            code=submission.code,
        )

        if not published:
            submission.status = Submission.Status.INTERNAL_ERROR
            submission.save(update_fields=["status"])
            return Response(
                {"detail": "Failed to enqueue submission. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"submission_id": str(submission.id), "status": submission.status},
            status=status.HTTP_201_CREATED,
        )


class SubmissionDetailView(generics.RetrieveAPIView):
    """
    GET /api/submissions/{id}/
    Returns submission status and per-testcase results.
    Only the submitting user or an admin can view.
    """
    serializer_class = SubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Submission.objects.all()
        return Submission.objects.filter(user=user)


class UserSubmissionListView(generics.ListAPIView):
    """
    GET /api/submissions/          — all submissions for current user
    GET /api/problems/{slug}/submissions/ — filtered to a problem
    """
    serializer_class = SubmissionListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Submission.objects.filter(user=self.request.user)
        slug = self.kwargs.get("problem_slug")
        if slug:
            qs = qs.filter(problem__slug=slug)
        return qs.select_related("problem")


class JudgeCallbackView(APIView):
    """
    POST /api/submissions/{id}/judge-callback/
    Internal endpoint called by the judge worker to write back results.
    Protected by a shared API key (not JWT).
    """
    permission_classes = [permissions.AllowAny]  # Auth via API key header

    def post(self, request, submission_id):
        from django.conf import settings
        key = request.headers.get("X-Judge-Api-Key", "")
        if key != settings.JUDGE_INTERNAL_API_KEY:
            return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        try:
            submission = Submission.objects.get(id=submission_id)
        except Submission.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        submission.status = data.get("status", Submission.Status.INTERNAL_ERROR)
        submission.runtime_ms = data.get("runtime_ms")
        submission.memory_kb = data.get("memory_kb")
        submission.error_message = data.get("error_message", "")

        from django.utils import timezone
        submission.judge_finished_at = timezone.now()
        submission.save()

        # Write per-testcase results
        from .models import SubmissionResult
        from apps.problems.models import TestCase

        for result_data in data.get("results", []):
            try:
                tc = TestCase.objects.get(id=result_data["test_case_id"])
                SubmissionResult.objects.update_or_create(
                    submission=submission,
                    test_case=tc,
                    defaults={
                        "status": result_data.get("status", "WRONG_ANSWER"),
                        "actual_output": result_data.get("actual_output", ""),
                        "expected_output": tc.expected_output,
                        "error_output": result_data.get("error_output", ""),
                        "time_ms": result_data.get("time_ms"),
                        "memory_kb": result_data.get("memory_kb"),
                    },
                )
            except TestCase.DoesNotExist:
                logger.warning(f"TestCase {result_data.get('test_case_id')} not found")

        # Update problem acceptance counter and user solved tracking
        if submission.status == Submission.Status.ACCEPTED:
            problem = submission.problem
            problem.accepted_submissions += 1
            problem.save(update_fields=["accepted_submissions"])

            UserSolvedProblem.objects.get_or_create(
                user=submission.user,
                problem=problem,
                defaults={
                    "best_runtime_ms": submission.runtime_ms,
                    "best_memory_kb": submission.memory_kb,
                },
            )
            # Update user solved count
            submission.user.problems_solved = (
                UserSolvedProblem.objects.filter(user=submission.user).count()
            )
            submission.user.save(update_fields=["problems_solved"])

        # Broadcast via Channels
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        group_name = f"submission_{submission_id}"
        try:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "submission_update",
                    "submission_id": str(submission.id),
                    "status": submission.status,
                    "runtime_ms": submission.runtime_ms,
                    "memory_kb": submission.memory_kb,
                },
            )
        except Exception as e:
            logger.warning(f"Could not broadcast submission update: {e}")

        return Response({"ok": True})