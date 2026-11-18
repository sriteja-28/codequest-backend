from rest_framework import serializers

from .models import AdCreative, AdPlacement, ContentPage


class ContentPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentPage
        fields = ["id", "slug", "title", "content", "published", "order_index", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"slug": {"required": False}}

    def validate(self, data):
        if self.instance is None and not data.get("slug") and data.get("title"):
            from apps.core.slugs import unique_slug
            data["slug"] = unique_slug(ContentPage, data["title"])
        return data


def validate_link(value: str) -> str:
    """Absolute http(s) URL or a site-relative path; never javascript:/data: URLs."""
    value = (value or "").strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    if value.lower().startswith(("http://", "https://")):
        return value
    raise serializers.ValidationError("Use an http(s):// URL or a site-relative path such as /upgrade.")


class AdCreativePublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdCreative
        fields = ["id", "name", "html_snippet", "image_url", "link_url", "plan_target", "priority"]


class AdCreativeAdminSerializer(serializers.ModelSerializer):
    link_url = serializers.CharField(max_length=200, validators=[validate_link])
    image_url = serializers.CharField(max_length=200, required=False, allow_blank=True)

    class Meta:
        model = AdCreative
        fields = [
            "id", "name", "html_snippet", "image_url", "link_url",
            "start_at", "end_at", "plan_target", "priority", "is_active", "placement",
        ]

    def validate_image_url(self, value):
        return validate_link(value) if value else value

    def validate(self, data):
        start = data.get("start_at", getattr(self.instance, "start_at", None))
        end = data.get("end_at", getattr(self.instance, "end_at", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_at": "end_at must be after start_at."})
        return data


class AdPlacementAdminSerializer(serializers.ModelSerializer):
    creative_count = serializers.SerializerMethodField()

    class Meta:
        model = AdPlacement
        fields = ["id", "key", "position", "description", "is_active", "max_per_page", "creative_count"]

    def get_creative_count(self, obj):
        return obj.creatives.count()
