from django.urls import path

from .views import (
    JudgeCallbackView,
    JudgeTestCasesView,
    RunCodeView,
    SubmissionCreateView,
    SubmissionDetailView,
    UserSubmissionListView,
)

urlpatterns = [
    path("", SubmissionCreateView.as_view(), name="submission-create"),
    path("history/", UserSubmissionListView.as_view(), name="submission-history"),
    path("run-code/", RunCodeView.as_view(), name="run-code"),
    path("<uuid:id>/", SubmissionDetailView.as_view(), name="submission-detail"),
    # Internal (judge worker only, X-Judge-Api-Key)
    path("<uuid:submission_id>/judge-callback/", JudgeCallbackView.as_view(), name="judge-callback"),
    path("judge/problems/<int:problem_id>/testcases/", JudgeTestCasesView.as_view(), name="judge-testcases"),
]
