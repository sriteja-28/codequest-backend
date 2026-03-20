from django.contrib import admin
from .models import Contest, ContestProblem, ContestParticipant


@admin.register(Contest)
class ContestAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "start_at", "end_at", "is_public", "is_rated", "status"]
    list_filter = ["is_public", "is_rated", "start_at"]
    search_fields = ["name", "slug"]
    readonly_fields = ["created_at", "updated_at", "status"]
    ordering = ["-start_at"]


@admin.register(ContestProblem)
class ContestProblemAdmin(admin.ModelAdmin):
    list_display = ["contest", "problem", "order_index", "score"]
    list_filter = ["contest"]
    search_fields = ["contest__slug", "problem__slug"]
    ordering = ["contest", "order_index"]


@admin.register(ContestParticipant)
class ContestParticipantAdmin(admin.ModelAdmin):
    list_display = ["user", "contest", "registered_at", "final_score", "rank", "is_disqualified"]
    list_filter = ["contest", "is_disqualified", "registered_at"]
    search_fields = ["user__username", "contest__slug"]
    readonly_fields = ["registered_at"]
    ordering = ["-registered_at"]
