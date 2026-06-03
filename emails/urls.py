from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .gmail_views import GmailIntegrationView, GmailOAuthCallbackView
from .views import (
    EmailBookingTemplateViewSet,
    EmailCalendarTemplateViewSet,
    EmailLogViewSet,
    EmailUserTemplateViewSet,
)

router = DefaultRouter()
router.register('emails', EmailLogViewSet, basename='email')
router.register(
    'email-templates/users',
    EmailUserTemplateViewSet,
    basename='email-template-users',
)
router.register(
    'email-templates/quotations',
    EmailBookingTemplateViewSet,
    basename='email-template-quotations',
)
router.register(
    'email-templates/calendar',
    EmailCalendarTemplateViewSet,
    basename='email-template-calendar',
)

urlpatterns = [
    path('email-integrations/gmail/', GmailIntegrationView.as_view()),
    path(
        'email-integrations/gmail/oauth/callback/',
        GmailOAuthCallbackView.as_view(),
    ),
    path('', include(router.urls)),
]
