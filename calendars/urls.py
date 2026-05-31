from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .google_calendar_views import (
    GoogleCalendarIntegrationView,
    GoogleCalendarOAuthCallbackView,
    GoogleCalendarSyncView,
    GoogleCalendarWebhookView,
)
from .views import CalendarStatusViewSet, CalendarViewSet

router = DefaultRouter()
router.register('calendar-statuses', CalendarStatusViewSet, basename='calendar-status')
router.register('calendar-events', CalendarViewSet, basename='calendar-event')

urlpatterns = [
    path(
        'calendar-integrations/google/',
        GoogleCalendarIntegrationView.as_view(),
    ),
    path(
        'calendar-integrations/google/sync/',
        GoogleCalendarSyncView.as_view(),
    ),
    path(
        'calendar-integrations/google/oauth/callback/',
        GoogleCalendarOAuthCallbackView.as_view(),
    ),
    path(
        'webhooks/google-calendar/',
        GoogleCalendarWebhookView.as_view(),
    ),
    path('', include(router.urls)),
]
