from django.db.models import Count, Q
from rest_framework import serializers

from apps.problems.models import Problem
from apps.problems.serializers import ProblemListSerializer

from .models import Contest, ContestParticipant, ContestProblem, ContestSubmissionStat


def contest_attempts(contest) -> dict:
    """{problem_id: (users_accepted, users_attempted)} over judged contest submissions."""
    rows = (
        ContestSubmissionStat.objects.filter(participant__contest=contest, participant__is_disqualified=False)
        .values("contest_problem__problem_id")
        .annotate(
            attempted=Count("participant_id", distinct=True),
            accepted=Count("participant_id", filter=Q(is_solved=True), distinct=True),
        )
    )
    return {row["contest_problem__problem_id"]: (row["accepted"], row["attempted"]) for row in rows}


def user_problem_stats(contest, user) -> dict:
    """{contest_problem_id: ContestSubmissionStat} for the requesting participant."""
    if not user or not user.is_authenticated:
        return {}
    stats = ContestSubmissionStat.objects.filter(participant__contest=contest, participant__user=user)
    return {stat.contest_problem_id: stat for stat in stats}


def user_result(context, contest):
    """The caller's standing in `contest` (from the participations map in the context)."""
    participation = (context.get("participations") or {}).get(contest.id)
    if participation is None:
        return None
    return {
        "rank": participation.rank,
        "final_score": participation.final_score,
        "is_disqualified": participation.is_disqualified,
    }


class ContestProblemSerializer(serializers.ModelSerializer):
    """One contest problem. Aggregates come precomputed in the context
    (`attempts`, `user_stats`) so a contest page costs a fixed number of queries."""

    problem = ProblemListSerializer(read_only=True)
    contest_accepted = serializers.SerializerMethodField()
    contest_total = serializers.SerializerMethodField()
    user_solved = serializers.SerializerMethodField()
    user_wrong_attempts = serializers.SerializerMethodField()
    user_solve_time = serializers.SerializerMethodField()
    # False until the problem is released to the practice catalogue.
    practice_available = serializers.BooleanField(source="problem.is_published", read_only=True)

    class Meta:
        model = ContestProblem
        fields = [
            "id", "problem", "order_index", "score",
            "contest_accepted", "contest_total",
            "user_solved", "user_wrong_attempts", "user_solve_time",
            "practice_available",
        ]

    def _attempts(self, obj):
        return (self.context.get("attempts") or {}).get(obj.problem_id, (0, 0))

    def _stat(self, obj):
        return (self.context.get("user_stats") or {}).get(obj.id)

    def get_contest_accepted(self, obj):
        return self._attempts(obj)[0]

    def get_contest_total(self, obj):
        return self._attempts(obj)[1]

    def get_user_solved(self, obj):
        stat = self._stat(obj)
        return bool(stat and stat.is_solved)

    def get_user_wrong_attempts(self, obj):
        stat = self._stat(obj)
        return stat.wrong_attempts if stat else 0

    def get_user_solve_time(self, obj):
        stat = self._stat(obj)
        return stat.solve_time_minutes if stat else None


class ContestListSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    finalized = serializers.BooleanField(source="is_finalized", read_only=True)
    participant_count = serializers.SerializerMethodField()
    problem_count = serializers.SerializerMethodField()
    user_result = serializers.SerializerMethodField()

    class Meta:
        model = Contest
        fields = [
            "id", "name", "slug", "start_at", "end_at",
            "is_public", "is_rated", "status", "finalized",
            "participant_count", "problem_count", "duration_minutes", "user_result",
        ]

    def get_participant_count(self, obj):
        annotated = getattr(obj, "participant_total", None)
        return annotated if annotated is not None else obj.participants.count()

    def get_problem_count(self, obj):
        annotated = getattr(obj, "problem_total", None)
        return annotated if annotated is not None else obj.contest_problems.count()

    def get_user_result(self, obj):
        return user_result(self.context, obj)


class ContestDetailSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    finalized = serializers.BooleanField(source="is_finalized", read_only=True)
    contest_problems = serializers.SerializerMethodField()
    problems_hidden = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()
    is_registered = serializers.SerializerMethodField()
    user_result = serializers.SerializerMethodField()

    class Meta:
        model = Contest
        fields = [
            "id", "name", "slug", "description_md",
            "start_at", "end_at", "is_public", "is_rated",
            "max_participants", "duration_minutes", "status",
            "finalized", "finalized_at",
            "contest_problems", "problems_hidden", "participant_count", "is_registered",
            "user_result",
        ]

    def _problems_hidden(self, obj):
        """Problems are revealed when the contest starts (admins always see them)."""
        request = self.context.get("request")
        is_admin = bool(request and request.user.is_authenticated and request.user.is_admin)
        return obj.status == "upcoming" and not is_admin

    def get_problems_hidden(self, obj):
        return self._problems_hidden(obj)

    def get_contest_problems(self, obj):
        if self._problems_hidden(obj):
            return []
        request = self.context.get("request")
        qs = obj.contest_problems.select_related("problem__section").prefetch_related("problem__tags")
        context = {
            **self.context,
            "attempts": contest_attempts(obj),
            "user_stats": user_problem_stats(obj, request.user if request else None),
        }
        return ContestProblemSerializer(qs, many=True, context=context).data

    def get_participant_count(self, obj):
        return obj.participants.count()

    def get_is_registered(self, obj):
        participations = self.context.get("participations")
        if participations is not None:
            return obj.id in participations
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.participants.filter(user=request.user).exists()

    def get_user_result(self, obj):
        return user_result(self.context, obj)


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")
    display_name = serializers.CharField(source="user.display_name")
    avatar_url = serializers.CharField(source="user.avatar_url")
    penalty_minutes = serializers.SerializerMethodField()
    problem_stats = serializers.SerializerMethodField()

    class Meta:
        model = ContestParticipant
        fields = [
            "rank", "username", "display_name", "avatar_url",
            "final_score", "penalty_minutes", "is_disqualified", "problem_stats",
        ]

    def get_penalty_minutes(self, obj):
        from .scoring import participant_penalty_minutes

        return participant_penalty_minutes(obj)

    def get_problem_stats(self, obj):
        # Uses the prefetched relation when the queryset provides it.
        return {
            str(s.contest_problem_id): {
                "solved": s.is_solved,
                "wrong_attempts": s.wrong_attempts,
                "solve_time": s.solve_time_minutes,
                "score": s.score_awarded,
            }
            for s in obj.problem_stats.all()
        }


class ContestProblemEntrySerializer(serializers.Serializer):
    """One row of a contest's problem set (order = list position)."""

    problem_id = serializers.PrimaryKeyRelatedField(queryset=Problem.objects.all())
    score = serializers.IntegerField(min_value=1, max_value=10_000, default=100)


class ContestAdminSerializer(serializers.ModelSerializer):
    """Admin CRUD. `problem_entries` (write) replaces the problem set in order;
    it is locked once the contest starts. Blank slugs follow the name."""

    status = serializers.CharField(read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    participant_count = serializers.SerializerMethodField()
    problems = serializers.SerializerMethodField()
    problem_entries = ContestProblemEntrySerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Contest
        fields = [
            "id", "name", "slug", "description_md", "start_at", "end_at",
            "is_public", "is_rated", "max_participants", "release_problems",
            "status", "duration_minutes", "participant_count", "finalized_at",
            "problems", "problem_entries", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "finalized_at", "created_at", "updated_at"]
        extra_kwargs = {"slug": {"required": False}}

    def get_participant_count(self, obj):
        annotated = getattr(obj, "participant_total", None)
        return annotated if annotated is not None else obj.participants.count()

    def get_problems(self, obj):
        links = sorted(obj.contest_problems.all(), key=lambda link: (link.order_index, link.id))
        return [
            {
                "id": link.id, "problem_id": link.problem_id, "slug": link.problem.slug,
                "title": link.problem.title, "difficulty": link.problem.difficulty,
                "is_published": link.problem.is_published, "score": link.score,
            }
            for link in links
        ]

    def validate_problem_entries(self, entries):
        ids = [entry["problem_id"].pk for entry in entries]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("A problem can appear only once in a contest.")
        return entries

    def validate(self, data):
        instance = self.instance
        if instance and instance.is_finalized:
            frozen = ("start_at", "end_at", "release_problems")
            if any(field in data and data[field] != getattr(instance, field) for field in frozen):
                raise serializers.ValidationError("A finalized contest's schedule and release policy are read-only.")
        start = data.get("start_at", getattr(instance, "start_at", None))
        end = data.get("end_at", getattr(instance, "end_at", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_at": "end_at must be after start_at."})
        entries = data.get("problem_entries")
        if entries is not None and instance is not None and instance.status != "upcoming":
            current = [(link.problem_id, link.score) for link in instance.contest_problems.order_by("order_index", "id")]
            proposed = [(entry["problem_id"].pk, entry["score"]) for entry in entries]
            if current != proposed:
                raise serializers.ValidationError(
                    {"problem_entries": "Problems and points are locked once the contest has started."}
                )
        if instance is None and not data.get("slug") and data.get("name"):
            from apps.core.slugs import unique_slug

            data["slug"] = unique_slug(Contest, data["name"])
        return data

    def _sync_problems(self, contest, entries):
        contest.contest_problems.all().delete()
        ContestProblem.objects.bulk_create([
            ContestProblem(contest=contest, problem=entry["problem_id"], score=entry["score"], order_index=index)
            for index, entry in enumerate(entries)
        ])

    def create(self, validated_data):
        entries = validated_data.pop("problem_entries", None)
        contest = super().create(validated_data)
        if entries is not None:
            self._sync_problems(contest, entries)
        return contest

    def update(self, instance, validated_data):
        entries = validated_data.pop("problem_entries", None)
        contest = super().update(instance, validated_data)
        if entries is not None and contest.status == "upcoming":
            self._sync_problems(contest, entries)
        return contest


class ParticipantUpdateSerializer(serializers.ModelSerializer):
    """Admin corrections before finalization. Scores and ranks are always
    recomputed (solved points + score_adjustment), so neither is writable."""

    class Meta:
        model = ContestParticipant
        fields = ["is_disqualified", "disqualified_reason", "score_adjustment", "adjustment_reason"]
        extra_kwargs = {"score_adjustment": {"min_value": -100_000, "max_value": 100_000}}


class AdminParticipantSerializer(serializers.ModelSerializer):
    """Every participant (disqualified ones included) for the admin contest page."""

    user = serializers.SerializerMethodField()
    penalty_minutes = serializers.SerializerMethodField()
    solved_count = serializers.SerializerMethodField()

    class Meta:
        model = ContestParticipant
        fields = [
            "user", "registered_at", "rank", "final_score", "score_adjustment", "adjustment_reason",
            "penalty_minutes", "solved_count", "is_disqualified", "disqualified_reason",
        ]

    def get_user(self, obj):
        user = obj.user
        return {
            "id": user.id, "username": user.username, "display_name": user.display_name,
            "email": user.email, "avatar_url": user.avatar_url,
        }

    def get_penalty_minutes(self, obj):
        from .scoring import participant_penalty_minutes

        return participant_penalty_minutes(obj)

    def get_solved_count(self, obj):
        return sum(1 for stat in obj.problem_stats.all() if stat.is_solved)
