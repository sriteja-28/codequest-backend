from django.db.models import Q
from django.utils import timezone
from rest_framework import filters, generics, permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_panel.audit import AuditedViewSetMixin
from apps.core.features import feature_enabled_for

from .models import AdCreative, AdPlacement, ContentPage
from .serializers import (
    AdCreativeAdminSerializer,
    AdCreativePublicSerializer,
    AdPlacementAdminSerializer,
    ContentPageSerializer,
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class ContentPageListView(generics.ListAPIView):
    """
    GET /api/layout/pages/
    List all published content pages.
    """
    queryset = ContentPage.objects.filter(published=True)
    serializer_class = ContentPageSerializer
    permission_classes = [permissions.AllowAny]


class ContentPageDetailView(generics.RetrieveAPIView):
    """
    GET /api/layout/pages/{slug}/
    Retrieve a specific content page by slug.
    """
    queryset = ContentPage.objects.filter(published=True)
    serializer_class = ContentPageSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"


class PlacementsView(APIView):
    """
    GET /api/layout/placements/?route=/problems
    Active ad placements with the creatives targeted at the viewer's plan
    (anonymous and Free users → FREE creatives; Pro users → PRO creatives,
    so Pro members see no Free-tier ads). `route` is accepted for forward
    compatibility; placements are currently global (matched by `position`).
    html_snippet is admin-authored markup: the frontend renders it inside a
    sandboxed iframe without script execution.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not feature_enabled_for(request.user, "ads"):
            return Response({"placements": [], "route": request.query_params.get("route", "")})
        now = timezone.now()
        user = request.user
        plan = "PRO" if user.is_authenticated and user.is_pro else "FREE"
        live = (
            AdCreative.objects.filter(is_active=True, plan_target=plan)
            .filter(Q(start_at__isnull=True) | Q(start_at__lte=now))
            .filter(Q(end_at__isnull=True) | Q(end_at__gte=now))
            .order_by("-priority", "id")
        )
        placements = []
        for placement in AdPlacement.objects.filter(is_active=True).order_by("key"):
            creatives = list(live.filter(placement=placement)[: max(placement.max_per_page, 0)])
            if creatives:
                placements.append({
                    "key": placement.key,
                    "position": placement.position,
                    "creatives": AdCreativePublicSerializer(creatives, many=True).data,
                })
        return Response({"placements": placements, "route": request.query_params.get("route", "")})


class AdminPlacementViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    """/api/layout/admin/placements/ — CRUD (admin only)."""
    queryset = AdPlacement.objects.all().order_by("key")
    serializer_class = AdPlacementAdminSerializer
    permission_classes = [IsAdminUser]


class AdminCreativeViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    """/api/layout/admin/creatives/ — CRUD (admin only)."""
    queryset = AdCreative.objects.select_related("placement").order_by("-priority", "id")
    serializer_class = AdCreativeAdminSerializer
    permission_classes = [IsAdminUser]


class AdminContentPageViewSet(AuditedViewSetMixin, viewsets.ModelViewSet):
    queryset = ContentPage.objects.all().order_by("order_index", "slug")
    serializer_class = ContentPageSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ["title", "slug"]
