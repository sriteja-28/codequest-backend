from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AdminContentPageViewSet,
    AdminCreativeViewSet,
    AdminPlacementViewSet,
    ContentPageDetailView,
    ContentPageListView,
    PlacementsView,
)

admin_router = SimpleRouter()
admin_router.register(r"pages", AdminContentPageViewSet, basename="admin-content-pages")
admin_router.register(r"placements", AdminPlacementViewSet, basename="admin-placements")
admin_router.register(r"creatives", AdminCreativeViewSet, basename="admin-creatives")

urlpatterns = [
    path("pages/", ContentPageListView.as_view(), name="content-list"),
    path("pages/<slug:slug>/", ContentPageDetailView.as_view(), name="content-detail"),
    path("placements/", PlacementsView.as_view(), name="layout-placements"),
    path("admin/", include(admin_router.urls)),
]
