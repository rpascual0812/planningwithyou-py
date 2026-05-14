from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DocumentFolderViewSet, DocumentViewSet

router = DefaultRouter()
router.register('documents', DocumentViewSet, basename='document')
router.register('document-folders', DocumentFolderViewSet, basename='document-folder')

urlpatterns = [
    path('', include(router.urls)),
]
