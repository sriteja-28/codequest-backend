from rest_framework import serializers
from .models import Submission, SubmissionResult


class SubmissionResultSerializer(serializers.ModelSerializer):
    is_hidden = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionResult
        fields = [
            "id", "test_case", "status",
            "actual_output", "expected_output", "error_output",
            "time_ms", "memory_kb", "is_hidden",
        ]

    def get_is_hidden(self, obj):
        return obj.test_case.is_hidden


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
            "language", "code", "status",
            "runtime_ms", "memory_kb", "error_message",
            "results", "duration_ms",
            "created_at", "judge_started_at", "judge_finished_at",
        ]
        read_only_fields = [
            "id", "status", "runtime_ms", "memory_kb", "error_message",
            "results", "duration_ms", "judge_started_at", "judge_finished_at",
        ]

    def get_duration_ms(self, obj):
        if obj.judge_started_at and obj.judge_finished_at:
            delta = obj.judge_finished_at - obj.judge_started_at
            return int(delta.total_seconds() * 1000)
        return None


class SubmissionCreateSerializer(serializers.ModelSerializer):
    problem_slug = serializers.SlugField(write_only=True)

    class Meta:
        model = Submission
        fields = ["problem_slug", "language", "code", "contest"]

    def validate_language(self, value):
        if value not in [c[0] for c in Submission.Language.choices]:
            raise serializers.ValidationError("Unsupported language.")
        return value

    def validate(self, data):
        from apps.problems.models import Problem
        slug = data.pop("problem_slug")
        try:
            data["problem"] = Problem.objects.get(slug=slug, is_published=True)
        except Problem.DoesNotExist:
            raise serializers.ValidationError("Problem not found.")
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