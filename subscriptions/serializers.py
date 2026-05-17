from rest_framework import serializers

from .models import Subscription


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
