from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BookingItemViewSet, BookingStatusViewSet, FormTemplateViewSet

router = DefaultRouter()
router.register('statuses', BookingStatusViewSet, basename='booking-status')
router.register('booking-items', BookingItemViewSet, basename='booking-item')
router.register('form-templates', FormTemplateViewSet, basename='form-template')

urlpatterns = [
    path('', include(router.urls)),
]
