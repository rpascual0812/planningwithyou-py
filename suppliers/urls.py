from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SupplierOptionListView, SupplierTypeViewSet, TierViewSet

router = DefaultRouter()
router.register('supplier-types', SupplierTypeViewSet, basename='supplier-type')
router.register('tiers', TierViewSet, basename='tier')

urlpatterns = [
    path('supplier-options/', SupplierOptionListView.as_view(), name='supplier-options'),
    path('', include(router.urls)),
]
