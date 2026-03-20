from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Built-in Django admin (fallback / superuser access)
    path("django-admin/", admin.site.urls),
    # API routes — all prefixed with /api/
    path("api/auth/", include("apps.users.urls")),
    path("api/problems/", include("apps.problems.urls")),
    path("api/submissions/", include("apps.submissions.urls")),
    path("api/contests/", include("apps.contests.urls")),
    path("api/discuss/", include("apps.discussions.urls")),
    path("api/ai/", include("apps.ai_assist.urls")),
    path("api/layout/", include("apps.content.urls")),
    path("api/admin/", include("apps.admin_panel.urls")),
    path("api/billing/", include("apps.billing.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
