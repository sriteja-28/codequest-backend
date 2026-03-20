from django.contrib import admin
from .models import AIInteraction


@admin.register(AIInteraction)
class AIInteractionAdmin(admin.ModelAdmin):
    list_display = ["user", "interaction_type", "problem", "tokens_used", "created_at"]
    list_filter = ["interaction_type", "created_at"]
    search_fields = ["user__username", "problem__slug", "query"]
    readonly_fields = ["created_at"]
