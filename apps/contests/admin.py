from django.contrib import admin, messages
from django.utils import timezone

from .finalize import FINALIZED, finalize_contest
from .models import Contest, ContestParticipant, ContestProblem


def _started(contest) -> bool:
    return bool(contest and contest.start_at and contest.start_at <= timezone.now())


class ContestProblemInline(admin.TabularInline):
    """The problem set is locked once the contest starts (same rule as the admin API)."""

    model = ContestProblem
    extra = 0
    autocomplete_fields = ["problem"]
    fields = ["order_index", "problem", "score"]
    ordering = ["order_index"]

    def has_add_permission(self, request, obj=None):
        return not _started(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not _started(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not _started(obj) and super().has_delete_permission(request, obj)


class ContestParticipantInline(admin.TabularInline):
    """Read-only standings overview; corrections go through the participant admin."""

    model = ContestParticipant
    extra = 0
    fields = ["user", "rank", "final_score", "score_adjustment", "is_disqualified", "registered_at"]
    readonly_fields = fields
    ordering = ["rank", "-final_score"]
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Contest)
class ContestAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "start_at", "end_at", "status", "finalized", "is_public", "is_rated"]
    list_filter = ["is_public", "is_rated", "start_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created_at", "updated_at", "status", "finalized_at"]
    ordering = ["-start_at"]
    inlines = [ContestProblemInline, ContestParticipantInline]
    actions = ["finalize_now"]
    fieldsets = [
        (None, {"fields": ["name", "slug", "description_md"]}),
        ("Schedule", {"fields": ["start_at", "end_at", "status"]}),
        ("Options", {"fields": ["is_public", "is_rated", "max_participants", "release_problems"]}),
        ("Lifecycle", {"fields": ["finalized_at", "created_at", "updated_at"]}),
    ]

    @admin.display(boolean=True, description="Finalized")
    def finalized(self, obj):
        return obj.is_finalized

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_finalized:
            fields += ["start_at", "end_at", "release_problems"]
        return fields

    @admin.action(description="Finalize selected ended contests now (freeze standings, release problems)")
    def finalize_now(self, request, queryset):
        done, skipped = [], []
        for contest in queryset:
            result = finalize_contest(contest, force=True, actor=request.user, source="django")
            (done if result.outcome == FINALIZED else skipped).append(f"{contest.slug} ({result.outcome})")
        if done:
            self.message_user(request, f"Finalized: {', '.join(done)}", messages.SUCCESS)
        if skipped:
            self.message_user(request, f"Skipped: {', '.join(skipped)}", messages.WARNING)


class FrozenContestRelationAdmin(admin.ModelAdmin):
    """Rows of a contest that become read-only at some point of its lifecycle."""

    def locked(self, contest) -> bool:
        return contest.is_finalized

    def has_change_permission(self, request, obj=None):
        return not (obj and self.locked(obj.contest)) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # No bulk delete: it cannot check each row's contest.
        return bool(obj and not self.locked(obj.contest)) and super().has_delete_permission(request, obj)


@admin.register(ContestProblem)
class ContestProblemAdmin(FrozenContestRelationAdmin):
    list_display = ["contest", "problem", "order_index", "score"]
    list_filter = ["contest"]
    search_fields = ["contest__slug", "problem__slug"]
    autocomplete_fields = ["problem"]
    ordering = ["contest", "order_index"]

    def locked(self, contest):
        return _started(contest)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "contest":
            kwargs["queryset"] = Contest.objects.filter(start_at__gt=timezone.now())
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ContestParticipant)
class ContestParticipantAdmin(FrozenContestRelationAdmin):
    list_display = ["user", "contest", "registered_at", "final_score", "score_adjustment", "rank", "is_disqualified"]
    list_filter = ["contest", "is_disqualified", "registered_at"]
    search_fields = ["user__username", "contest__slug"]
    readonly_fields = ["registered_at", "final_score", "rank"]
    ordering = ["-registered_at"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "contest":
            kwargs["queryset"] = Contest.objects.filter(finalized_at__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # Django admin edits go through the same rescoring as the API.
        from .scoring import recalculate_ranks, recalculate_score

        super().save_model(request, obj, form, change)
        recalculate_score(obj)
        recalculate_ranks(obj.contest)
        ContestParticipant.objects.filter(contest=obj.contest, is_disqualified=True).update(rank=None)
