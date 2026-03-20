from django.contrib import admin
from .models import DiscussionThread, DiscussionComment


@admin.register(DiscussionThread)
class DiscussionThreadAdmin(admin.ModelAdmin):
    list_display = ["title", "problem", "author", "created_at", "is_pinned", "is_locked"]
    list_filter = ["is_pinned", "is_locked", "created_at"]
    search_fields = ["title", "content", "author__username"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(DiscussionComment)
class DiscussionCommentAdmin(admin.ModelAdmin):
    list_display = ["author", "thread", "created_at", "upvotes", "is_accepted_answer"]
    list_filter = ["is_accepted_answer", "created_at"]
    search_fields = ["content", "author__username"]
    readonly_fields = ["created_at", "updated_at"]
