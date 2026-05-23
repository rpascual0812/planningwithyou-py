from rest_framework import serializers

from .models import BookingPayment


class BookingPaymentPayoutAdminSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    booking_unique_id = serializers.CharField(
        source='booking.unique_id',
        read_only=True,
    )
    booking_title = serializers.CharField(source='booking.title', read_only=True)
    payout_sent = serializers.SerializerMethodField()

    class Meta:
        model = BookingPayment
        fields = [
            'id',
            'company',
            'company_name',
            'booking',
            'booking_unique_id',
            'booking_title',
            'base_amount',
            'platform_fee',
            'processing_fee',
            'net_amount',
            'charge_amount',
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


class BookingPaymentPayoutMarkSerializer(serializers.Serializer):
    payout_sent = serializers.BooleanField()

    def validate_payout_sent(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError(
                'Only marking payout as sent is supported.',
            )
        return value

    def save(self, **kwargs) -> BookingPayment:
        payment: BookingPayment = self.context['payment']
        if payment.payout_sent_at is None:
            from django.utils import timezone

            payment.payout_sent_at = timezone.now()
            payment.save(update_fields=['payout_sent_at', 'updated_at'])
        return payment
