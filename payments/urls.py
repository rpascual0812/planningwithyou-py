from django.urls import path

from .views import CompanyPayMongoIntegrationView

urlpatterns = [
    path(
        'companies/<int:company_id>/payment-integrations/paymongo/',
        CompanyPayMongoIntegrationView.as_view(),
        name='company-paymongo-integration',
    ),
]
