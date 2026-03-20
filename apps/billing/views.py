from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    BillingPlanSerializer,
    SubscriptionSerializer,
    CancelSubscriptionSerializer,
)


class BillingPlansView(APIView):
    """
    GET /api/billing/plans/
    List available subscription plans.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # Placeholder: Return available plans
        plans = [
            {
                "id": 1,
                "name": "Free",
                "description": "Basic access",
                "price": 0,
                "period": "month",
                "features": ["20 AI hints/day", "Limited problems"],
            },
            {
                "id": 2,
                "name": "Pro",
                "description": "Premium access",
                "price": 9.99,
                "period": "month",
                "features": ["200 AI hints/day", "All problems", "Priority support"],
            },
        ]
        serializer = BillingPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SubscribeView(APIView):
    """
    POST /api/billing/subscribe/
    Subscribe to a plan.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Placeholder: Process subscription
        return Response(
            {"message": "Subscription successful."},
            status=status.HTTP_201_CREATED,
        )


class CancelSubscriptionView(APIView):
    """
    POST /api/billing/cancel/
    Cancel current subscription.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CancelSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Placeholder: Cancel subscription
        return Response(
            {"message": "Subscription cancelled."},
            status=status.HTTP_200_OK,
        )
