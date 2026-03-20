from django.urls import path
from .views import (
    ContentPageListView,
    ContentPageDetailView,
)

urlpatterns = [
    path("pages/", ContentPageListView.as_view(), name="content-list"),
    path("pages/<slug:slug>/", ContentPageDetailView.as_view(), name="content-detail"),
]
