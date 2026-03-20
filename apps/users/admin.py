from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserSolvedProblem


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "role", "plan", "is_active", "is_banned", "problems_solved"]
    list_filter = ["role", "plan", "is_active", "is_banned", "created_at"]
    search_fields = ["username", "email", "display_name"]
    readonly_fields = ["created_at", "updated_at", "last_login"]
    
    fieldsets = (
        ("Basic Info", {
            "fields": ("username", "email", "display_name", "avatar_url", "bio")
        }),
        ("Status", {
            "fields": ("role", "plan", "plan_expires_at", "is_active", "is_banned", "banned_reason")
        }),
        ("Stats", {
            "fields": ("problems_solved", "current_streak", "last_active_date")
        }),
        ("Permissions", {
            "fields": ("is_staff", "is_superuser", "groups", "user_permissions")
        }),
        ("Dates", {
            "fields": ("created_at", "updated_at", "last_login"),
            "classes": ("collapse",)
        }),
    )
    ordering = ["-created_at"]


@admin.register(UserSolvedProblem)
class UserSolvedProblemAdmin(admin.ModelAdmin):
    list_display = ["user", "problem", "solved_at", "best_runtime_ms", "best_memory_kb"]
    list_filter = ["solved_at", "problem"]
    search_fields = ["user__username", "problem__slug"]
    readonly_fields = ["solved_at"]
    ordering = ["-solved_at"]
