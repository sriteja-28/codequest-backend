from django.contrib import admin

from .models import Category, Chapter, Course, Lesson, LessonProgress


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "order_index"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 0
    fields = ["title", "order_index", "description_md"]
    ordering = ["order_index", "id"]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "category", "difficulty", "is_published", "order_index"]
    list_filter = ["is_published", "difficulty", "category"]
    search_fields = ["title", "slug", "subtitle"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ChapterInline]
    readonly_fields = ["created_at", "updated_at"]


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ["title", "slug", "problem", "estimated_minutes", "is_published", "order_index"]
    autocomplete_fields = ["problem"]
    ordering = ["order_index", "id"]


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ["title", "course", "order_index"]
    list_filter = ["course"]
    search_fields = ["title", "course__title"]
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ["title", "chapter", "problem", "is_published", "order_index"]
    list_filter = ["is_published", "chapter__course"]
    search_fields = ["title", "slug", "chapter__title", "chapter__course__title"]
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ["problem"]


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "lesson", "completed_at"]
    list_filter = ["lesson__chapter__course"]
    search_fields = ["user__email", "lesson__title", "lesson__slug"]
    readonly_fields = ["completed_at"]
