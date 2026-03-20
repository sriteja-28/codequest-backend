from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProblemViewSet, SectionListView, TagListView,
    AdminProblemViewSet, AdminTestCaseViewSet,
    AdminSectionViewSet, AdminTagViewSet, AdminSolutionViewSet,
)

router = DefaultRouter()
router.register(r"", ProblemViewSet, basename="problems")

admin_router = DefaultRouter()
admin_router.register(r"", AdminProblemViewSet, basename="admin-problems")

urlpatterns = [
    # Public
    path("sections/", SectionListView.as_view(), name="sections-list"),
    path("tags/", TagListView.as_view(), name="tags-list"),

    # Admin CRUD
    path("admin/problems/", include(admin_router.urls)),
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