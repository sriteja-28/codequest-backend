from django.contrib import admin
from .forms import SectionAdminForm, TestCaseAdminForm
from .models import (
    DailyProblem,
    Problem,
    ProblemList,
    ProblemListItem,
    Section,
    Star,
    Tag,
    TestCase,
    Solution,
    ProblemTag,
)


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    form = SectionAdminForm
    list_display = ["display_name", "name", "slug", "order_index"]
    search_fields = ["display_name", "name", "slug"]
    ordering = ["order_index"]
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ["prerequisites"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "tag_type", "slug"]
    list_filter = ["tag_type"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


class TestCaseInline(admin.StackedInline):
    form = TestCaseAdminForm
    model = TestCase
    extra = 0
    fields = [("order_index", "is_sample", "is_hidden"), "input_data", "expected_output", "explanation"]
    ordering = ["order_index", "id"]
    classes = ["collapse"]


class SolutionInline(admin.StackedInline):
    model = Solution
    extra = 0
    fields = [
        ("title", "order_index", "is_official", "visibility"),
        "approach_summary_md",
        ("time_complexity", "space_complexity"),
        "code_python", "code_cpp", "code_java", "code_javascript",
    ]
    ordering = ["order_index", "id"]
    classes = ["collapse"]


class ProblemTagInline(admin.TabularInline):
    """Tags use the ProblemTag through model, so they are edited as rows here."""

    model = ProblemTag
    extra = 0
    autocomplete_fields = ["tag"]
    verbose_name = "tag"
    verbose_name_plural = "tags"


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "number", "difficulty", "section", "is_published"]
    list_filter = ["difficulty", "section", "is_published", "created_at"]
    search_fields = ["title", "slug"]
    readonly_fields = ["created_at", "updated_at", "acceptance_rate"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ProblemTagInline, TestCaseInline, SolutionInline]
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
        ("Judge", {
            "fields": ("function_signature", "compare_mode", "float_tolerance"),
            "description": (
                "Function-only problems parse test-case input by parameter name and compare the "
                "returned value. Leave the signature empty for legacy stdin/stdout problems."
            ),
        }),
        ("Starter code (optional overrides)", {
            "fields": ("starter_code_python", "starter_code_cpp", "starter_code_java", "starter_code_javascript"),
            "classes": ("collapse",),
            "description": "Blank fields are generated from the function signature in the API.",
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
    form = TestCaseAdminForm
    list_display = ["problem", "order_index", "is_sample", "is_hidden"]
    list_filter = ["is_sample", "is_hidden"]
    search_fields = ["problem__slug", "problem__title"]
    autocomplete_fields = ["problem"]
    ordering = ["problem", "order_index"]


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ["problem", "title", "is_official", "visibility", "order_index"]
    list_filter = ["is_official", "visibility"]
    search_fields = ["problem__slug", "title"]
    autocomplete_fields = ["problem"]
    ordering = ["problem", "order_index"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ProblemTag)
class ProblemTagAdmin(admin.ModelAdmin):
    list_display = ["problem", "tag"]
    list_filter = ["tag"]
    search_fields = ["problem__slug", "tag__name"]
    autocomplete_fields = ["problem", "tag"]


class ProblemListItemInline(admin.TabularInline):
    model = ProblemListItem
    extra = 0
    fields = ["problem", "order_index"]
    autocomplete_fields = ["problem"]
    ordering = ["order_index", "id"]


@admin.register(ProblemList)
class ProblemListAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "is_published", "order_index", "updated_at"]
    list_filter = ["is_published"]
    search_fields = ["title", "slug"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ProblemListItemInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Star)
class StarAdmin(admin.ModelAdmin):
    list_display = ["user", "problem", "created_at"]
    search_fields = ["user__email", "problem__slug", "problem__title"]
    autocomplete_fields = ["problem"]
    readonly_fields = ["created_at"]


@admin.register(DailyProblem)
class DailyProblemAdmin(admin.ModelAdmin):
    list_display = ["date", "problem", "created_at"]
    date_hierarchy = "date"
    search_fields = ["problem__slug", "problem__title"]
    autocomplete_fields = ["problem"]
    readonly_fields = ["created_at"]
