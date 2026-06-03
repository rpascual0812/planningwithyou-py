from decimal import Decimal, InvalidOperation

from rest_framework import serializers

MANUAL_PAYMENT_METHODS = ('Cash', 'Cheque', 'Bank Transfer')


class ManualQuotationPaymentCreateSerializer(serializers.Serializer):
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
