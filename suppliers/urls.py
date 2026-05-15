from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SupplierTypeViewSet

router = DefaultRouter()
router.register('supplier-types', SupplierTypeViewSet, basename='supplier-type')

urlpatterns = [
    path('', include(router.urls)),
]
