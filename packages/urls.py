from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PackagePriceViewSet, PackageVersionViewSet

router = DefaultRouter()
router.register('package-prices', PackagePriceViewSet, basename='package-price')
router.register('package-versions', PackageVersionViewSet, basename='package-version')

urlpatterns = [
    path('', include(router.urls)),
]
