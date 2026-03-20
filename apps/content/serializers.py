from rest_framework import serializers
from .models import ContentPage


class ContentPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentPage
        fields = ["id", "slug", "title", "content", "published", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
