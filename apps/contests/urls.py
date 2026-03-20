from django.urls import path
from .views import (
    ContestListView,
    ContestDetailView,
    ContestRegisterView,
    ContestLeaderboardView,
)

# urlpatterns = []
urlpatterns = [
    path("", ContestListView.as_view()),
    path("<slug:slug>/", ContestDetailView.as_view()),
    path("<slug:slug>/register/", ContestRegisterView.as_view()),
    path("<slug:slug>/leaderboard/", ContestLeaderboardView.as_view()),
]