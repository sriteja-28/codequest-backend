from django.urls import path
from .views import (
    AdminUsersListView,
    AdminStatisticsView,
    AdminSettingsView,
)

urlpatterns = [
    path("users/", AdminUsersListView.as_view(), name="admin-users"),
    path("statistics/", AdminStatisticsView.as_view(), name="admin-statistics"),
    path("settings/", AdminSettingsView.as_view(), name="admin-settings"),
]
