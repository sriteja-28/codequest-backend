from django.urls import path
from .views import (
    BillingPlansView,
    SubscribeView,
    CancelSubscriptionView,
)

urlpatterns = [
    path("plans/", BillingPlansView.as_view(), name="billing-plans"),
    path("subscribe/", SubscribeView.as_view(), name="subscribe"),
    path("cancel/", CancelSubscriptionView.as_view(), name="cancel-subscription"),
]
