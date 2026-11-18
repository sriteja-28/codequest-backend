from rest_framework import serializers

from . import codegen
from .models import (
    DailyProblem,
    Problem,
    ProblemList,
    ProblemListItem,
    Section,
    Tag,
    TestCase,
    Solution,
    ProblemTag,
)


class SectionSummarySerializer(serializers.ModelSerializer):
    """Compact section for nesting inside problems (no per-row counts)."""

    class Meta:
        model = Section
        fields = ["id", "name", "slug", "display_name", "order_index", "icon"]


class SectionSerializer(serializers.ModelSerializer):
    """Full section for the catalogue and the admin CRUD endpoints."""

    prerequisites = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="slug"
    )
    problem_count = serializers.SerializerMethodField()
    solved_count = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = [
            "id", "name", "slug", "display_name", "description_md",
            "order_index", "icon", "prerequisites", "problem_count", "solved_count",
        ]

    def get_problem_count(self, obj):
        annotated = getattr(obj, "published_problem_count", None)
        if annotated is not None:
            return annotated
        return obj.problems.filter(is_published=True).count()

    def get_solved_count(self, obj):
        return (self.context.get("solved_by_section") or {}).get(obj.id, 0)


class SectionAdminSerializer(serializers.ModelSerializer):
    prerequisite_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Section.objects.all(),
        source="prerequisites",
        required=False,
    )
    problem_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Section
        fields = [
            "id", "name", "slug", "display_name", "description_md",
            "order_index", "icon", "prerequisite_ids", "problem_count",
        ]
        extra_kwargs = {"slug": {"required": False}}

    def validate_prerequisite_ids(self, sections):
        """No self-reference and no cycles: the roadmap draws prerequisites as a DAG."""
        if self.instance is None or not sections:
            return sections
        own_id = self.instance.pk
        if any(section.pk == own_id for section in sections):
            raise serializers.ValidationError("A section cannot require itself.")
        edges = {}
        for source_id, target_id in Section.prerequisites.through.objects.values_list("from_section_id", "to_section_id"):
            edges.setdefault(source_id, set()).add(target_id)
        stack, seen = [section.pk for section in sections], set()
        while stack:
            node = stack.pop()
            if node == own_id:
                raise serializers.ValidationError("That would create a cycle: a prerequisite already depends on this section.")
            if node not in seen:
                seen.add(node)
                stack.extend(edges.get(node, ()))
        return sections


class TagAdminSerializer(serializers.ModelSerializer):
    problem_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "tag_type", "problem_count"]
        # Blank slugs are generated from the name (Tag.save).
        extra_kwargs = {"slug": {"required": False}}


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "tag_type"]


class TestCaseSerializer(serializers.ModelSerializer):
    display_input = serializers.SerializerMethodField()

    class Meta:
        model = TestCase
        fields = ["id", "input_data", "display_input", "expected_output", "explanation", "order_index"]

    def get_display_input(self, obj):
        signature = self.context.get("function_signature")
        if not signature:
            return obj.input_data
        return codegen.format_input(signature, obj.input_data)


class TestCaseAdminSerializer(serializers.ModelSerializer):
    """Test cases of one problem (the problem comes from the URL and the context).
    Function-mode problems get their input/expected output checked against the
    signature, exactly as the judge will read them."""

    class Meta:
        model = TestCase
        fields = "__all__"
        # The problem comes from the URL (/admin/problems/<slug>/testcases/).
        read_only_fields = ["problem"]

    def validate(self, data):
        problem = self.context.get("problem") or getattr(self.instance, "problem", None)
        signature = getattr(problem, "function_signature", None)
        if not signature:
            return data
        errors = {}
        input_data = data.get("input_data", getattr(self.instance, "input_data", None))
        expected = data.get("expected_output", getattr(self.instance, "expected_output", None))
        if input_data is not None:
            try:
                codegen.validate_input(signature, input_data)
            except (ValueError, codegen.SignatureError) as exc:
                errors["input_data"] = str(exc)
        if expected is not None:
            try:
                codegen.validate_expected(signature, expected, problem.compare_mode)
            except (ValueError, codegen.SignatureError) as exc:
                errors["expected_output"] = str(exc)
        if errors:
            raise serializers.ValidationError(errors)
        return data


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
        if request and request.user.is_authenticated and request.user.is_admin:
            return False
        if self.context.get("contest_locked"):
            return True
        if obj.visibility == Solution.Visibility.PRO:
            if not request or not request.user.is_authenticated:
                return True
            return not request.user.is_pro
        return False

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get("is_locked"):
            # Strip code and explanations for locked solutions. PRO editorials
            # keep a short teaser; during a live contest nothing is revealed.
            if self.context.get("contest_locked"):
                data["approach_summary_md"] = ""
            else:
                data["approach_summary_md"] = data["approach_summary_md"][:200] + "…"
            data["complexity_explanation_md"] = ""
            data["code_python"] = ""
            data["code_cpp"] = ""
            data["code_java"] = ""
            data["code_javascript"] = ""
        return data


class ProblemListSerializer(serializers.ModelSerializer):
    """Compact representation for problem list."""

    section = SectionSummarySerializer(read_only=True)
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

    section = SectionSummarySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    sample_test_cases = serializers.SerializerMethodField()
    acceptance_rate = serializers.FloatField(read_only=True)
    hints = serializers.SerializerMethodField()
    is_solved = serializers.SerializerMethodField()
    is_starred = serializers.SerializerMethodField()
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
            "function_signature",
            "compare_mode",
            "float_tolerance",
            "acceptance_rate",
            "total_submissions",
            "accepted_submissions",
            "is_solved",
            "is_starred",
            "next_slug",
            "prev_slug",
            "starter_code_python",
            "starter_code_cpp",
            "starter_code_java",
            "starter_code_javascript",
        ]

    def get_sample_test_cases(self, obj):
        qs = obj.test_cases.filter(is_sample=True).order_by("order_index")
        return TestCaseSerializer(
            qs,
            many=True,
            context={**self.context, "function_signature": obj.function_signature},
        ).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Existing rows may predate the signature, and admins may leave the
        # editable starter blank on purpose: generate a function-only template.
        if instance.function_signature:
            for language in codegen.LANGUAGES:
                key = f"starter_code_{language}"
                if not (data.get(key) or "").strip():
                    data[key] = codegen.starter_code(instance.function_signature, language)
        return data

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

    def get_is_starred(self, obj):
        return obj.id in self.context.get("starred_ids", set())

    def get_next_slug(self, obj):
        # Neighbours by catalogue number; unnumbered problems (e.g. fresh contest
        # problems) have none, and `number__gt=None` would raise.
        if obj.number is None:
            return None
        qs = (
            Problem.objects.filter(is_published=True, number__gt=obj.number)
            .order_by("number")
            .first()
        )
        return qs.slug if qs else None

    def get_prev_slug(self, obj):
        if obj.number is None:
            return None
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
        allow_null=True,
    )
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        source="tags",
        write_only=True,
        required=False,
    )
    section = SectionSummarySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    acceptance_rate = serializers.FloatField(read_only=True)
    test_case_count = serializers.SerializerMethodField()

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
            "function_signature",
            "compare_mode",
            "float_tolerance",
            "starter_code_python",
            "starter_code_cpp",
            "starter_code_java",
            "starter_code_javascript",
            "is_published",
            "total_submissions",
            "accepted_submissions",
            "acceptance_rate",
            "test_case_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "total_submissions", "accepted_submissions",
        ]
        extra_kwargs = {"slug": {"required": False}}

    def get_test_case_count(self, obj):
        annotated = getattr(obj, "test_case_total", None)
        return annotated if annotated is not None else obj.test_cases.count()

    def validate_function_signature(self, value):
        if not value:
            return None
        try:
            return codegen.validate_signature(value)
        except codegen.SignatureError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate(self, data):
        signature = data.get("function_signature", getattr(self.instance, "function_signature", None))
        mode = data.get("compare_mode", getattr(self.instance, "compare_mode", "EXACT"))
        if signature and mode == "UNORDERED" and "[]" not in signature["return_type"]:
            raise serializers.ValidationError({"compare_mode": "Unordered comparison needs an array return type."})
        tolerance = data.get("float_tolerance", getattr(self.instance, "float_tolerance", 1e-5))
        import math
        if not math.isfinite(tolerance) or tolerance < 0:
            raise serializers.ValidationError({"float_tolerance": "Use a finite, non-negative tolerance."})
        if self.instance is None and not data.get("slug") and data.get("title"):
            from apps.core.slugs import unique_slug
            data["slug"] = unique_slug(Problem, data["title"])
        return data

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


class ProblemAdminListSerializer(serializers.ModelSerializer):
    """Light rows for the admin problem table (no statements or starter code)."""

    section = SectionSummarySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    acceptance_rate = serializers.FloatField(read_only=True)
    test_case_count = serializers.IntegerField(source="test_case_total", read_only=True)
    has_signature = serializers.SerializerMethodField()

    class Meta:
        model = Problem
        fields = [
            "id", "slug", "title", "number", "difficulty", "visibility", "is_published",
            "section", "tags", "total_submissions", "accepted_submissions", "acceptance_rate",
            "test_case_count", "has_signature", "updated_at",
        ]

    def get_has_signature(self, obj):
        return bool(obj.function_signature)


# ─────────────────────────────────────────────
# Practice lists / daily problem / stars
# ─────────────────────────────────────────────

def _published_items(problem_list):
    """List items whose problem is still published (works on prefetched rows)."""
    return [
        item for item in problem_list.items.all()
        if item.problem.is_published
    ]


class PracticeListSerializer(serializers.ModelSerializer):
    problem_count = serializers.SerializerMethodField()
    solved_count = serializers.SerializerMethodField()
    difficulties = serializers.SerializerMethodField()

    class Meta:
        model = ProblemList
        fields = [
            "id", "slug", "title", "description_md", "order_index",
            "problem_count", "solved_count", "difficulties",
        ]

    def get_problem_count(self, obj):
        return len(_published_items(obj))

    def get_solved_count(self, obj):
        solved_ids = self.context.get("solved_ids") or set()
        return sum(1 for item in _published_items(obj) if item.problem_id in solved_ids)

    def get_difficulties(self, obj):
        counts = {"EASY": 0, "MEDIUM": 0, "HARD": 0}
        for item in _published_items(obj):
            counts[item.problem.difficulty] = counts.get(item.problem.difficulty, 0) + 1
        return counts


class PracticeListDetailSerializer(PracticeListSerializer):
    problems = serializers.SerializerMethodField()

    class Meta(PracticeListSerializer.Meta):
        fields = PracticeListSerializer.Meta.fields + ["problems"]

    def get_problems(self, obj):
        items = _published_items(obj)
        problems = [item.problem for item in items]
        return ProblemListSerializer(problems, many=True, context=self.context).data


class DailyProblemSerializer(serializers.ModelSerializer):
    problem = ProblemListSerializer(read_only=True)

    class Meta:
        model = DailyProblem
        fields = ["date", "problem"]


class DailyProblemAdminSerializer(serializers.ModelSerializer):
    problem_id = serializers.PrimaryKeyRelatedField(
        queryset=Problem.objects.all(), source="problem", write_only=True
    )
    problem = ProblemListSerializer(read_only=True)

    class Meta:
        model = DailyProblem
        fields = ["id", "date", "problem", "problem_id"]


class AdminPracticeListSerializer(serializers.ModelSerializer):
    """Practice lists are edited as an ordered list of problem ids."""

    problem_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Problem.objects.all(),
        write_only=True,
        required=False,
        help_text="Problem ids in display order.",
    )
    problem_count = serializers.SerializerMethodField()
    # The list's problems in display order (what `problem_ids` writes).
    problems = serializers.SerializerMethodField()

    class Meta:
        model = ProblemList
        fields = [
            "id", "slug", "title", "description_md", "is_published",
            "order_index", "problem_ids", "problem_count", "problems",
        ]
        extra_kwargs = {"slug": {"required": False}}

    def get_problem_count(self, obj):
        return len(obj.items.all())

    def get_problems(self, obj):
        items = sorted(obj.items.all(), key=lambda item: (item.order_index, item.id))
        return [
            {
                "id": item.problem_id,
                "slug": item.problem.slug,
                "title": item.problem.title,
                "number": item.problem.number,
                "difficulty": item.problem.difficulty,
                "is_published": item.problem.is_published,
            }
            for item in items
        ]

    def validate_problem_ids(self, problems):
        ids = [problem.pk for problem in problems]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("A problem can appear only once in a list.")
        return problems

    def validate(self, data):
        # Blank slugs follow the title, like Django admin's prepopulated field.
        if not data.get("slug") and data.get("title") and self.instance is None:
            from apps.core.slugs import unique_slug

            data["slug"] = unique_slug(ProblemList, data["title"])
        return data

    def _sync_items(self, instance, problem_ids):
        instance.items.all().delete()
        ProblemListItem.objects.bulk_create([
            ProblemListItem(problem_list=instance, problem=problem, order_index=index)
            for index, problem in enumerate(problem_ids)
        ])

    def create(self, validated_data):
        problem_ids = validated_data.pop("problem_ids", [])
        instance = super().create(validated_data)
        self._sync_items(instance, problem_ids)
        return instance

    def update(self, instance, validated_data):
        problem_ids = validated_data.pop("problem_ids", None)
        instance = super().update(instance, validated_data)
        if problem_ids is not None:
            self._sync_items(instance, problem_ids)
        return instance

