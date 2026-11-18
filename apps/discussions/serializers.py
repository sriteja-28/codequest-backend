"""
apps/discussions/serializers.py

Serializers that match frontend TypeScript types exactly.
Handles anonymous posting - shows real author to admins only.
"""

from rest_framework import serializers
from .models import DiscussionThread, DiscussionComment, ThreadUpvote, CommentUpvote
from apps.problems.models import Problem


class AdminThreadSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.username", read_only=True)
    problem_title = serializers.CharField(source="problem.title", read_only=True)

    class Meta:
        model = DiscussionThread
        fields = ["id", "title", "content", "problem", "problem_title", "author_name", "is_anonymous", "is_pinned", "is_locked", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class AdminCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.username", read_only=True)
    thread_title = serializers.CharField(source="thread.title", read_only=True)

    class Meta:
        model = DiscussionComment
        fields = ["id", "thread", "thread_title", "author_name", "content", "parent", "is_anonymous", "is_hidden", "is_flagged", "is_accepted_answer", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, data):
        thread = data.get("thread", getattr(self.instance, "thread", None))
        parent = data.get("parent", getattr(self.instance, "parent", None))
        if parent and (parent.thread_id != thread.pk or parent.pk == getattr(self.instance, "pk", None)):
            raise serializers.ValidationError({"parent": "Choose another comment in the same thread."})
        if self.instance and "thread" in data and thread.pk != self.instance.thread_id:
            raise serializers.ValidationError({"thread": "An existing comment cannot be moved to another thread."})
        if self.instance and "parent" in data and getattr(parent, "pk", None) != self.instance.parent_id:
            raise serializers.ValidationError({"parent": "An existing reply cannot be moved."})
        if data.get("is_hidden", getattr(self.instance, "is_hidden", False)):
            data["is_flagged"] = False
        return data


class DiscussionAuthorSerializer(serializers.Serializer):
    """
    Author info for discussions.
    If anonymous: shows "Anonymous" to regular users, real info to admins.
    """
    id = serializers.IntegerField()
    username = serializers.CharField()
    display_name = serializers.CharField()
    avatar_url = serializers.CharField()
    plan = serializers.CharField()


class DiscussionCommentSerializer(serializers.ModelSerializer):
    """Comment serializer matching frontend Comment type."""
    created_by = serializers.SerializerMethodField()
    body_md = serializers.CharField(source='content')  # Frontend expects body_md
    upvotes = serializers.SerializerMethodField()
    has_upvoted = serializers.SerializerMethodField()
    can_moderate = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionComment
        fields = [
            'id', 'thread', 'parent', 'body_md', 'created_by', 
            'created_at', 'updated_at', 'upvotes', 'has_upvoted',
            'is_accepted_answer', 'is_flagged', 'is_hidden', 
            'replies', 'can_moderate'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'upvotes', 'has_upvoted']

    def get_created_by(self, obj):
        """Return author info - Anonymous if is_anonymous=True and user is not admin."""
        request = self.context.get('request')
        user = request.user if request else None
        
        # Admins/moderators always see real author
        # if user and (user.role in ['ADMIN', 'MODERATOR']):
        if user and user.is_authenticated and getattr(user, "role", None) in ['ADMIN', 'MODERATOR']:

            return {
                'id': obj.author.id,
                'username': obj.author.username,
                'display_name': f"{obj.author.display_name} [Real Author]" if obj.is_anonymous else obj.author.display_name,
                'avatar_url': obj.author.avatar_url,
                'plan': obj.author.plan,
            }
        
        # Anonymous posting - hide real author from regular users
        if obj.is_anonymous:
            return {
                'id': 0,
                'username': 'anonymous',
                'display_name': 'Anonymous',
                'avatar_url': '/avatars/anonymous.png',
                'plan': 'FREE',
            }
        
        # Regular author display
        return {
            'id': obj.author.id,
            'username': obj.author.username,
            'display_name': obj.author.display_name,
            'avatar_url': obj.author.avatar_url,
            'plan': obj.author.plan,
        }

    def get_upvotes(self, obj):
        """Total upvote count."""
        # return obj.upvote_count
        return obj.upvotes.count()

    def get_has_upvoted(self, obj):
        """Check if current user has upvoted this comment."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.upvotes.filter(user=request.user).exists()

    def get_can_moderate(self, obj):
        """Check if user can moderate this comment."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        # return request.user.role in ['ADMIN', 'MODERATOR']
        return getattr(request.user, "role", None) in ['ADMIN', 'MODERATOR']

    def get_replies(self, obj):
        """Get nested replies."""
        replies = obj.replies.filter(is_hidden=False)
        return DiscussionCommentSerializer(replies, many=True, context=self.context).data


class ThreadListSerializer(serializers.ModelSerializer):
    """Thread serializer for list view - matching frontend Thread type."""
    created_by = serializers.SerializerMethodField()
    problem_slug = serializers.CharField(source='problem.slug', read_only=True)
    views = serializers.IntegerField(source='view_count', read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    # upvote_count = serializers.SerializerMethodField()
    # using annotated value instead of method
    upvote_count = serializers.IntegerField(read_only=True)
    has_upvoted = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionThread
        fields = [
            'id', 'problem_slug', 'title', 'content', 'created_by',
            'created_at', 'updated_at', 'is_pinned', 'is_locked',
            'views', 'comment_count', 'upvote_count', 'has_upvoted'
        ]
        read_only_fields = ['id', 'views', 'comment_count', 'created_at', 'updated_at']

    def get_created_by(self, obj):
        """Return author info - Anonymous if is_anonymous=True and user is not admin."""
        request = self.context.get('request')
        user = request.user if request else None
        
        # Admins/moderators always see real author
        # if user and user.is_authenticated and (user.role in ['ADMIN', 'MODERATOR']):
        if user and user.is_authenticated and getattr(user, "role", None) in ['ADMIN', 'MODERATOR']:
            return {
                'id': obj.author.id,
                'username': obj.author.username,
                'display_name': f"{obj.author.display_name} [Anon]" if obj.is_anonymous else obj.author.display_name,
                # 'avatar_url': obj.author.avatar_url,
                # 'plan': obj.author.plan,
                'avatar_url': getattr(obj.author, "avatar_url", ""),
                'plan': getattr(obj.author, "plan", "FREE"),
            }
        
        # Anonymous posting
        if obj.is_anonymous:
            return {
                'id': 0,
                'username': 'anonymous',
                'display_name': 'Anonymous',
                'avatar_url': '/avatars/anonymous.png',
                'plan': 'FREE',
            }
        
        # Regular author
        return {
            'id': obj.author.id,
            'username': obj.author.username,
            'display_name': obj.author.display_name,
            'avatar_url': obj.author.avatar_url,
            'plan': obj.author.plan,
        }

    # def get_upvote_count(self, obj):
    #     """Total upvotes for this thread."""
    #     return obj.upvote_count

    def get_has_upvoted(self, obj):
        """Check if current user has upvoted."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.upvotes.filter(user=request.user).exists()


class ThreadDetailSerializer(ThreadListSerializer):
    """Thread detail serializer with comments included."""
    comments = serializers.SerializerMethodField()

    class Meta(ThreadListSerializer.Meta):
        fields = ThreadListSerializer.Meta.fields + ['comments']

    def get_comments(self, obj):
        """Get top-level comments (parent=None) with nested replies."""
        comments = obj.comments.filter(parent=None, is_hidden=False)
        return DiscussionCommentSerializer(comments, many=True, context=self.context).data


MAX_THREAD_CHARS = 20_000
MAX_COMMENT_CHARS = 10_000


class ThreadCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new threads."""
    is_anonymous = serializers.BooleanField(default=False)
    title = serializers.CharField(max_length=200, trim_whitespace=True)
    content = serializers.CharField(max_length=MAX_THREAD_CHARS, trim_whitespace=False)

    class Meta:
        model = DiscussionThread
        # problem and author are set by the view
        fields = ['id', 'title', 'content', 'is_anonymous']
        read_only_fields = ['id']

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Content must not be empty.")
        return value

    def create(self, validated_data):
        """Set author from request user."""
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class CommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new comments."""
    body_md = serializers.CharField(source='content', max_length=MAX_COMMENT_CHARS, trim_whitespace=False)
    is_anonymous = serializers.BooleanField(default=False)

    class Meta:
        model = DiscussionComment
        fields = ['id', 'parent', 'body_md', 'is_anonymous']
        read_only_fields = ['id']

    def validate_body_md(self, value):
        if not value.strip():
            raise serializers.ValidationError("Comment must not be empty.")
        return value

    def validate_parent(self, parent):
        thread = self.context.get("thread")
        if parent is not None and thread is not None and parent.thread_id != thread.id:
            raise serializers.ValidationError("Parent comment belongs to a different thread.")
        return parent

    def create(self, validated_data):
        """Set author from request user."""
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)
