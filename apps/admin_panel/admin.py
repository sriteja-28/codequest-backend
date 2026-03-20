from django.contrib import admin
from .models import AdminLog, PlatformSettings


@admin.register(AdminLog)
class AdminLogAdmin(admin.ModelAdmin):
    list_display = ["admin", "action", "object_type", "created_at"]
    list_filter = ["action", "object_type", "created_at"]
    search_fields = ["admin__username", "description"]
    readonly_fields = ["created_at"]


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ["site_name", "maintenance_mode", "updated_at"]
    readonly_fields = ["updated_at"]
