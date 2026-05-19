from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CalendarStatusViewSet, CalendarViewSet

router = DefaultRouter()
router.register('calendar-statuses', CalendarStatusViewSet, basename='calendar-status')
router.register('calendar-events', CalendarViewSet, basename='calendar-event')

urlpatterns = [
    path('', include(router.urls)),
]
