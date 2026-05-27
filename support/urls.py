from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_views import SupportTicketAdminViewSet
from .views import SupportTicketViewSet

router = DefaultRouter()
router.register('support-tickets', SupportTicketViewSet, basename='support-ticket')
router.register(
    'admin/support-tickets',
    SupportTicketAdminViewSet,
    basename='admin-support-ticket',
)

urlpatterns = [
    path('', include(router.urls)),
]
