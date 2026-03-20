from rest_framework import serializers


class AIHintRequestSerializer(serializers.Serializer):
    problem_id = serializers.IntegerField()
    difficulty = serializers.CharField(max_length=20, required=False)


class AIHintResponseSerializer(serializers.Serializer):
    hint = serializers.CharField()
    level = serializers.IntegerField()


class AIChatRequestSerializer(serializers.Serializer):
    problem_id = serializers.IntegerField()
    message = serializers.CharField(max_length=2000)


class AIChatResponseSerializer(serializers.Serializer):
    response = serializers.CharField()
    tokens_used = serializers.IntegerField()
