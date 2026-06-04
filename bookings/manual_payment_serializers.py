from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from .payment_breakdown import booking_payments_paid_base_total

MANUAL_PAYMENT_METHODS = ('Cash', 'Cheque', 'Bank Transfer')


class ManualQuotationPaymentCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=('payment', 'refund'),
        default='payment',
        required=False,
    )
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    payment_method = serializers.ChoiceField(choices=MANUAL_PAYMENT_METHODS)
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_amount(self, value: Decimal) -> Decimal:
        try:
            quantized = value.quantize(Decimal('0.01'))
        except InvalidOperation as exc:
            raise serializers.ValidationError('Invalid amount.') from exc
        if quantized <= Decimal('0'):
            raise serializers.ValidationError('Amount must be greater than zero.')
        return quantized

    def validate(self, attrs):
        if attrs.get('kind', 'payment') != 'refund':
            return attrs
        quotation = self.context.get('quotation')
        if quotation is not None:
            paid = booking_payments_paid_base_total(quotation.pk)
            if attrs['amount'] > paid:
                raise serializers.ValidationError(
                    {
                        'amount': (
                            f'Refund amount cannot exceed {paid} already paid on this quotation.'
                        ),
                    },
                )
        return attrs


class ManualQuotationRefundCreateSerializer(ManualQuotationPaymentCreateSerializer):
    kind = serializers.ChoiceField(choices=('refund',), default='refund')
