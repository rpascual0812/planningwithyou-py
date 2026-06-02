from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_error_log_views import ErrorLogAdminViewSet
from .views import (
    ActiveProjectsTagConfigView,
    BookingViewConfigView,
    BookingsGroupNameConfigView,
    ProfitProgressTagConfigView,
)

router = DefaultRouter()
router.register('admin/error-logs', ErrorLogAdminViewSet, basename='admin-error-log')

urlpatterns = [
    path(
        'config/booking-view/',
        BookingViewConfigView.as_view(),
        name='config-booking-view',
    ),
    path(
        'config/bookings-group-name/',
        BookingsGroupNameConfigView.as_view(),
        name='config-bookings-group-name',
    ),
    path(
        'config/profit-progress-tag/',
        ProfitProgressTagConfigView.as_view(),
        name='config-profit-progress-tag',
    ),
    path(
        'config/active-projects-tag/',
        ActiveProjectsTagConfigView.as_view(),
        name='config-active-projects-tag',
    ),
    path('', include(router.urls)),
]
