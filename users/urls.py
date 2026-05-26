from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenRefreshView,
)

from .views import (
    AccountViewSet,
    EmailTokenObtainPairView,
    EmailVerifyView,
    PasswordResetConfirmView,
    RegisterView,
    RoleViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register('accounts', AccountViewSet, basename='account')
router.register('roles', RoleViewSet, basename='role')
router.register('users', UserViewSet, basename='user')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', EmailVerifyView.as_view(), name='verify_email'),
    path('token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path(
        'token/blacklist/',
        TokenBlacklistView.as_view(),
        name='token_blacklist',
    ),
    path(
        'reset-password/confirm/',
        PasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path('', include(router.urls)),
]
