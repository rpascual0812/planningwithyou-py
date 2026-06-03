from rest_framework import serializers

from .models import QuotationPayment


class QuotationPaymentPayoutReportSerializer(serializers.ModelSerializer):
    quotation_unique_id = serializers.CharField(
        source='quotation.unique_id',
        read_only=True,
    )
    quotation_title = serializers.CharField(source='quotation.title', read_only=True)
    quotation_credit = serializers.DecimalField(
        source='base_amount',
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    payout_sent = serializers.SerializerMethodField()

    class Meta:
        model = QuotationPayment
        fields = [
            'id',
            'quotation',
            'quotation_unique_id',
            'quotation_title',
            'quotation_credit',
            'payment_method',
            'notes',
            'transaction_id',
            'transaction_status',
            'transaction_date',
            'payout_sent_at',
            'payout_sent',
            'created_at',
        ]
        read_only_fields = fields

    def get_payout_sent(self, obj: QuotationPayment) -> bool:
        return obj.payout_sent_at is not None
