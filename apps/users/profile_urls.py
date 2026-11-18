from django.urls import path

from .views import MyProgressView

urlpatterns = [
    path("me/progress/", MyProgressView.as_view(), name="users-me-progress"),
]
