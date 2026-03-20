from rest_framework import serializers
from .models import Contest, ContestProblem, ContestParticipant
from apps.problems.serializers import ProblemListSerializer


class ContestProblemSerializer(serializers.ModelSerializer):
    problem = ProblemListSerializer(read_only=True)

    class Meta:
        model = ContestProblem
        fields = ["id", "problem", "order_index", "score"]


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

    class Meta:
        model = ContestParticipant
        fields = ["rank", "username", "display_name", "avatar_url", "final_score", "is_disqualified"]


class ContestAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contest
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]