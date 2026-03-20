from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User
from .serializers import (
    AdminUserSerializer,
    AdminStatisticsSerializer,
    AdminSettingsSerializer,
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class AdminUsersListView(APIView):
    """
    GET /api/admin/users/
    List all users (admin only).
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        users = User.objects.all().values("id", "username", "email", "role", "plan", "is_active")
        serializer = AdminUserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminStatisticsView(APIView):
    """
    GET /api/admin/statistics/
    Retrieve platform statistics (admin only).
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.problems.models import Problem
        from apps.submissions.models import Submission
        from apps.contests.models import Contest

        stats = {
            "total_users": User.objects.count(),
            "total_problems": Problem.objects.count(),
            "total_submissions": Submission.objects.count(),
            "total_contests": Contest.objects.count(),
        }
        serializer = AdminStatisticsSerializer(stats)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminSettingsView(APIView):
    """
    GET/POST /api/admin/settings/
    Manage platform settings (admin only).
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Placeholder: Return current settings
        settings_data = {
            "site_name": "CodeQuest",
            "maintenance_mode": False,
            "max_problem_limit": 500,
        }
        serializer = AdminSettingsSerializer(settings_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AdminSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Placeholder: Update settings
        return Response(
            {"message": "Settings updated."},
            status=status.HTTP_200_OK,
        )
