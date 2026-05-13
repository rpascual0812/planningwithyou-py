from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenRefreshView,
)

from .views import EmailTokenObtainPairView, UserViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')

urlpatterns = [
    path('token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path(
        'token/blacklist/',
        TokenBlacklistView.as_view(),
        name='token_blacklist',
    ),
    path('', include(router.urls)),
]
