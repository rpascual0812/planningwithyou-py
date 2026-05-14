from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EmailLogViewSet

router = DefaultRouter()
router.register('emails', EmailLogViewSet, basename='email')

urlpatterns = [
    path('', include(router.urls)),
]
