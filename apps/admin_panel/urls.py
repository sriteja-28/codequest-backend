from django.urls import path

from .views import (
    AdminAuditLogTypesView,
    AdminAuditLogView,
    AdminContestStatsView,
    AdminFeatureDetailView,
    AdminFeatureListView,
    AdminFlaggedCommentsView,
    AdminProblemStatsView,
    AdminSettingsView,
    AdminStatsOverviewView,
    AdminUserDetailView,
    AdminUsersListView,
)

urlpatterns = [
    path("users/", AdminUsersListView.as_view(), name="admin-users"),
    path("users/<int:user_id>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("stats/overview/", AdminStatsOverviewView.as_view(), name="admin-stats-overview"),
    path("stats/problems/", AdminProblemStatsView.as_view(), name="admin-stats-problems"),
    path("stats/contests/<slug:slug>/", AdminContestStatsView.as_view(), name="admin-stats-contest"),
    path("discussions/flags/", AdminFlaggedCommentsView.as_view(), name="admin-discussion-flags"),
    path("settings/", AdminSettingsView.as_view(), name="admin-settings"),
    path("features/", AdminFeatureListView.as_view(), name="admin-features"),
    path("features/<slug:key>/", AdminFeatureDetailView.as_view(), name="admin-feature-detail"),
    path("audit-log/", AdminAuditLogView.as_view(), name="admin-audit-log"),
    path("audit-log/types/", AdminAuditLogTypesView.as_view(), name="admin-audit-log-types"),
]
