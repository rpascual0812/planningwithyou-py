from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company
from planningwithyou.permissions import HasAccount

from .models import PaymentIntegration
from .serializers import PayMongoIntegrationSerializer


class CompanyPayMongoIntegrationView(APIView):
    """GET/PUT/DELETE PayMongo credentials for a company on the user's account."""

    permission_classes = [IsAuthenticated, HasAccount]

    def _company(self, request, company_id: int) -> Company | None:
        return (
            Company.objects.filter(
                pk=company_id,
                account_id=request.user.account_id,
            )
            .first()
        )

    def get(self, request, company_id: int):
        company = self._company(request, company_id)
        if company is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = PayMongoIntegrationSerializer(
            instance={},
            context={'company': company, 'request': request},
        )
        return Response(serializer.data)

    def put(self, request, company_id: int):
        company = self._company(request, company_id)
        if company is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = PayMongoIntegrationSerializer(
            data=request.data,
            context={'company': company, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            PayMongoIntegrationSerializer(
                instance={},
                context={'company': company, 'request': request},
            ).data,
        )

    def delete(self, request, company_id: int):
        company = self._company(request, company_id)
        if company is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        integration = PaymentIntegration.objects.filter(
            company_id=company.pk,
            payment_gateway=PaymentIntegration.PaymentGateway.PAYMONGO,
        ).first()
        if integration is not None:
            integration.deleted_at = timezone.now()
            integration.save(update_fields=['deleted_at', 'updated_at'])
        return Response(
            PayMongoIntegrationSerializer(
                instance={},
                context={'company': company, 'request': request},
            ).data,
        )
