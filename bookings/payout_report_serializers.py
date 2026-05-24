from rest_framework import serializers

from .models import BookingPayment


class BookingPaymentPayoutReportSerializer(serializers.ModelSerializer):
    booking_unique_id = serializers.CharField(
        source='booking.unique_id',
        read_only=True,
    )
    booking_title = serializers.CharField(source='booking.title', read_only=True)
    booking_credit = serializers.DecimalField(
        source='base_amount',
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    payout_sent = serializers.SerializerMethodField()

    class Meta:
        model = BookingPayment
        fields = [
            'id',
            'booking',
            'booking_unique_id',
            'booking_title',
            'booking_credit',
            'payment_method',
            'transaction_id',
            'transaction_status',
            'transaction_date',
            'payout_sent_at',
            'payout_sent',
            'created_at',
        ]
        read_only_fields = fields

    def get_payout_sent(self, obj: BookingPayment) -> bool:
        return obj.payout_sent_at is not None
