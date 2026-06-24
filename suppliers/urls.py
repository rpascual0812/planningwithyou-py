from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .booking_package_views import BookingSupplierPackageView
from .views import (
    PackageViewSet,
    PublicSupplierTypeListView,
    SupplierOptionListView,
    SupplierPackageListView,
    SupplierTypeViewSet,
)

router = DefaultRouter()
router.register('supplier-types', SupplierTypeViewSet, basename='supplier-type')
router.register('packages', PackageViewSet, basename='package')

urlpatterns = [
    path(
        'public/supplier-types/',
        PublicSupplierTypeListView.as_view(),
        name='public-supplier-types',
    ),
    path('supplier-options/', SupplierOptionListView.as_view(), name='supplier-options'),
    path('supplier-packages/', SupplierPackageListView.as_view(), name='supplier-packages'),
    path(
        'booking-supplier-package/',
        BookingSupplierPackageView.as_view(),
        name='booking-supplier-package',
    ),
    path('', include(router.urls)),
]
