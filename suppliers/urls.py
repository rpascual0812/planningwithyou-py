from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .booking_package_views import BookingSupplierPackageView
from .views import (
    PublicSupplierTypeListView,
    SupplierOptionListView,
    SupplierTierListView,
    SupplierTypeViewSet,
    TierViewSet,
)

router = DefaultRouter()
router.register('supplier-types', SupplierTypeViewSet, basename='supplier-type')
router.register('tiers', TierViewSet, basename='tier')

urlpatterns = [
    path(
        'public/supplier-types/',
        PublicSupplierTypeListView.as_view(),
        name='public-supplier-types',
    ),
    path('supplier-options/', SupplierOptionListView.as_view(), name='supplier-options'),
    path('supplier-tiers/', SupplierTierListView.as_view(), name='supplier-tiers'),
    path(
        'booking-supplier-package/',
        BookingSupplierPackageView.as_view(),
        name='booking-supplier-package',
    ),
    path('', include(router.urls)),
]
