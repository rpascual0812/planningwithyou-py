from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EmailLogViewSet, EmailUserTemplateViewSet

router = DefaultRouter()
router.register('emails', EmailLogViewSet, basename='email')
router.register(
    'email-templates/users',
    EmailUserTemplateViewSet,
    basename='email-template-users',
)

urlpatterns = [
    path('', include(router.urls)),
]
