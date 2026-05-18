from rest_framework import serializers

from .models import SupplierSetting, SupplierSettingTier, SupplierType, Tier


class SupplierTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierType
        fields = ['id', 'name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = fields


class TierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tier
        fields = ['id', 'name', 'is_active', 'created_at']
        read_only_fields = fields


class SupplierOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='supplier_setting.supplier_id')
    name = serializers.CharField(source='supplier_setting.supplier.name')
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    discount_type = serializers.CharField()
    price_adjustment = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    price_adjustment_type = serializers.CharField()
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )


class SupplierOptionQuerySerializer(serializers.Serializer):
    tier_id = serializers.IntegerField(required=False)

    def validate_tier_id(self, value):
        account_id = self.context['request'].user.account_id
        if not Tier.objects.filter(
            pk=value,
            account_id=account_id,
            is_active=True,
            deleted_at__isnull=True,
        ).exists():
            raise serializers.ValidationError('Invalid or inactive tier.')
        return value


class SupplierListOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='supplier_id')
    name = serializers.CharField(source='supplier.name')


class SupplierTierQuerySerializer(serializers.Serializer):
    supplier_id = serializers.IntegerField()

    def validate_supplier_id(self, value):
        account_id = self.context['request'].user.account_id
        if not SupplierSetting.objects.filter(
            account_id=account_id,
            supplier_id=value,
            is_active=True,
            supplier__is_active=True,
        ).exists():
            raise serializers.ValidationError(
                'Invalid or inactive supplier for this account.',
            )
        return value


class SupplierTierOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='tier_id')
    name = serializers.CharField(source='tier.name')
    is_active = serializers.BooleanField(source='tier.is_active')
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    discount_type = serializers.CharField()
    price_adjustment = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    price_adjustment_type = serializers.CharField()
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
