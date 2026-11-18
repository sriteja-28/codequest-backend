from django.urls import include, path
from rest_framework.routers import DefaultRouter, SimpleRouter

from .admin_views import AdminCategoryViewSet, AdminChapterViewSet, AdminCourseViewSet, AdminLessonViewSet
from .views import CategoryListView, CourseViewSet, LessonCompleteView

router = DefaultRouter()
router.register(r"", CourseViewSet, basename="courses")

admin_router = SimpleRouter()
admin_router.register(r"categories", AdminCategoryViewSet, basename="admin-course-categories")
admin_router.register(r"courses", AdminCourseViewSet, basename="admin-courses")
admin_router.register(r"chapters", AdminChapterViewSet, basename="admin-course-chapters")
admin_router.register(r"lessons", AdminLessonViewSet, basename="admin-course-lessons")

urlpatterns = [
    path("categories/", CategoryListView.as_view(), name="course-categories"),
    path("lessons/<int:pk>/complete/", LessonCompleteView.as_view(), name="course-lesson-complete"),
    # Before the public router: its detail route would otherwise claim "admin".
    path("admin/", include(admin_router.urls)),
    path("", include(router.urls)),
]
