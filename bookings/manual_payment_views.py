from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .manual_payment_serializers import (
    ManualQuotationPaymentCreateSerializer,
    ManualQuotationRefundCreateSerializer,
)
from .manual_payments import create_manual_quotation_payment, create_manual_quotation_refund
from .payment_link_serializers import QuotationPaymentSerializer
from .scope import assert_booking_editable, bookings_for_user


def _create_manual_payment_response(request, quotation_id: int, *, refund: bool):
    quotation = get_object_or_404(bookings_for_user(request.user), pk=quotation_id)
    assert_booking_editable(quotation, request.user)
    serializer_class = (
        ManualQuotationRefundCreateSerializer
        if refund
        else ManualQuotationPaymentCreateSerializer
    )
    serializer = serializer_class(
        data=request.data,
        context={'quotation': quotation},
    )
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    is_refund = refund or data.get('kind') == 'refund'
    create_fn = (
        create_manual_quotation_refund if is_refund else create_manual_quotation_payment
    )
    try:
        payment = create_fn(
            quotation,
            amount=data['amount'],
            payment_method=data['payment_method'],
            notes=data.get('notes') or '',
        )
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        QuotationPaymentSerializer(payment).data,
        status=status.HTTP_201_CREATED,
    )


class QuotationManualPaymentCreateView(APIView):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'quotations'

    def post(self, request, quotation_id: int):
        return _create_manual_payment_response(request, quotation_id, refund=False)


class QuotationManualRefundCreateView(APIView):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'quotations'

    def post(self, request, quotation_id: int):
        return _create_manual_payment_response(request, quotation_id, refund=True)
