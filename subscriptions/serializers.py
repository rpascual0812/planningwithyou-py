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


class AccountSubscriptionSerializer(serializers.ModelSerializer):
    plan = serializers.CharField(source='subscription.plan', read_only=True)
    plan_name = serializers.CharField(source='subscription.name', read_only=True)
    billing_cycle = serializers.CharField(
        source='subscription.billing_cycle',
        read_only=True,
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
            'base_price',
            'total_per_users',
            'total_price',
            'discount_code',
        ]
        read_only_fields = fields
