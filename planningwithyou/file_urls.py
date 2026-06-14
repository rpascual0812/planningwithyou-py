from django.urls import path

from . import file_views

urlpatterns = [
    path(
        'files/d/<int:document_id>/',
        file_views.DocumentFileView.as_view(),
        name='secured-file-document',
    ),
    path(
        'files/b/<int:quotation_id>/pdf/',
        file_views.BookingPdfFileView.as_view(),
        name='secured-file-quotation-pdf',
    ),
    path(
        'files/r/<int:receipt_id>/pdf/',
        file_views.PaymentReceiptFileView.as_view(),
        name='secured-file-payment-receipt',
    ),
    path(
        'files/sr/<int:receipt_id>/pdf/',
        file_views.SubscriptionReceiptFileView.as_view(),
        name='secured-file-subscription-receipt',
    ),
    path(
        'files/c/<int:company_id>/logo/',
        file_views.CompanyLogoFileView.as_view(),
        name='secured-file-company-logo',
    ),
    path(
        'files/u/<int:user_id>/photo/',
        file_views.UserPhotoFileView.as_view(),
        name='secured-file-user-photo',
    ),
]
