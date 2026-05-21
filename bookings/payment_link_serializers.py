from rest_framework import serializers

from .models import BookingPaymentLink
from .payment_links import public_payment_url


class BookingPaymentLinkSerializer(serializers.ModelSerializer):
    public_url = serializers.SerializerMethodField()
    checkout_url = serializers.SerializerMethodField()

    class Meta:
        model = BookingPaymentLink
        fields = [
            'id',
            'public_token',
            'status',
            'base_amount',
            'platform_fee',
            'processing_fee_estimate',
            'charge_amount',
            'currency',
            'expires_at',
            'paid_at',
            'paymongo_checkout_url',
            'checkout_url',
            'public_url',
            'created_at',
        ]
        read_only_fields = fields

    def get_public_url(self, obj: BookingPaymentLink) -> str:
        return public_payment_url(obj.public_token)

    def get_checkout_url(self, obj: BookingPaymentLink) -> str:
        if obj.status != BookingPaymentLink.Status.PENDING:
            return ''
        return obj.paymongo_checkout_url or ''
