from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .payment_link_views import (
    BookingPaymentLinkDetailView,
    BookingPaymentLinkListCreateView,
    PayMongoWebhookView,
    PublicPaymentLinkView,
)
from .payout_admin_views import BookingPaymentPayoutAdminViewSet
from .payout_report_views import BookingPaymentPayoutReportViewSet
from .dashboard_views import DashboardSummaryView
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
router.register(
    'admin/booking-payments',
    BookingPaymentPayoutAdminViewSet,
    basename='admin-booking-payment',
)
router.register(
    'booking-payouts',
    BookingPaymentPayoutReportViewSet,
    basename='booking-payout',
)

urlpatterns = [
    path(
        'dashboard/summary/',
        DashboardSummaryView.as_view(),
        name='dashboard-summary',
    ),
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
    # Backward-compatible webhook route used by older PayMongo endpoint configs.
    path(
        'api/webhooks/paymongo/',
        PayMongoWebhookView.as_view(),
        name='paymongo-webhook-legacy-api-prefix',
    ),
    path('', include(router.urls)),
]
