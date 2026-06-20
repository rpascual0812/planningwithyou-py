from rest_framework import serializers

from .models import AccountSubscription, Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = [
            'id',
            'plan',
            'name',
            'subtitle',
            'features',
            'billing_cycle',
            'base_price',
            'price_per_user',
            'default_users',
            'has_team_stepper',
            'is_active',
            'is_selectable',
            'sort_order',
        ]
        read_only_fields = fields


class SubscriptionCheckoutSerializer(serializers.Serializer):
    plan = serializers.CharField(max_length=64)
    billing_cycle = serializers.ChoiceField(choices=Subscription.BillingCycle.choices)
    team_seats = serializers.IntegerField(min_value=1, default=1, required=False)
    discount_code = serializers.CharField(max_length=64, required=False, allow_blank=True)


class SubscribeFreePlanSerializer(serializers.Serializer):
    billing_cycle = serializers.ChoiceField(
        choices=Subscription.BillingCycle.choices,
        default=Subscription.BillingCycle.MONTHLY,
        required=False,
    )


class AccountSubscriptionSerializer(serializers.ModelSerializer):
    plan = serializers.CharField(source='subscription.plan', read_only=True)
    plan_name = serializers.CharField(source='subscription.name', read_only=True)
    billing_cycle = serializers.CharField(
        source='subscription.billing_cycle',
        read_only=True,
    )
    scheduled_plan = serializers.CharField(
        source='scheduled_subscription.plan',
        read_only=True,
        allow_null=True,
    )
    scheduled_plan_name = serializers.CharField(
        source='scheduled_subscription.name',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = AccountSubscription
        fields = [
            'uuid',
            'plan',
            'plan_name',
            'billing_cycle',
            'status',
            'team_seats',
            'start_date',
            'end_date',
            'scheduled_plan',
            'scheduled_plan_name',
            'scheduled_team_seats',
            'base_price',
            'total_per_users',
            'total_price',
            'discount_code',
        ]
        read_only_fields = fields


class SubscriptionPaymentReceiptSummarySerializer(serializers.ModelSerializer):
    class Meta:
        from .models import SubscriptionReceipt

        model = SubscriptionReceipt
        fields = ['id', 'receipt_number', 'receipt_url']
        read_only_fields = fields


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(
        source='account_subscription.subscription.name',
        read_only=True,
        default='',
    )
    receipt = serializers.SerializerMethodField()

    class Meta:
        from .models import SubscriptionPayment

        model = SubscriptionPayment
        fields = [
            'id',
            'amount',
            'currency',
            'paid_at',
            'period_start',
            'period_end',
            'description',
            'plan_name',
            'receipt',
            'created_at',
        ]
        read_only_fields = fields

    def get_receipt(self, obj):
        from .models import SubscriptionReceipt

        try:
            receipt = obj.receipt
        except SubscriptionReceipt.DoesNotExist:
            return None
        return SubscriptionPaymentReceiptSummarySerializer(receipt).data


class SubscriptionReceiptSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(
        source='payment.account_subscription.subscription.name',
        read_only=True,
    )
    amount = serializers.DecimalField(
        source='payment.amount',
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    paid_at = serializers.DateTimeField(source='payment.paid_at', read_only=True)
    period_start = serializers.DateField(source='payment.period_start', read_only=True)
    period_end = serializers.DateField(
        source='payment.period_end',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        from .models import SubscriptionReceipt

        model = SubscriptionReceipt
        fields = [
            'id',
            'receipt_number',
            'receipt_url',
            'plan_name',
            'amount',
            'paid_at',
            'period_start',
            'period_end',
            'created_at',
        ]
        read_only_fields = fields
