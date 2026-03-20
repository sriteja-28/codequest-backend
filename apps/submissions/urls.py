from django.urls import path
from .views import SubmissionCreateView, SubmissionDetailView, UserSubmissionListView, JudgeCallbackView

urlpatterns = [
    path("", SubmissionCreateView.as_view(), name="submission-create"),
    path("history/", UserSubmissionListView.as_view(), name="submission-history"),
    path("<uuid:id>/", SubmissionDetailView.as_view(), name="submission-detail"),
    path("<uuid:submission_id>/judge-callback/", JudgeCallbackView.as_view(), name="judge-callback"),
]