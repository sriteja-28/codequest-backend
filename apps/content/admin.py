from django.contrib import admin
from .models import ContentPage


@admin.register(ContentPage)
class ContentPageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "published", "order_index", "updated_at"]
    list_filter = ["published", "created_at"]
    search_fields = ["title", "slug", "content"]
    readonly_fields = ["created_at", "updated_at"]
    prepopulated_fields = {"slug": ("title",)}
