"""Home/profile progress aggregation.

One cached payload per user powers the home dashboard, the profile progress
ring, the streak/heatmap and the per-section roadmap. It is invalidated after
every judged submission (see submissions.services.finalize_submission), and
otherwise refreshed on the PROGRESS_CACHE_TTL cadence.
"""

from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

CACHE_VERSION = "v1"
ACTIVITY_DAYS = 365


def progress_cache_key(user_id) -> str:
    return f"progress:{CACHE_VERSION}:user:{user_id}"


def invalidate_progress(user_id) -> None:
    cache.delete(progress_cache_key(user_id))


def _bucket():
    return {"total": 0, "solved": 0}


def build_progress(user) -> dict:
    from apps.problems.models import Problem, Section
    from apps.submissions.models import Submission
    from apps.users.models import UserDailyActivity, UserSolvedProblem

    today = timezone.now().date()
    solved_ids = set(
        UserSolvedProblem.objects.filter(
            user=user, problem__is_published=True
        ).values_list("problem_id", flat=True)
    )

    totals = {"all": _bucket(), "EASY": _bucket(), "MEDIUM": _bucket(), "HARD": _bucket()}
    section_totals = {}
    for problem_id, difficulty, section_id in Problem.objects.filter(
        is_published=True
    ).values_list("id", "difficulty", "section_id"):
        totals["all"]["total"] += 1
        totals.setdefault(difficulty, _bucket())["total"] += 1
        if section_id:
            section_totals[section_id] = section_totals.get(section_id, 0) + 1
        if problem_id in solved_ids:
            totals["all"]["solved"] += 1
            totals.setdefault(difficulty, _bucket())["solved"] += 1

    solved_by_section = dict(
        UserSolvedProblem.objects.filter(user=user, problem__is_published=True)
        .values("problem__section_id")
        .annotate(count=Count("id"))
        .values_list("problem__section_id", "count")
    )

    sections = []
    for section in Section.objects.all().order_by("order_index", "display_name"):
        total = section_totals.get(section.id, 0)
        solved = solved_by_section.get(section.id, 0)
        sections.append({
            "id": section.id,
            "name": section.name,
            "slug": section.slug,
            "display_name": section.display_name,
            "icon": section.icon,
            "total": total,
            "solved": solved,
            "percent": round(solved / total * 100, 1) if total else 0.0,
        })

    submissions = Submission.objects.filter(user=user, is_sample_run=False).exclude(
        status=Submission.Status.INTERNAL_ERROR
    )
    stats = submissions.aggregate(
        total=Count("id"),
        accepted=Count("id", filter=Q(status=Submission.Status.ACCEPTED)),
    )
    total_submissions = stats["total"] or 0
    accepted_submissions = stats["accepted"] or 0

    today_activity = UserDailyActivity.objects.filter(user=user, date=today).first()

    start = today - timedelta(days=ACTIVITY_DAYS - 1)
    rows = {
        row.date: row
        for row in UserDailyActivity.objects.filter(user=user, date__gte=start)
    }
    activity = []
    for offset in range(ACTIVITY_DAYS):
        day = start + timedelta(days=offset)
        row = rows.get(day)
        activity.append({
            "date": day.isoformat(),
            "submissions": row.submissions if row else 0,
            "accepted": row.accepted if row else 0,
        })

    # The stored streak is only advanced by accepted submissions; report it as
    # 0 once the last accepted day is older than yesterday.
    current_streak = user.current_streak
    if not user.last_active_date or user.last_active_date < today - timedelta(days=1):
        current_streak = 0

    recent = [
        {
            "id": str(sub.id),
            "problem_slug": sub.problem.slug,
            "problem_title": sub.problem.title,
            "status": sub.status,
            "language": sub.language,
            "created_at": sub.created_at.isoformat(),
        }
        for sub in submissions.select_related("problem").order_by("-created_at")[:5]
    ]

    return {
        "totals": totals,
        "solve_rate": (
            round(totals["all"]["solved"] / totals["all"]["total"] * 100, 1)
            if totals["all"]["total"] else 0.0
        ),
        "submissions": {
            "total": total_submissions,
            "accepted": accepted_submissions,
            "acceptance_rate": (
                round(accepted_submissions / total_submissions * 100, 1)
                if total_submissions else 0.0
            ),
            "today": today_activity.submissions if today_activity else 0,
            "accepted_today": today_activity.accepted if today_activity else 0,
        },
        "streak": {
            "current": current_streak,
            "best": user.best_streak,
            "last_active_date": user.last_active_date.isoformat() if user.last_active_date else None,
        },
        "sections": sections,
        "activity": activity,
        "recent_submissions": recent,
    }


def get_user_progress(user) -> dict:
    key = progress_cache_key(user.id)
    data = cache.get(key)
    if data is None:
        data = build_progress(user)
        cache.set(key, data, getattr(settings, "PROGRESS_CACHE_TTL", 300))
    return data
