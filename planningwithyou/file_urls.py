from django.urls import path

from . import file_views

urlpatterns = [
    path(
        'files/d/<int:document_id>/',
        file_views.DocumentFileView.as_view(),
        name='secured-file-document',
    ),
    path(
        'files/b/<int:booking_id>/pdf/',
        file_views.BookingPdfFileView.as_view(),
        name='secured-file-booking-pdf',
    ),
    path(
        'files/c/<int:company_id>/logo/',
        file_views.CompanyLogoFileView.as_view(),
        name='secured-file-company-logo',
    ),
]
