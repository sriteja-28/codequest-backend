from rest_framework import serializers
from django.utils import timezone
from .models import Contest, ContestProblem, ContestParticipant, ContestSubmissionStat
from apps.problems.serializers import ProblemListSerializer
from apps.submissions.models import Submission


class ContestProblemSerializer(serializers.ModelSerializer):
    problem = ProblemListSerializer(read_only=True)
    contest_accepted = serializers.SerializerMethodField()
    contest_total = serializers.SerializerMethodField()
    # Per-user fields (only when request user is authenticated)
    user_solved = serializers.SerializerMethodField()
    user_wrong_attempts = serializers.SerializerMethodField()
    user_solve_time = serializers.SerializerMethodField()

    class Meta:
        model = ContestProblem
        fields = [
            "id", "problem", "order_index", "score",
            "contest_accepted", "contest_total",
            "user_solved", "user_wrong_attempts", "user_solve_time",
        ]

    def get_contest_accepted(self, obj):
        return Submission.objects.filter(
            problem=obj.problem, contest=obj.contest, status="ACCEPTED"
        ).values("user").distinct().count()

    def get_contest_total(self, obj):
        return Submission.objects.filter(
            problem=obj.problem, contest=obj.contest
        ).values("user").distinct().count()

    def _get_stat(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        try:
            participant = ContestParticipant.objects.get(
                contest=obj.contest, user=request.user
            )
            return ContestSubmissionStat.objects.filter(
                participant=participant, contest_problem=obj
            ).first()
        except ContestParticipant.DoesNotExist:
            return None

    def get_user_solved(self, obj):
        stat = self._get_stat(obj)
        return stat.is_solved if stat else False

    def get_user_wrong_attempts(self, obj):
        stat = self._get_stat(obj)
        return stat.wrong_attempts if stat else 0

    def get_user_solve_time(self, obj):
        stat = self._get_stat(obj)
        return stat.solve_time_minutes if stat else None


class ContestListSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Contest
        fields = [
            "id", "name", "slug", "start_at", "end_at",
            "is_public", "is_rated", "status", "participant_count", "duration_minutes",
        ]

    def get_participant_count(self, obj):
        return obj.participants.count()


class ContestDetailSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    contest_problems = ContestProblemSerializer(many=True, read_only=True)
    participant_count = serializers.SerializerMethodField()
    is_registered = serializers.SerializerMethodField()

    class Meta:
        model = Contest
        fields = [
            "id", "name", "slug", "description_md",
            "start_at", "end_at", "is_public", "is_rated",
            "max_participants", "duration_minutes", "status",
            "contest_problems", "participant_count", "is_registered",
        ]

    def get_participant_count(self, obj):
        return obj.participants.count()

    def get_is_registered(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.participants.filter(user=request.user).exists()


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")
    display_name = serializers.CharField(source="user.display_name")
    avatar_url = serializers.URLField(source="user.avatar_url")
    problem_stats = serializers.SerializerMethodField()

    class Meta:
        model = ContestParticipant
        fields = [
            "rank", "username", "display_name", "avatar_url",
            "final_score", "is_disqualified", "problem_stats",
        ]

    def get_problem_stats(self, obj):
        stats = ContestSubmissionStat.objects.filter(participant=obj).select_related("contest_problem")
        return {
            str(s.contest_problem_id): {
                "solved": s.is_solved,
                "wrong_attempts": s.wrong_attempts,
                "solve_time": s.solve_time_minutes,
                "score": s.score_awarded,
            }
            for s in stats
        }


class ContestAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contest
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]