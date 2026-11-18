from rest_framework import serializers


class _ProblemRefSerializer(serializers.Serializer):
    """Accepts the frontend's problem_slug (preferred) or a numeric problem_id."""

    problem_slug = serializers.SlugField(required=False)
    problem_id = serializers.IntegerField(required=False, min_value=1)

    def validate(self, data):
        if not data.get("problem_slug") and not data.get("problem_id"):
            raise serializers.ValidationError({"problem_slug": "This field is required."})
        return data


class AIHintRequestSerializer(_ProblemRefSerializer):
    contest = serializers.IntegerField(required=False, min_value=1)
    hint_level = serializers.IntegerField(required=False, min_value=0, max_value=50, default=0)
    user_code = serializers.CharField(required=False, allow_blank=True, max_length=65536, trim_whitespace=False)

    def validate(self, data):
        data = super().validate(data)
        if data.get("contest") and not data.get("problem_slug"):
            raise serializers.ValidationError({"problem_slug": "Required with contest."})
        return data


class AIHintResponseSerializer(serializers.Serializer):
    hint = serializers.CharField()
    level = serializers.IntegerField()
    has_more = serializers.BooleanField()
    next_requires_pro = serializers.BooleanField()
    used_today = serializers.IntegerField()
    daily_limit = serializers.IntegerField()
    source = serializers.CharField()


class AIChatRequestSerializer(_ProblemRefSerializer):
    message = serializers.CharField(max_length=2000)
    conversation_id = serializers.CharField(required=False, allow_blank=True, max_length=64)


class AICodeRequestSerializer(serializers.Serializer):
    problem_slug = serializers.SlugField(required=False)
    code = serializers.CharField(max_length=65536, trim_whitespace=False)
    language = serializers.ChoiceField(choices=["python", "cpp", "java", "javascript"])
