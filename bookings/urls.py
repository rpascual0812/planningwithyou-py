from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BookingItemViewSet,
    BookingStatusViewSet,
    FormTemplateViewSet,
    SupplierBookingCapacityView,
)

router = DefaultRouter()
router.register('booking-statuses', BookingStatusViewSet, basename='booking-status')
router.register('booking-items', BookingItemViewSet, basename='booking-item')
router.register('form-templates', FormTemplateViewSet, basename='form-template')

urlpatterns = [
    path(
        'supplier-booking-capacity/',
        SupplierBookingCapacityView.as_view(),
        name='supplier-booking-capacity',
    ),
    path('', include(router.urls)),
]
