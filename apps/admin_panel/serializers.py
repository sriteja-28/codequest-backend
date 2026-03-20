from rest_framework import serializers


class AdminUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    plan = serializers.CharField()
    is_active = serializers.BooleanField()


class AdminStatisticsSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    total_problems = serializers.IntegerField()
    total_submissions = serializers.IntegerField()
    total_contests = serializers.IntegerField()


class AdminSettingsSerializer(serializers.Serializer):
    site_name = serializers.CharField(max_length=100)
    maintenance_mode = serializers.BooleanField()
    max_problem_limit = serializers.IntegerField()
