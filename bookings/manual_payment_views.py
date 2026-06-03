from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .manual_payment_serializers import ManualQuotationPaymentCreateSerializer
from .manual_payments import create_manual_quotation_payment
from .payment_link_serializers import QuotationPaymentSerializer
from .scope import assert_booking_editable, bookings_for_user


class QuotationManualPaymentCreateView(APIView):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'quotations'

    def post(self, request, quotation_id: int):
        quotation = get_object_or_404(bookings_for_user(request.user), pk=quotation_id)
        assert_booking_editable(quotation, request.user)
        serializer = ManualQuotationPaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payment = create_manual_quotation_payment(
            quotation,
            amount=data['amount'],
            payment_method=data['payment_method'],
            notes=data.get('notes') or '',
        )
        return Response(
            QuotationPaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )
