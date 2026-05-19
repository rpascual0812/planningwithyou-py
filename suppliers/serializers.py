from rest_framework import serializers

from companies.models import Company

from .models import SupplierSetting, SupplierSettingTier, SupplierType, Tier


class SupplierTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierType
        fields = ['id', 'name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = fields


class TierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tier
        fields = ['id', 'name', 'company', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_extra_kwargs(self):
        kwargs = super().get_extra_kwargs()
        if self.instance is not None:
            extra = dict(kwargs.get('company', {}))
            extra['read_only'] = True
            kwargs['company'] = extra
        return kwargs

    def validate_company(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.account_id != request.user.account_id:
            raise serializers.ValidationError('Invalid company.')
        if not value.is_active or value.deleted_at is not None:
            raise serializers.ValidationError('Company must be active.')
        return value


class SupplierOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='supplier_setting.supplier_id')
    name = serializers.CharField(source='supplier_setting.supplier.name')
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    discount_type = serializers.CharField()
    mark_up = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    mark_up_type = serializers.CharField()
    price_override = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    tax = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )


class SupplierOptionQuerySerializer(serializers.Serializer):
    tier_id = serializers.IntegerField(required=False)

    def validate_tier_id(self, value):
        company_id = self.context['request'].user.company_id
        if not Tier.objects.filter(
            pk=value,
            company_id=company_id,
            is_active=True,
            deleted_at__isnull=True,
        ).exists():
            raise serializers.ValidationError('Invalid or inactive tier.')
        return value


class SupplierListOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(source='supplier_id')
    name = serializers.CharField(source='supplier.name')


class CompanyListOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name']


class SupplierTierQuerySerializer(serializers.Serializer):
    supplier_id = serializers.IntegerField()

    def validate_supplier_id(self, value):
        account_id = self.context['request'].user.account_id
        if not Company.objects.filter(
            pk=value,
            account_id=account_id,
            is_active=True,
            deleted_at__isnull=True,
        ).exists():
            raise serializers.ValidationError(
                'Invalid or inactive company.',
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
    mark_up = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    mark_up_type = serializers.CharField()
    price_override = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    tax = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
