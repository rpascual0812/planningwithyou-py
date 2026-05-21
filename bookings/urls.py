from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .payment_link_views import (
    BookingPaymentLinkDetailView,
    BookingPaymentLinkListCreateView,
    PayMongoWebhookView,
    PublicPaymentLinkView,
)
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
    path(
        'booking-items/<int:booking_id>/payment-links/',
        BookingPaymentLinkListCreateView.as_view(),
        name='booking-payment-links',
    ),
    path(
        'booking-items/<int:booking_id>/payment-links/<int:link_id>/',
        BookingPaymentLinkDetailView.as_view(),
        name='booking-payment-link-detail',
    ),
    path(
        'public/payment-links/<uuid:token>/',
        PublicPaymentLinkView.as_view(),
        name='public-payment-link',
    ),
    path(
        'webhooks/paymongo/',
        PayMongoWebhookView.as_view(),
        name='paymongo-webhook',
    ),
    path('', include(router.urls)),
]
