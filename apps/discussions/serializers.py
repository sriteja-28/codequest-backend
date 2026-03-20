from rest_framework import serializers
from .models import DiscussionThread, DiscussionComment
from apps.problems.models import Problem


class DiscussionCommentSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)
    thread = serializers.PrimaryKeyRelatedField(queryset=DiscussionThread.objects.all())

    class Meta:
        model = DiscussionComment
        fields = ["id", "thread", "author", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]


class DiscussionThreadSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)
    problem = serializers.PrimaryKeyRelatedField(queryset=Problem.objects.all())
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionThread
        fields = ["id", "problem", "title", "content", "author", "comment_count", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]

    def get_comment_count(self, obj):
        return obj.comments.count()


class DiscussionThreadDetailSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)
    comments = DiscussionCommentSerializer(many=True, read_only=True)

    class Meta:
        model = DiscussionThread
        fields = ["id", "problem", "title", "content", "author", "comments", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]
