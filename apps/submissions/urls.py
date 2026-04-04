from django.urls import path
from .views import SubmissionCreateView, SubmissionDetailView, UserSubmissionListView, JudgeCallbackView, RunCodeView

urlpatterns = [
    path("", SubmissionCreateView.as_view(), name="submission-create"),
    path("history/", UserSubmissionListView.as_view(), name="submission-history"),
    path("<uuid:id>/", SubmissionDetailView.as_view(), name="submission-detail"),
    path("<uuid:submission_id>/judge-callback/", JudgeCallbackView.as_view(), name="judge-callback"),
    path("run-code/", RunCodeView.as_view(), name="run-code"),
]


# from django.urls import path
# from . import views

# urlpatterns = [
#     path('submissions/', views.SubmissionCreateView.as_view()),
#     path('submissions/<uuid:submission_id>/', views.SubmissionDetailView.as_view()),
#     path('submissions/list/', views.SubmissionListView.as_view()),
#     path('judge/callback/', views.JudgeCallbackView.as_view()),
# ]