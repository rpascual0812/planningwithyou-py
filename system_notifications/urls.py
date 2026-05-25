from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_views import SystemNotificationAdminViewSet
from .views import ActiveSystemNotificationsView

router = DefaultRouter()
router.register(
    r'admin/system-notifications',
    SystemNotificationAdminViewSet,
    basename='admin-system-notification',
)

urlpatterns = [
    path(
        'system-notifications/active/',
        ActiveSystemNotificationsView.as_view(),
        name='system-notifications-active',
    ),
    path('', include(router.urls)),
]
