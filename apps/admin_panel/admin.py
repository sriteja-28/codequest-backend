from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import AdminLog, PlatformSettings


@admin.register(AdminLog)
class AdminLogAdmin(admin.ModelAdmin):
    """The audit trail is append-only: viewable here, written by apps.admin_panel.audit."""

    list_display = ["created_at", "admin", "action", "object_type", "object_repr", "source"]
    list_filter = ["action", "source", "object_type", "created_at"]
    search_fields = ["admin__username", "object_repr", "description"]
    readonly_fields = [
        "created_at", "admin", "action", "object_type", "object_id", "object_repr",
        "description", "changes", "source",
    ]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    """One settings row: the list view opens it directly; it cannot be added twice or deleted."""

    readonly_fields = ["updated_at"]
    fieldsets = [
        ("Site", {"fields": ["site_name", "site_description"]}),
        ("Banners", {"fields": ["announcement_text", "announcement_level", "maintenance_mode", "maintenance_message"]}),
        ("Limits", {"fields": ["ai_hints_free_daily", "ai_hints_pro_daily"]}),
        ("Contests", {"fields": ["contest_recent_days"]}),
        ("Metadata", {"fields": ["updated_at"]}),
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        settings_row = PlatformSettings.load()
        return redirect(reverse("admin:admin_panel_platformsettings_change", args=[settings_row.pk]))
