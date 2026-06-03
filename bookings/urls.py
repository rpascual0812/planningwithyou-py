from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .manual_payment_views import QuotationManualPaymentCreateView
from .payment_link_views import (
    QuotationPaymentLinkDetailView,
    QuotationPaymentLinkListCreateView,
    PayMongoWebhookView,
    PublicPaymentLinkView,
)
from .payout_admin_views import QuotationPaymentPayoutAdminViewSet
from .payout_report_views import QuotationPaymentPayoutReportViewSet
from .dashboard_views import (
    DashboardActiveProjectsView,
    DashboardProfitProgressView,
    DashboardSummaryView,
)
from .views import (
    QuotationViewSet,
    QuotationStatusViewSet,
    FormTemplateViewSet,
    SupplierQuotationCapacityView,
    TagViewSet,
)

router = DefaultRouter()
router.register('quotation-statuses', QuotationStatusViewSet, basename='quotation-status')
router.register('tags', TagViewSet, basename='tag')
router.register('quotation-items', QuotationViewSet, basename='quotation-item')
router.register('form-templates', FormTemplateViewSet, basename='form-template')
router.register(
    'admin/quotation-payments',
    QuotationPaymentPayoutAdminViewSet,
    basename='admin-quotation-payment',
)
router.register(
    'booking-payouts',
    QuotationPaymentPayoutReportViewSet,
    basename='quotation-payout',
)

urlpatterns = [
    path(
        'dashboard/summary/',
        DashboardSummaryView.as_view(),
        name='dashboard-summary',
    ),
    path(
        'dashboard/profit-progress/',
        DashboardProfitProgressView.as_view(),
        name='dashboard-profit-progress',
    ),
    path(
        'dashboard/active-projects/',
        DashboardActiveProjectsView.as_view(),
        name='dashboard-active-projects',
    ),
    path(
        'supplier-quotation-capacity/',
        SupplierQuotationCapacityView.as_view(),
        name='supplier-quotation-capacity',
    ),
    path(
        'quotation-items/<int:quotation_id>/payment-links/',
        QuotationPaymentLinkListCreateView.as_view(),
        name='quotation-payment-links',
    ),
    path(
        'quotation-items/<int:quotation_id>/payment-links/<int:link_id>/',
        QuotationPaymentLinkDetailView.as_view(),
        name='quotation-payment-link-detail',
    ),
    path(
        'quotation-items/<int:quotation_id>/manual-payments/',
        QuotationManualPaymentCreateView.as_view(),
        name='quotation-manual-payment',
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
