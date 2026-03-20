from django.contrib import admin
from .models import Problem, Section, Tag, TestCase, Solution, ProblemTag


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ["display_name", "name", "order_index"]
    list_filter = ["name"]
    search_fields = ["display_name"]
    ordering = ["order_index"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "tag_type", "slug"]
    list_filter = ["tag_type"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "number", "difficulty", "section", "is_published"]
    list_filter = ["difficulty", "section", "is_published", "created_at"]
    search_fields = ["title", "slug"]
    readonly_fields = ["created_at", "updated_at", "acceptance_rate"]
    fieldsets = (
        ("Basic Info", {
            "fields": ("title", "slug", "number", "difficulty", "visibility", "section")
        }),
        ("Content", {
            "fields": ("statement_md", "hints_md")
        }),
        ("Complexity", {
            "fields": ("time_complexity_best", "time_complexity_average", "time_complexity_worst", "space_complexity", "complexity_notes_md")
        }),
        ("Stats", {
            "fields": ("total_submissions", "accepted_submissions", "acceptance_rate", "is_published")
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ["problem", "order_index", "is_sample", "is_hidden"]
    list_filter = ["problem", "is_sample", "is_hidden"]
    search_fields = ["problem__slug"]
    ordering = ["problem", "order_index"]


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ["problem", "title", "is_official", "visibility", "order_index"]
    list_filter = ["problem", "is_official", "visibility"]
    search_fields = ["problem__slug", "title"]
    ordering = ["problem", "order_index"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ProblemTag)
class ProblemTagAdmin(admin.ModelAdmin):
    list_display = ["problem", "tag"]
    list_filter = ["tag"]
    search_fields = ["problem__slug", "tag__name"]
