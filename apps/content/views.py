from rest_framework import generics, permissions
from .models import ContentPage
from .serializers import ContentPageSerializer


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
