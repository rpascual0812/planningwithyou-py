from django.urls import path

from .views import CompanyPayMongoIntegrationRefreshView, CompanyPayMongoIntegrationView

urlpatterns = [
    path(
        'companies/<int:company_id>/payment-integrations/paymongo/',
        CompanyPayMongoIntegrationView.as_view(),
        name='company-paymongo-integration',
    ),
    path(
        'companies/<int:company_id>/payment-integrations/paymongo/refresh/',
        CompanyPayMongoIntegrationRefreshView.as_view(),
        name='company-paymongo-integration-refresh',
    ),
]
