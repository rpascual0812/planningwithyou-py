from django.urls import path

from .views import BookingViewConfigView

urlpatterns = [
    path(
        'config/booking-view/',
        BookingViewConfigView.as_view(),
        name='config-booking-view',
    ),
]
