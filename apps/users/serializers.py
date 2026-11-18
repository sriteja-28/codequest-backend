from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import SocialIdentity, User


class DevLoginSerializer(serializers.Serializer):
    """Email + password sign-in for local development only (DEBUG-gated view)."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, data):
        request = self.context.get("request")
        user = authenticate(request=request, username=data["email"], password=data["password"])
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is deactivated.")
        if user.is_banned:
            raise serializers.ValidationError("This account is suspended.")
        data["user"] = user
        return data


class SocialIdentitySerializer(serializers.ModelSerializer):
    provider_display = serializers.CharField(source="get_provider_display", read_only=True)

    class Meta:
        model = SocialIdentity
        fields = [
            "id", "provider", "provider_display", "email", "email_verified",
            "display_name", "avatar_url", "created_at", "last_login_at",
        ]
        read_only_fields = fields


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
