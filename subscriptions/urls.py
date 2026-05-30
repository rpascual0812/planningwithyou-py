from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountSubscriptionCurrentView,
    SubscribeFreePlanView,
    SubscriptionCheckoutPreviewView,
    SubscriptionCheckoutView,
    SubscriptionReceiptDownloadView,
    SubscriptionReceiptListView,
    SubscriptionViewSet,
)

router = DefaultRouter()
router.register('subscriptions', SubscriptionViewSet, basename='subscription')

urlpatterns = [
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
        'subscriptions/subscribe-free/',
        SubscribeFreePlanView.as_view(),
        name='subscription-subscribe-free',
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
