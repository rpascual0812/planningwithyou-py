from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BookingColumnViewSet, BookingItemViewSet, FormTemplateViewSet

router = DefaultRouter()
router.register('booking-columns', BookingColumnViewSet, basename='booking-column')
router.register('booking-items', BookingItemViewSet, basename='booking-item')
router.register('form-templates', FormTemplateViewSet, basename='form-template')

urlpatterns = [
    path('', include(router.urls)),
]
