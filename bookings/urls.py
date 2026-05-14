from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FormTemplateViewSet

router = DefaultRouter()
router.register('form-templates', FormTemplateViewSet, basename='form-template')

urlpatterns = [
    path('', include(router.urls)),
]
