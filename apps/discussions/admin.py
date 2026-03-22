"""
apps/discussions/admin.py

Admin interface for discussion threads and comments.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import DiscussionThread, DiscussionComment, ThreadUpvote, CommentUpvote


@admin.register(DiscussionThread)
class DiscussionThreadAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title', 'problem', 'author_display', 
        'upvote_count_display', 'comment_count_display', 
        'view_count', 'is_pinned', 'is_locked', 'is_anonymous',
        'created_at'
    ]
    list_filter = ['is_pinned', 'is_locked', 'is_anonymous', 'created_at']
    search_fields = ['title', 'content', 'author__username', 'problem__title']
    readonly_fields = ['view_count', 'created_at', 'updated_at']
    list_editable = ['is_pinned', 'is_locked']
    
    fieldsets = (
        ('Thread Info', {
            'fields': ('problem', 'author', 'title', 'content')
        }),
        ('Settings', {
            'fields': ('is_anonymous', 'is_pinned', 'is_locked')
        }),
        ('Stats', {
            'fields': ('view_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def author_display(self, obj):
        """Display author with anonymous indicator."""
        if obj.is_anonymous:
            return format_html(
                '<span style="color: #999;">{} <em>(Anonymous)</em></span>',
                obj.author.username
            )
        return obj.author.username
    author_display.short_description = 'Author'
    
    def upvote_count_display(self, obj):
        """Display upvote count (can't use reverse FK directly in list_display)."""
        count = obj.upvote_count
        return format_html(
            '<span style="color: #0066cc;">👍 {}</span>',
            count
        )
    upvote_count_display.short_description = 'Upvotes'
    
    def comment_count_display(self, obj):
        """Display comment count."""
        count = obj.comment_count
        return format_html(
            '<span style="color: #666;">💬 {}</span>',
            count
        )
    comment_count_display.short_description = 'Comments'


@admin.register(DiscussionComment)
class DiscussionCommentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'thread', 'author_display', 
        'upvote_count_display', 'is_accepted_answer',
        'is_anonymous', 'is_flagged', 'is_hidden',
        'created_at'
    ]
    list_filter = [
        'is_accepted_answer', 'is_flagged', 'is_hidden', 
        'is_anonymous', 'created_at'
    ]
    search_fields = ['content', 'author__username', 'thread__title']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_accepted_answer', 'is_flagged', 'is_hidden']
    
    fieldsets = (
        ('Comment Info', {
            'fields': ('thread', 'author', 'parent', 'content')
        }),
        ('Settings', {
            'fields': ('is_anonymous', 'is_accepted_answer', 'is_flagged', 'is_hidden')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def author_display(self, obj):
        """Display author with anonymous indicator."""
        if obj.is_anonymous:
            return format_html(
                '<span style="color: #999;">{} <em>(Anon)</em></span>',
                obj.author.username
            )
        return obj.author.username
    author_display.short_description = 'Author'
    
    def upvote_count_display(self, obj):
        """Display upvote count (property, not direct field)."""
        count = obj.upvote_count
        color = '#0066cc' if count > 0 else '#999'
        return format_html(
            '<span style="color: {};">👍 {}</span>',
            color, count
        )
    upvote_count_display.short_description = 'Upvotes'


@admin.register(ThreadUpvote)
class ThreadUpvoteAdmin(admin.ModelAdmin):
    list_display = ['id', 'thread', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['thread__title', 'user__username']
    readonly_fields = ['created_at']


@admin.register(CommentUpvote)
class CommentUpvoteAdmin(admin.ModelAdmin):
    list_display = ['id', 'comment', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['comment__content', 'user__username']
    readonly_fields = ['created_at']