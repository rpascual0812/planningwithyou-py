from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .kyb_admin_views import CompanyKybVerificationAdminViewSet
from .views import CompanyViewSet

router = DefaultRouter()
router.register('companies', CompanyViewSet, basename='company')
router.register(
    'admin/kyb-verifications',
    CompanyKybVerificationAdminViewSet,
    basename='admin-kyb-verification',
)

urlpatterns = [
    path('', include(router.urls)),
]
