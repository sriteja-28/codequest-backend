from rest_framework import serializers
from .models import Problem, Section, Tag, TestCase, Solution, ProblemTag


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ["id", "name", "display_name", "order_index", "icon"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "tag_type"]


class TestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCase
        fields = ["id", "input_data", "expected_output", "explanation", "order_index"]


class TestCaseAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCase
        fields = "__all__"


class SolutionSerializer(serializers.ModelSerializer):
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = Solution
        fields = [
            "id",
            "title",
            "approach_summary_md",
            "code_python",
            "code_cpp",
            "code_java",
            "code_javascript",
            "time_complexity",
            "space_complexity",
            "complexity_explanation_md",
            "is_official",
            "visibility",
            "order_index",
            "is_locked",
        ]

    def get_is_locked(self, obj):
        request = self.context.get("request")
        if obj.visibility == Solution.Visibility.PRO:
            if not request or not request.user.is_authenticated:
                return True
            return not request.user.is_pro
        return False

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get("is_locked"):
            # Strip code fields for locked solutions
            data["approach_summary_md"] = data["approach_summary_md"][:200] + "…"
            data["code_python"] = ""
            data["code_cpp"] = ""
            data["code_java"] = ""
            data["code_javascript"] = ""
        return data


class ProblemListSerializer(serializers.ModelSerializer):
    """Compact representation for problem list."""

    section = SectionSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    acceptance_rate = serializers.FloatField(read_only=True)
    is_solved = serializers.SerializerMethodField()

    class Meta:
        model = Problem
        fields = [
            "id",
            "slug",
            "title",
            "number",
            "difficulty",
            "visibility",
            "section",
            "tags",
            "acceptance_rate",
            "time_complexity_average",
            "space_complexity",
            "total_submissions",
            "accepted_submissions",
            "is_solved",
        ]

    def get_is_solved(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.id in self.context.get("solved_ids", set())


class ProblemDetailSerializer(serializers.ModelSerializer):
    """Full problem detail including sample test cases."""

    section = SectionSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    sample_test_cases = serializers.SerializerMethodField()
    acceptance_rate = serializers.FloatField(read_only=True)
    hints = serializers.SerializerMethodField()
    is_solved = serializers.SerializerMethodField()
    next_slug = serializers.SerializerMethodField()
    prev_slug = serializers.SerializerMethodField()

    class Meta:
        model = Problem
        fields = [
            "id",
            "slug",
            "title",
            "number",
            "difficulty",
            "visibility",
            "statement_md",
            "section",
            "tags",
            "time_complexity_best",
            "time_complexity_average",
            "time_complexity_worst",
            "space_complexity",
            "complexity_notes_md",
            "sample_test_cases",
            "hints",
            "acceptance_rate",
            "total_submissions",
            "accepted_submissions",
            "is_solved",
            "next_slug",
            "prev_slug",
            "starter_code_python",
            "starter_code_cpp",
            "starter_code_java",
            "starter_code_javascript",
        ]

    def get_sample_test_cases(self, obj):
        qs = obj.test_cases.filter(is_sample=True).order_by("order_index")
        return TestCaseSerializer(qs, many=True).data

    def get_hints(self, obj):
        hints = obj.get_hints()
        request = self.context.get("request")
        if not request or not request.user.is_authenticated or not request.user.is_pro:
            # Free users see only first hint label, not content
            return [{"index": i, "available": i == 0} for i in range(len(hints))]
        return [
            {"index": i, "available": True, "content": h} for i, h in enumerate(hints)
        ]

    def get_is_solved(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return obj.id in self.context.get("solved_ids", set())

    def get_next_slug(self, obj):
        # Next problem by number within same section, fallback to global order
        qs = (
            Problem.objects.filter(is_published=True, number__gt=obj.number)
            .order_by("number")
            .first()
        )
        return qs.slug if qs else None

    def get_prev_slug(self, obj):
        qs = (
            Problem.objects.filter(is_published=True, number__lt=obj.number)
            .order_by("-number")
            .first()
        )
        return qs.slug if qs else None


class ProblemAdminSerializer(serializers.ModelSerializer):
    """Full editable serializer for admin CRUD."""

    section_id = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.all(),
        source="section",
        write_only=True,
        required=False,
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        source="tags",
        write_only=True,
        required=False,
    )
    section = SectionSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)

    class Meta:
        model = Problem
        fields = [
            "id",
            "slug",
            "title",
            "number",
            "difficulty",
            "visibility",
            "statement_md",
            "section",
            "section_id",
            "tags",
            "tag_ids",
            "time_complexity_best",
            "time_complexity_average",
            "time_complexity_worst",
            "space_complexity",
            "complexity_notes_md",
            "hints_md",
            "is_published",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        problem = super().create(validated_data)
        problem.tags.set(tags)
        return problem

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        problem = super().update(instance, validated_data)
        if tags is not None:
            problem.tags.set(tags)
        return problem
