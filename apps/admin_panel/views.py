from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.features import FEATURES_BY_KEY, admin_feature_rows
from apps.users.models import User

from .audit import audited_update, record
from .models import AdminLog, PlatformSettings
from .serializers import (
    AdminLogSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    FeatureOverrideSerializer,
    PlatformSettingsSerializer,
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class IsModerator(permissions.BasePermission):
    """Admins and moderators (discussion moderation)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in (User.Role.ADMIN, User.Role.MODERATOR)


def _pro_filter(now):
    return Q(plan=User.Plan.PRO) & (Q(plan_expires_at__isnull=True) | Q(plan_expires_at__gt=now))


def _pct(part, whole):
    return round(part * 100.0 / whole, 1) if whole else 0.0


class AdminUsersListView(generics.ListAPIView):
    """
    GET /api/admin/users/?search=&plan=FREE|PRO&role=USER|MODERATOR|ADMIN&status=active|banned|inactive
    Paginated user list (admin only), newest first, with judged submission counts.
    """

    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        # "-id" tiebreaks identical created_at timestamps so ordering is stable.
        qs = User.objects.annotate(
            submission_count=Count("submissions", filter=Q(submissions__is_sample_run=False), distinct=True)
        ).order_by("-created_at", "-id")
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(email__icontains=search) | Q(username__icontains=search) | Q(display_name__icontains=search))
        plan = params.get("plan", "").upper()
        now = timezone.now()
        if plan == "PRO":
            qs = qs.filter(_pro_filter(now))
        elif plan == "FREE":
            qs = qs.exclude(_pro_filter(now))
        role = params.get("role", "").upper()
        if role in User.Role.values:
            qs = qs.filter(role=role)
        state = params.get("status", "").lower()
        if state == "banned":
            qs = qs.filter(is_banned=True)
        elif state == "inactive":
            qs = qs.filter(is_active=False)
        elif state == "active":
            qs = qs.filter(is_active=True, is_banned=False)
        return qs


class AdminUserDetailView(APIView):
    """
    GET   /api/admin/users/{id}/
    PATCH /api/admin/users/{id}/  {role?, is_active?, is_banned?, banned_reason?, display_name?}
    Changes are audited; bans and unbans are logged as BAN / UNBAN.
    """

    permission_classes = [IsAdminUser]

    def get(self, request, user_id):
        return Response(AdminUserSerializer(get_object_or_404(User, pk=user_id)).data)

    def patch(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        banned = serializer.validated_data.get("is_banned")
        action, description = "UPDATE", None
        if banned is not None and banned != user.is_banned:
            action = "BAN" if banned else "UNBAN"
            reason = serializer.validated_data.get("banned_reason", "")
            description = f"Banned {user.username}" + (f": {reason}" if reason else "") if banned else f"Unbanned {user.username}"
        audited_update(actor=request.user, instance=user, apply=serializer.save, action=action, description=description)
        return Response(AdminUserSerializer(user).data)


class AdminStatsOverviewView(APIView):
    """GET /api/admin/stats/overview/ — dashboard KPIs (frontend AdminStats type)."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.contests.models import Contest
        from apps.courses.models import Course
        from apps.discussions.models import DiscussionComment
        from apps.problems.models import Problem, ProblemList
        from apps.submissions.models import Submission

        now = timezone.now()
        today = now.date()
        total_users = User.objects.count()
        pro_users = User.objects.filter(_pro_filter(now)).count()

        judged = Submission.objects.filter(is_sample_run=False)
        today_qs = judged.filter(created_at__date=today)
        submitted_today = today_qs.count()
        accepted_today = today_qs.filter(status="ACCEPTED").count()

        start = today - timedelta(days=13)
        rows = (
            judged.filter(created_at__date__gte=start)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"), accepted=Count("id", filter=Q(status="ACCEPTED")))
        )
        by_day = {row["day"]: row for row in rows}
        per_day = []
        for i in range(14):
            day = start + timedelta(days=i)
            row = by_day.get(day, {})
            per_day.append({"day": day.isoformat(), "count": row.get("count", 0), "accepted": row.get("accepted", 0)})

        problems = Problem.objects.aggregate(
            published=Count("id", filter=Q(is_published=True)),
            drafts=Count("id", filter=Q(is_published=False)),
        )
        return Response({
            "users": {
                "total": total_users,
                "pro": pro_users,
                "free": total_users - pro_users,
                "new_this_week": User.objects.filter(created_at__gte=now - timedelta(days=7)).count(),
                "pro_pct": _pct(pro_users, total_users),
            },
            "submissions": {
                "total": judged.count(),
                "today": submitted_today,
                "accepted_today": accepted_today,
                "acceptance_rate_today": _pct(accepted_today, submitted_today),
                "per_day": per_day,
            },
            "platform": {
                "total_problems": problems["published"],
                "draft_problems": problems["drafts"],
                "practice_lists": ProblemList.objects.count(),
                "courses": Course.objects.count(),
                "active_contests": Contest.objects.filter(start_at__lte=now, end_at__gte=now, finalized_at__isnull=True).count(),
                "upcoming_contests": Contest.objects.filter(start_at__gt=now).count(),
                "flagged_comments": DiscussionComment.objects.filter(is_flagged=True, is_hidden=False).count(),
            },
        })


class AdminProblemStatsView(APIView):
    """GET /api/admin/stats/problems/ — per-problem submission stats, busiest first."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.problems.models import Problem

        problems = Problem.objects.order_by("-total_submissions", "number")[:500]
        return Response({
            "problems": [
                {
                    "slug": p.slug,
                    "title": p.title,
                    "difficulty": p.difficulty,
                    "is_published": p.is_published,
                    "total_submissions": p.total_submissions,
                    "accepted_submissions": p.accepted_submissions,
                    "acceptance_rate": p.acceptance_rate,
                }
                for p in problems
            ]
        })


class AdminContestStatsView(APIView):
    """GET /api/admin/stats/contests/{slug}/ — participation and per-problem results."""

    permission_classes = [IsAdminUser]

    def get(self, request, slug):
        from apps.contests.models import Contest
        from apps.submissions.models import Submission

        contest = get_object_or_404(Contest, slug=slug)
        subs = Submission.objects.filter(contest=contest, is_sample_run=False)
        per_problem = []
        for cp in contest.contest_problems.select_related("problem"):
            p_subs = subs.filter(problem=cp.problem)
            per_problem.append({
                "problem_slug": cp.problem.slug,
                "title": cp.problem.title,
                "score": cp.score,
                "submissions": p_subs.count(),
                "solved_by": p_subs.filter(status="ACCEPTED").values("user").distinct().count(),
            })
        return Response({
            "contest": contest.slug,
            "status": contest.status,
            "participants": contest.participants.count(),
            "submissions": subs.count(),
            "accepted": subs.filter(status="ACCEPTED").count(),
            "problems": per_problem,
        })


class AdminFlaggedCommentsView(APIView):
    """GET /api/admin/discussions/flags/ — flagged, still-visible comments (moderators too)."""

    permission_classes = [IsModerator]

    def get(self, request):
        from apps.discussions.models import DiscussionComment

        comments = (
            DiscussionComment.objects.filter(is_flagged=True, is_hidden=False)
            .select_related("author", "thread__problem")
            .order_by("-created_at")[:200]
        )
        items = [
            {
                "id": c.id,
                "body_preview": c.content[:200],
                "created_by": c.author.username,
                "thread_id": c.thread_id,
                "thread_title": c.thread.title,
                "problem_slug": c.thread.problem.slug,
                "problem_title": c.thread.problem.title,
                "created_at": c.created_at,
            }
            for c in comments
        ]
        return Response({"flagged_comments": items, "count": len(items)})


class AdminSettingsView(APIView):
    """
    GET   /api/admin/settings/  — the platform settings row (created with defaults on first use).
    PATCH /api/admin/settings/  — partial update; audited; /api/config/ reflects it immediately.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(PlatformSettingsSerializer(PlatformSettings.load()).data)

    def patch(self, request):
        PlatformSettings.load()
        with transaction.atomic():
            instance = PlatformSettings.objects.select_for_update().get(pk=1)
            serializer = PlatformSettingsSerializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            audited_update(actor=request.user, instance=instance, apply=serializer.save)
        return Response(PlatformSettingsSerializer(instance).data)


def _feature_overrides():
    from apps.content.models import FeatureFlag

    return dict(FeatureFlag.objects.values_list("key", "value"))


class AdminFeatureListView(APIView):
    """GET /api/admin/features/ — every registry feature with its state and admin override."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({"features": admin_feature_rows(_feature_overrides())})


class AdminFeatureDetailView(APIView):
    """
    PATCH /api/admin/features/{key}/  {enabled: true | false | null}
    Turns an implemented feature on/off (null = back to the default). Features
    that are not built yet stay "coming soon" (400 not_toggleable). Audited.
    """

    permission_classes = [IsAdminUser]

    def patch(self, request, key):
        from apps.content.models import FeatureFlag

        feature = FEATURES_BY_KEY.get(key)
        if feature is None:
            return Response({"detail": "Unknown feature."}, status=status.HTTP_404_NOT_FOUND)
        if not feature.implemented:
            return Response(
                {"detail": f"{feature.label} is not built yet, so it stays 'coming soon'.", "code": "not_toggleable"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = FeatureOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enabled = serializer.validated_data["enabled"]

        with transaction.atomic():
            flag = FeatureFlag.objects.select_for_update().filter(key=key).first()
            before = None if flag is None else flag.value
            if enabled is None:
                if flag is not None:
                    flag.delete()
            elif flag is None:
                FeatureFlag.objects.create(key=key, value=enabled, description=f"Admin override for {feature.label}")
            elif flag.value != enabled:
                flag.value = enabled
                flag.save(update_fields=["value"])
            if before != enabled:
                if enabled is None:
                    default = "on" if feature.default_on else "off"
                    description = f"Reset {feature.label} to its default ({default})"
                else:
                    description = f"Turned {feature.label} {'on' if enabled else 'off'}"
                record(actor=request.user, action="UPDATE", object_type="feature", object_id=key,
                       object_repr=feature.label, changes={"enabled": [before, enabled]}, description=description)

        row = next(item for item in admin_feature_rows(_feature_overrides()) if item["key"] == key)
        return Response(row)


class AdminAuditLogView(generics.ListAPIView):
    """
    GET /api/admin/audit-log/?action=&object_type=&object_id=&source=api|django|system&admin=<id|username>&search=
    The audit trail, newest first (paginated).
    """

    permission_classes = [IsAdminUser]
    serializer_class = AdminLogSerializer

    def get_queryset(self):
        qs = AdminLog.objects.select_related("admin").order_by("-created_at", "-id")
        params = self.request.query_params
        if params.get("action"):
            qs = qs.filter(action=params["action"].upper())
        if params.get("object_type"):
            qs = qs.filter(object_type=params["object_type"])
        if params.get("object_id"):
            qs = qs.filter(object_id=params["object_id"])
        if params.get("source"):
            qs = qs.filter(source=params["source"])
        admin = params.get("admin", "").strip()
        if admin:
            qs = qs.filter(admin_id=admin) if admin.isdigit() else qs.filter(admin__username=admin)
        search = params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(object_repr__icontains=search) | Q(description__icontains=search) | Q(admin__username__icontains=search)
            )
        return qs


class AdminAuditLogTypesView(APIView):
    """GET /api/admin/audit-log/types/ — object types present in the log (filter options)."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        types = AdminLog.objects.order_by("object_type").values_list("object_type", flat=True).distinct()
        return Response({"object_types": [t for t in types if t]})
