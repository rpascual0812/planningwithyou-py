from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_views import (
    AdminSubscriptionPaymentProviderView,
    AdminSubscriptionPlanPricingView,
    SubscriptionPaymentProviderPublicView,
)
from .views import (
    AccountSubscriptionCurrentView,
    SubscribeAdminPlanView,
    SubscribeFreePlanView,
    SubscriptionCheckoutConfirmView,
    SubscriptionCheckoutPreviewView,
    SubscriptionCheckoutView,
    SubscriptionPaymentListView,
    SubscriptionPaymentReceiptDownloadView,
    SubscriptionReceiptDownloadView,
    SubscriptionReceiptListView,
    SubscriptionViewSet,
)
from .xendit_webhook_views import XenditWebhookView

router = DefaultRouter()
router.register('subscriptions', SubscriptionViewSet, basename='subscription')

urlpatterns = [
    path(
        'admin/subscription-payment-provider/',
        AdminSubscriptionPaymentProviderView.as_view(),
        name='admin-subscription-payment-provider',
    ),
    path(
        'admin/subscription-plan-pricing/',
        AdminSubscriptionPlanPricingView.as_view(),
        name='admin-subscription-plan-pricing',
    ),
    path(
        'subscriptions/payment-provider/',
        SubscriptionPaymentProviderPublicView.as_view(),
        name='subscription-payment-provider',
    ),
    path(
        'account-subscription/current/',
        AccountSubscriptionCurrentView.as_view(),
        name='account-subscription-current',
    ),
    path(
        'subscriptions/checkout/preview/',
        SubscriptionCheckoutPreviewView.as_view(),
        name='subscription-checkout-preview',
    ),
    path(
        'subscriptions/checkout/',
        SubscriptionCheckoutView.as_view(),
        name='subscription-checkout',
    ),
    path(
        'subscriptions/checkout/confirm/',
        SubscriptionCheckoutConfirmView.as_view(),
        name='subscription-checkout-confirm',
    ),
    path(
        'webhooks/xendit/',
        XenditWebhookView.as_view(),
        name='xendit-webhook',
    ),
    path(
        'api/webhooks/xendit/',
        XenditWebhookView.as_view(),
        name='xendit-webhook-legacy-api-prefix',
    ),
    path(
        'subscriptions/subscribe-free/',
        SubscribeFreePlanView.as_view(),
        name='subscription-subscribe-free',
    ),
    path(
        'subscriptions/subscribe-admin/',
        SubscribeAdminPlanView.as_view(),
        name='subscription-subscribe-admin',
    ),
    path(
        'subscriptions/payments/',
        SubscriptionPaymentListView.as_view(),
        name='subscription-payment-list',
    ),
    path(
        'subscriptions/payments/<int:payment_id>/receipt/download/',
        SubscriptionPaymentReceiptDownloadView.as_view(),
        name='subscription-payment-receipt-download',
    ),
    path(
        'subscriptions/receipts/',
        SubscriptionReceiptListView.as_view(),
        name='subscription-receipt-list',
    ),
    path(
        'subscriptions/receipts/<int:receipt_id>/download/',
        SubscriptionReceiptDownloadView.as_view(),
        name='subscription-receipt-download',
    ),
    path('', include(router.urls)),
]
