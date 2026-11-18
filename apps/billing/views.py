"""
Billing.

No payment provider is integrated. Plans are informational, self-service
subscribe/cancel answer 501 coming_soon (feature "payments") instead of
reporting a fake success, and admins grant or revoke Pro via
PATCH /api/billing/admin/users/{id}/plan/ (audited).
Integrating a provider (e.g. Stripe Checkout + a signed, idempotent webhook
that sets User.plan / plan_expires_at) requires provider credentials.
"""

from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_panel.audit import audited_update
from apps.core.features import coming_soon_response
from apps.users.models import User

from .models import BillingPlan
from .serializers import (
    AdminPlanChangeSerializer,
    BillingPlanSerializer,
    CancelSubscriptionSerializer,
    SubscriptionSerializer,
)

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


def _default_plans():
    """Plans derived from the limits the backend actually enforces."""
    from apps.core.site import hint_quota

    free_hints, pro_hints = hint_quota(pro=False), hint_quota(pro=True)
    return [
        {
            "id": 1,
            "name": "Free",
            "description": "Practice problems with sample runs and full judging.",
            "price": 0,
            "period": "month",
            "features": [
                "All free problems",
                f"{free_hints} hints/day (first hint of each problem)",
                "Free editorials",
            ],
        },
        {
            "id": 2,
            "name": "Pro",
            "description": "Premium problems, editorials and higher limits.",
            "price": 9.99,
            "period": "month",
            "features": [
                "Pro-only problems and editorials",
                f"{pro_hints} hints/day (all hint levels)",
                "Higher run/submit rate limits",
                "Priority when the judge queue is busy",
            ],
        },
    ]


class BillingPlansView(APIView):
    """
    GET /api/billing/plans/
    Active BillingPlan rows if configured, otherwise the built-in Free/Pro plans.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        rows = BillingPlan.objects.filter(is_active=True)
        plans = [
            {"id": p.id, "name": p.name, "description": p.description, "price": p.price,
             "period": p.period, "features": p.features or []}
            for p in rows
        ] or _default_plans()
        return Response(BillingPlanSerializer(plans, many=True).data, status=status.HTTP_200_OK)


class SubscribeView(APIView):
    """POST /api/billing/subscribe/ — 501 coming_soon (feature "payments") until a
    payment provider is integrated."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        SubscriptionSerializer(data=request.data).is_valid(raise_exception=True)
        return coming_soon_response("payments")


class CancelSubscriptionView(APIView):
    """POST /api/billing/cancel/ — 501 coming_soon (feature "payments")."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        CancelSubscriptionSerializer(data=request.data).is_valid(raise_exception=True)
        return coming_soon_response("payments")


class AdminChangePlanView(APIView):
    """
    PATCH /api/billing/admin/users/{id}/plan/   {plan: "FREE"|"PRO", days?: 1..3650 (default 30)}
    PRO sets plan_expires_at = now + days; FREE clears the expiry.
    """
    permission_classes = [IsAdminUser]

    def patch(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        serializer = AdminPlanChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.validated_data["plan"]

        def apply():
            if plan == User.Plan.PRO:
                user.plan = User.Plan.PRO
                user.plan_expires_at = timezone.now() + timedelta(days=serializer.validated_data["days"])
            else:
                user.plan = User.Plan.FREE
                user.plan_expires_at = None
            user.save(update_fields=["plan", "plan_expires_at", "updated_at"])

        verb = f"Granted Pro ({serializer.validated_data['days']} days) to" if plan == User.Plan.PRO else "Set Free plan for"
        audited_update(actor=request.user, instance=user, apply=apply, description=f"{verb} {user.username}")
        return Response({
            "user_id": user.id,
            "new_plan": user.plan,
            "plan_expires_at": user.plan_expires_at,
        })
