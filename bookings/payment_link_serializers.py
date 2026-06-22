from rest_framework import serializers

from .models import QuotationPayment, QuotationPaymentLink
from .payment_links import (
    PaymentLinkError,
    provider_checkout_url,
    public_payment_url,
    xendit_payment_return_urls,
)
from .payment_providers import PROVIDER_LABELS


class QuotationPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationPayment
        fields = [
            'id',
            'amount',
            'charge_amount',
            'base_amount',
            'platform_fee',
            'processing_fee',
            'net_amount',
            'tax',
            'payment_method',
            'transaction_id',
            'transaction_status',
            'transaction_date',
            'created_at',
            'notes',
        ]
        read_only_fields = fields


class QuotationPaymentLinkSerializer(serializers.ModelSerializer):
    public_url = serializers.SerializerMethodField()
    checkout_url = serializers.SerializerMethodField()
    payment_provider_label = serializers.SerializerMethodField()

    class Meta:
        model = QuotationPaymentLink
        fields = [
            'id',
            'public_token',
            'status',
            'payment_provider',
            'payment_provider_label',
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

    def get_public_url(self, obj: QuotationPaymentLink) -> str:
        if obj.payment_provider == QuotationPaymentLink.PaymentProvider.XENDIT:
            try:
                _, _, public_url = xendit_payment_return_urls(obj.public_token)
                return public_url
            except PaymentLinkError:
                pass
        return public_payment_url(obj.public_token)

    def get_checkout_url(self, obj: QuotationPaymentLink) -> str:
        if obj.status != QuotationPaymentLink.Status.PENDING:
            return ''
        return provider_checkout_url(obj)

    def get_payment_provider_label(self, obj: QuotationPaymentLink) -> str:
        return PROVIDER_LABELS.get(obj.payment_provider, obj.payment_provider.title())
