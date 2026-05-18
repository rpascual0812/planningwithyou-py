from django.urls import path

from .views import BookingViewConfigView, BookingsGroupNameConfigView

urlpatterns = [
    path(
        'config/booking-view/',
        BookingViewConfigView.as_view(),
        name='config-booking-view',
    ),
    path(
        'config/bookings-group-name/',
        BookingsGroupNameConfigView.as_view(),
        name='config-bookings-group-name',
    ),
]
