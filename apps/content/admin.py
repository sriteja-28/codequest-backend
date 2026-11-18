from django.contrib import admin
from django import forms
from apps.core.features import FEATURES, FEATURES_BY_KEY
from .models import AdCreative, AdPlacement, ContentPage, FeatureFlag


@admin.register(ContentPage)
class ContentPageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "published", "order_index", "updated_at"]
    list_filter = ["published", "created_at"]
    search_fields = ["title", "slug", "content"]
    readonly_fields = ["created_at", "updated_at"]
    prepopulated_fields = {"slug": ("title",)}


class CreativeInline(admin.StackedInline):
    model = AdCreative
    extra = 0
    show_change_link = True


@admin.register(AdPlacement)
class AdPlacementAdmin(admin.ModelAdmin):
    list_display = ["key", "position", "is_active", "max_per_page"]
    search_fields = ["key", "position"]
    inlines = [CreativeInline]


@admin.register(AdCreative)
class AdCreativeAdmin(admin.ModelAdmin):
    list_display = ["name", "placement", "plan_target", "priority", "is_active"]
    list_filter = ["is_active", "plan_target", "placement"]
    search_fields = ["name"]


class FeatureFlagForm(forms.ModelForm):
    key = forms.ChoiceField(choices=[(f.key, f.label) for f in FEATURES if f.implemented])

    class Meta:
        model = FeatureFlag
        fields = ["key", "value", "description"]

    def clean_key(self):
        key = self.cleaned_data["key"]
        if key not in FEATURES_BY_KEY or not FEATURES_BY_KEY[key].implemented:
            raise forms.ValidationError("Only implemented registry features can be overridden.")
        return key


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    form = FeatureFlagForm
    list_display = ["key", "value", "description"]
    search_fields = ["key"]
