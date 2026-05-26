from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_views import SystemLegalAdminViewSet
from .views import SystemLegalPublicView

router = DefaultRouter()
router.register(
    r'admin/system-legal',
    SystemLegalAdminViewSet,
    basename='admin-system-legal',
)

urlpatterns = [
    path(
        'system-legal/<str:name>/',
        SystemLegalPublicView.as_view(),
        name='system-legal-public',
    ),
    path('', include(router.urls)),
]
