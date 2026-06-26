from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import UserNotificationViewSet

router = DefaultRouter()
router.register('user-notifications', UserNotificationViewSet, basename='user-notification')

urlpatterns = [
    path('', include(router.urls)),
]
