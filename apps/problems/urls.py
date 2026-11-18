from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProblemViewSet, PracticeListViewSet, DailyProblemView, StarredProblemsView,
    SectionListView, TagListView,
    AdminProblemViewSet, AdminTestCaseViewSet,
    AdminSectionViewSet, AdminTagViewSet, AdminSolutionViewSet,
    AdminPracticeListViewSet, AdminDailyProblemViewSet,
)

router = DefaultRouter()
router.register(r"", ProblemViewSet, basename="problems")

admin_router = DefaultRouter()
admin_router.register(r"", AdminProblemViewSet, basename="admin-problems")

practice_router = DefaultRouter()
practice_router.register(r"", PracticeListViewSet, basename="practice-lists")

admin_practice_router = DefaultRouter()
admin_practice_router.register(r"", AdminPracticeListViewSet, basename="admin-practice-lists")

admin_daily_router = DefaultRouter()
admin_daily_router.register(r"", AdminDailyProblemViewSet, basename="admin-daily-problems")

urlpatterns = [
    # Public
    path("sections/", SectionListView.as_view(), name="sections-list"),
    path("tags/", TagListView.as_view(), name="tags-list"),
    path("daily/", DailyProblemView.as_view(), name="daily-problem"),
    path("starred/", StarredProblemsView.as_view(), name="starred-problems"),
    path("lists/", include(practice_router.urls)),

    # Admin CRUD
    path("admin/problems/", include(admin_router.urls)),
    path("admin/lists/", include(admin_practice_router.urls)),
    path("admin/daily/", include(admin_daily_router.urls)),
    path("admin/problems/<str:problem_slug>/testcases/", include([
        path("", AdminTestCaseViewSet.as_view({"get": "list", "post": "create"})),
        path("<int:pk>/", AdminTestCaseViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    ])),
    path("admin/problems/<str:problem_slug>/solutions/", include([
        path("", AdminSolutionViewSet.as_view({"get": "list", "post": "create"})),
        path("<int:pk>/", AdminSolutionViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    ])),
    path("admin/sections/", include([
        path("", AdminSectionViewSet.as_view({"get": "list", "post": "create"})),
        path("<int:pk>/", AdminSectionViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    ])),
    path("admin/tags/", include([
        path("", AdminTagViewSet.as_view({"get": "list", "post": "create"})),
        path("<int:pk>/", AdminTagViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"})),
    ])),

    # Public router (must be last — catches all slugs)
    path("", include(router.urls)),
]