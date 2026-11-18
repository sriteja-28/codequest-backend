from django.conf import settings
from rest_framework import exceptions, serializers

from .models import Submission, SubmissionResult
from .services import TERMINAL_STATUSES, public_error_message


class SubmissionResultSerializer(serializers.ModelSerializer):
    """Per-test-case result.

    For hidden test cases the input, expected output, program output and stderr
    are withheld unless the serializer context has reveal_hidden=True (admins).
    """

    is_hidden = serializers.SerializerMethodField()
    input_data = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionResult
        fields = [
            "id", "test_case", "status",
            "input_data", "actual_output", "expected_output", "error_output",
            "time_ms", "memory_kb", "is_hidden",
        ]

    def get_is_hidden(self, obj):
        return obj.test_case.is_hidden

    def get_input_data(self, obj):
        return obj.test_case.input_data

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if obj.test_case.is_hidden and not self.context.get("reveal_hidden", False):
            for field in ("input_data", "actual_output", "expected_output", "error_output"):
                data[field] = None
        return data


class SubmissionSerializer(serializers.ModelSerializer):
    results = SubmissionResultSerializer(many=True, read_only=True)
    problem_slug = serializers.CharField(source="problem.slug", read_only=True)
    problem_title = serializers.CharField(source="problem.title", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    duration_ms = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            "id", "problem_slug", "problem_title", "username",
            "language", "code", "status", "is_sample_run",
            "runtime_ms", "memory_kb", "error_message",
            "results", "duration_ms",
            "created_at", "judge_started_at", "judge_finished_at",
        ]
        read_only_fields = fields

    def get_duration_ms(self, obj):
        """Wall-clock time the judge spent (RUNNING callback -> verdict)."""
        if obj.judge_started_at and obj.judge_finished_at:
            delta = obj.judge_finished_at - obj.judge_started_at
            return int(delta.total_seconds() * 1000)
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("reveal_hidden", False):
            data["error_message"] = public_error_message(instance, list(instance.results.all()))
        return data


def _code_field():
    return serializers.CharField(trim_whitespace=False)


def _validate_code(value: str) -> str:
    if not value.strip():
        raise serializers.ValidationError("Code must not be empty.")
    if len(value.encode("utf-8")) > settings.MAX_CODE_BYTES:
        raise serializers.ValidationError(f"Code exceeds the {settings.MAX_CODE_BYTES}-byte limit.")
    return value


def resolve_problem_for_user(slug: str, user):
    """Published problem visible to `user`; PRO problems require a Pro plan.
    Admins may run/submit unpublished problems (authoring workflow)."""
    from apps.problems.models import Problem

    qs = Problem.objects.all() if getattr(user, "is_admin", False) else Problem.objects.filter(is_published=True)
    problem = qs.filter(slug=slug).first()
    if problem is None:
        raise serializers.ValidationError({"problem_slug": "Problem not found."})
    if (
        problem.visibility == Problem.Visibility.PRO
        and not getattr(user, "is_pro", False)
        and not getattr(user, "is_admin", False)
    ):
        raise exceptions.PermissionDenied(detail={"detail": "This problem requires a Pro plan.", "code": "pro_required"})
    return problem


def resolve_contest_problem(contest_id, slug: str, user):
    """(contest, problem) for a problem opened through its contest, published or not.
    Access rules live in apps/contests/access.py; errors map to 400/403 here."""
    from apps.contests.access import ContestAccessError, contest_problem_for, visible_contest
    from apps.core.features import FeatureDisabled, feature_enabled_for

    if not feature_enabled_for(user, "contests"):
        raise FeatureDisabled("contests")
    contest = visible_contest(user=user, pk=contest_id)
    if contest is None:
        raise serializers.ValidationError({"contest": "Contest not found."})
    try:
        return contest, contest_problem_for(contest, slug, user)
    except ContestAccessError as exc:
        if exc.code == ContestAccessError.NOT_IN_CONTEST:
            raise serializers.ValidationError({"contest": exc.message}) from exc
        if exc.code == ContestAccessError.PRO_REQUIRED:
            raise exceptions.PermissionDenied(
                detail={"detail": "This problem requires a Pro plan.", "code": "pro_required"}
            ) from exc
        raise exceptions.PermissionDenied(
            detail={"detail": "This contest has not started yet.", "code": exc.code}
        ) from exc


class RunCodeSerializer(serializers.Serializer):
    """Judge the sample cases only. With `contest`, the problem is opened through
    that contest (so unpublished contest problems work while it runs); the run
    itself is never attached to the contest and never scores."""

    problem_slug = serializers.SlugField()
    language = serializers.ChoiceField(choices=Submission.Language.choices)
    code = _code_field()
    contest = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate_code(self, value):
        return _validate_code(value)

    def validate(self, data):
        user = self.context["request"].user
        slug = data.pop("problem_slug")
        contest_id = data.pop("contest", None)
        self._resolved_contest = None
        if contest_id:
            self._resolved_contest, data["problem"] = resolve_contest_problem(contest_id, slug, user)
        else:
            data["problem"] = resolve_problem_for_user(slug, user)
        data["contest"] = None
        return data


class SubmissionCreateSerializer(RunCodeSerializer):
    """A full submission; with `contest` it also counts toward that contest
    (live window, registered, not disqualified)."""

    def validate(self, data):
        from apps.contests.access import submission_block_reason

        data = super().validate(data)
        contest = self._resolved_contest
        if contest is None:
            return data
        reason = submission_block_reason(contest, self.context["request"].user)
        if reason:
            raise exceptions.PermissionDenied(reason)
        data["contest"] = contest
        return data


class SubmissionListSerializer(serializers.ModelSerializer):
    """Compact list view — no code, no per-testcase results."""
    problem_slug = serializers.CharField(source="problem.slug", read_only=True)
    problem_title = serializers.CharField(source="problem.title", read_only=True)

    class Meta:
        model = Submission
        fields = [
            "id", "problem_slug", "problem_title",
            "language", "status", "runtime_ms", "memory_kb",
            "created_at",
        ]


# ─── Judge → backend contract ────────────────────────────────────────────────

_CALLBACK_STATUSES = [Submission.Status.RUNNING.value] + sorted(str(s) for s in TERMINAL_STATUSES)


class JudgeResultItemSerializer(serializers.Serializer):
    test_case_id = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=SubmissionResult.Status.choices)
    actual_output = serializers.CharField(required=False, allow_blank=True, default="", trim_whitespace=False)
    error_output = serializers.CharField(required=False, allow_blank=True, default="", trim_whitespace=False)
    time_ms = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)
    memory_kb = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)


class JudgeCallbackSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=_CALLBACK_STATUSES)
    runtime_ms = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)
    memory_kb = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)
    error_message = serializers.CharField(required=False, allow_blank=True, default="", trim_whitespace=False)
    results = JudgeResultItemSerializer(many=True, required=False, default=list)

    def validate_results(self, value):
        if len(value) > 1000:
            raise serializers.ValidationError("Too many results.")
        ids = [r["test_case_id"] for r in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Duplicate test_case_id in results.")
        return value
