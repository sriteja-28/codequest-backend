from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AdminContestParticipantView,
    AdminContestViewSet,
    ContestDetailView,
    ContestLeaderboardView,
    ContestListView,
    ContestProblemDetailView,
    ContestRegisterView,
)

admin_router = SimpleRouter()
admin_router.register(r"contests", AdminContestViewSet, basename="admin-contests")

urlpatterns = [
    # Admin (role=ADMIN) — must precede the public <slug> routes
    path("admin/", include(admin_router.urls)),
    path(
        "admin/contests/<slug:slug>/participants/<int:user_id>/",
        AdminContestParticipantView.as_view(),
        name="admin-contest-participant",
    ),
    # Public
    path("", ContestListView.as_view()),
    path("<slug:slug>/", ContestDetailView.as_view()),
    path("<slug:slug>/register/", ContestRegisterView.as_view()),
    path("<slug:slug>/leaderboard/", ContestLeaderboardView.as_view()),
    path("<slug:slug>/problems/<slug:problem_slug>/", ContestProblemDetailView.as_view()),
]
