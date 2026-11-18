from django.conf import settings
from rest_framework import serializers

from apps.users.models import User

from .models import AdminLog, PlatformSettings


class AdminUserSerializer(serializers.ModelSerializer):
    """User row for /api/admin/users/ (admin only)."""

    is_pro = serializers.BooleanField(read_only=True)
    # Annotated by the list view; absent on single-user responses.
    submission_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "display_name", "avatar_url",
            "role", "plan", "is_pro", "plan_expires_at",
            "is_active", "is_banned", "banned_reason",
            "problems_solved", "current_streak", "best_streak", "submission_count",
            "last_login", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_submission_count(self, obj):
        return getattr(obj, "submission_count", None)


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Fields an admin may change via PATCH /api/admin/users/{id}/.
    Plan changes go through PATCH /api/billing/admin/users/{id}/plan/."""

    class Meta:
        model = User
        fields = ["role", "is_active", "is_banned", "banned_reason", "display_name"]

    def validate(self, data):
        request = self.context["request"]
        target = self.instance
        if target is not None and target.pk == request.user.pk:
            if data.get("role", target.role) != User.Role.ADMIN:
                raise serializers.ValidationError({"role": "You cannot remove your own admin role."})
            if data.get("is_banned") or data.get("is_active") is False:
                raise serializers.ValidationError({"detail": "You cannot ban or deactivate yourself."})
        if data.get("is_banned") is False:
            data.setdefault("banned_reason", "")
        return data


class PlatformSettingsSerializer(serializers.ModelSerializer):
    """GET/PATCH /api/admin/settings/ (the single settings row)."""

    # Shown as placeholders: what blank quota fields fall back to.
    hint_defaults = serializers.SerializerMethodField()

    class Meta:
        model = PlatformSettings
        fields = [
            "site_name", "site_description",
            "announcement_text", "announcement_level",
            "maintenance_mode", "maintenance_message",
            "ai_hints_free_daily", "ai_hints_pro_daily", "hint_defaults",
            "contest_recent_days", "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def get_hint_defaults(self, obj):
        return {"free": settings.AI_HINTS_FREE_DAILY, "pro": settings.AI_HINTS_PRO_DAILY}

    def validate_site_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("The site needs a name.")
        return value


class AdminLogSerializer(serializers.ModelSerializer):
    admin = serializers.SerializerMethodField()

    class Meta:
        model = AdminLog
        fields = [
            "id", "created_at", "action", "object_type", "object_id", "object_repr",
            "description", "changes", "source", "admin",
        ]

    def get_admin(self, obj):
        if obj.admin_id is None:
            return None
        user = obj.admin
        return {"id": user.id, "username": user.username, "display_name": user.display_name}


class FeatureOverrideSerializer(serializers.Serializer):
    """`enabled`: true/false to override the registry default, null to reset it."""

    enabled = serializers.BooleanField(allow_null=True)
