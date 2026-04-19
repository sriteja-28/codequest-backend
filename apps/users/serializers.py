from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "username", "password", "password_confirm", "display_name"]

    def validate(self, data):
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data["email"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        if not user.is_active:
            raise serializers.ValidationError("Account is deactivated.")
        if user.is_banned:
            raise serializers.ValidationError("Account is banned.")
        data["user"] = user
        return data


class UserPublicSerializer(serializers.ModelSerializer):
    """Safe public representation — no sensitive fields."""
    class Meta:
        model = User
        fields = [
            "id", "username", "display_name", "avatar_url", "bio",
            "plan", "role", "problems_solved", "current_streak",
            "created_at",
        ]
        read_only_fields = fields


class UserMeSerializer(serializers.ModelSerializer):
    """Full representation for the authenticated user themselves."""
    is_pro = serializers.BooleanField(read_only=True)
    ai_hint_limit = serializers.IntegerField(source="get_ai_hint_limit", read_only=True)
    ai_chat_limit = serializers.IntegerField(source="get_ai_chat_limit", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "display_name", "avatar_url", "bio",
            "role", "plan", "is_pro", "plan_expires_at",
            "problems_solved", "current_streak", "best_streak", "last_active_date",
            "ai_hint_limit", "ai_chat_limit",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "email", "role", "plan", "is_pro", "plan_expires_at",
                            "problems_solved", "current_streak", "best_streak", "last_active_date",
                            "ai_hint_limit", "ai_chat_limit", "created_at", "updated_at"]


class UserAdminSerializer(serializers.ModelSerializer):
    """Admin-level serializer with all fields."""
    class Meta:
        model = User
        fields = [
            "id", "email", "username", "display_name", "avatar_url",
            "role", "plan", "plan_expires_at",
            "is_active", "is_banned", "banned_reason",
            "problems_solved", "current_streak",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "email", "created_at", "updated_at"]