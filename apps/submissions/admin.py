from django.contrib import admin
from .models import Submission, SubmissionResult


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ["user", "problem", "language", "status", "created_at", "runtime_ms", "memory_kb"]
    list_filter = ["status", "language", "created_at"]
    search_fields = ["user__username", "problem__slug", "id"]
    readonly_fields = ["created_at", "judge_started_at", "judge_finished_at", "id"]
    ordering = ["-created_at"]


@admin.register(SubmissionResult)
class SubmissionResultAdmin(admin.ModelAdmin):
    list_display = ["submission", "test_case", "status", "time_ms", "memory_kb"]
    list_filter = ["status", "submission__created_at"]
    search_fields = ["submission__id", "test_case__problem__slug"]
    ordering = ["submission", "test_case__order_index"]
