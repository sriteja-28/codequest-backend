from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import SocialIdentity, User, UserDailyActivity, UserSolvedProblem


class SocialIdentityInline(admin.TabularInline):
    model = SocialIdentity
    extra = 0
    fields = ["provider", "subject", "email", "email_verified", "display_name", "last_login_at"]
    readonly_fields = ["created_at", "last_login_at"]
    ordering = ["provider"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "role", "plan", "is_active", "is_banned", "problems_solved"]
    list_filter = ["role", "plan", "is_active", "is_banned", "created_at"]
    search_fields = ["username", "email", "display_name"]
    readonly_fields = ["created_at", "updated_at", "last_login"]
    inlines = [SocialIdentityInline]

    fieldsets = (
        ("Basic Info", {
            "fields": ("username", "email", "display_name", "avatar_url", "bio")
        }),
        ("Status", {
            "fields": ("role", "plan", "plan_expires_at", "is_active", "is_banned", "banned_reason")
        }),
        ("Stats", {
            "fields": ("problems_solved", "current_streak", "best_streak", "last_active_date")
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


@admin.register(SocialIdentity)
class SocialIdentityAdmin(admin.ModelAdmin):
    list_display = ["provider", "email", "user", "email_verified", "last_login_at", "created_at"]
    list_filter = ["provider", "email_verified", "created_at"]
    search_fields = ["subject", "email", "user__username", "user__email"]
    readonly_fields = ["created_at", "last_login_at"]
    raw_id_fields = ["user"]
    ordering = ["provider", "email"]


@admin.register(UserSolvedProblem)
class UserSolvedProblemAdmin(admin.ModelAdmin):
    list_display = ["user", "problem", "solved_at", "best_runtime_ms", "best_memory_kb"]
    list_filter = ["solved_at", "problem"]
    search_fields = ["user__username", "problem__slug"]
    readonly_fields = ["solved_at"]
    ordering = ["-solved_at"]


@admin.register(UserDailyActivity)
class UserDailyActivityAdmin(admin.ModelAdmin):
    list_display = ["user", "date", "submissions", "accepted"]
    list_filter = ["date"]
    search_fields = ["user__username", "user__email"]
    ordering = ["-date"]
