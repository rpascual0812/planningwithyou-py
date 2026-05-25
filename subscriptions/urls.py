from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountSubscriptionCurrentView,
    SubscriptionCheckoutPreviewView,
    SubscriptionCheckoutView,
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
    path('', include(router.urls)),
]
