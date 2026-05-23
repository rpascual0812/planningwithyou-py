from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company
from planningwithyou.permissions import HasAccount

from .models import PaymentIntegration
from .paymongo_onboarding import (
    PayMongoOnboardingError,
    disconnect_paymongo_integration,
    refresh_paymongo_integration,
    start_paymongo_onboarding,
)
from .serializers import PayMongoIntegrationSerializer


class CompanyPayMongoIntegrationView(APIView):
    """PayMongo Platforms child account for a company on the user's account."""

    permission_classes = [IsAuthenticated, HasAccount]

    def _company(self, request, company_id: int) -> Company | None:
        return Company.objects.filter(
            pk=company_id,
            account_id=request.user.account_id,
        ).first()

    def _response(self, company: Company, request) -> Response:
        serializer = PayMongoIntegrationSerializer(
            instance={},
            context={'company': company, 'request': request},
        )
        return Response(serializer.data)

    def get(self, request, company_id: int):
        company = self._company(request, company_id)
        if company is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return self._response(company, request)

    def put(self, request, company_id: int):
        """Start or continue PayMongo Platforms onboarding."""
        company = self._company(request, company_id)
        if company is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            start_paymongo_onboarding(company, created_by=request.user)
        except PayMongoOnboardingError as exc:
            body = {'detail': str(exc)}
            if exc.status_code is not None:
                body['paymongo_status'] = exc.status_code
            return Response(body, status=status.HTTP_400_BAD_REQUEST)
        return self._response(company, request)

    def delete(self, request, company_id: int):
        company = self._company(request, company_id)
        if company is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        disconnect_paymongo_integration(company.pk)
        return self._response(company, request)


class CompanyPayMongoIntegrationRefreshView(APIView):
    """POST — sync child account status from PayMongo."""

    permission_classes = [IsAuthenticated, HasAccount]

    def post(self, request, company_id: int):
        company = Company.objects.filter(
            pk=company_id,
            account_id=request.user.account_id,
        ).first()
        if company is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        integration = PaymentIntegration.objects.filter(
            company_id=company.pk,
            payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
        ).first()
        if integration is None or not (integration.paymongo_account_id or '').strip():
            return Response(
                {'detail': 'PayMongo is not connected for this company.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            refresh_paymongo_integration(integration)
        except PayMongoOnboardingError as exc:
            body = {'detail': str(exc)}
            if exc.status_code is not None:
                body['paymongo_status'] = exc.status_code
            return Response(body, status=status.HTTP_400_BAD_REQUEST)
        serializer = PayMongoIntegrationSerializer(
            instance={},
            context={'company': company, 'request': request},
        )
        return Response(serializer.data)
