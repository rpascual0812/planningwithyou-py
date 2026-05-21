from django.db import transaction
from rest_framework import serializers

from planningwithyou.file_storage import company_logo_public_url
from suppliers.models import SupplierType

from .logo_image import delete_company_logo, save_company_logo
from .models import Company


class SupplierCompanyTierPricingItemSerializer(serializers.Serializer):
    tier_id = serializers.IntegerField()
    tier_name = serializers.CharField(read_only=True)
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True,
    )
    discount_type = serializers.ChoiceField(
        choices=['percent', 'fixed'],
        required=False,
        default='percent',
    )
    mark_up = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True,
    )
    mark_up_type = serializers.ChoiceField(
        choices=['percent', 'fixed'],
        required=False,
        default='percent',
    )
    price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        read_only=True,
    )
    original_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        read_only=True,
    )


class SupplierCompanyTierPricingSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    tiers = SupplierCompanyTierPricingItemSerializer(many=True)

    def validate_tiers(self, value):
        supplier_company = self.context.get('supplier_company')
        if supplier_company is None:
            raise serializers.ValidationError('No supplier company for tiers.')
        from suppliers.models import Tier

        valid_ids = set(
            Tier.objects.filter(
                company_id=supplier_company.id,
                is_active=True,
                deleted_at__isnull=True,
            ).values_list('id', flat=True),
        )
        for item in value:
            if item['tier_id'] not in valid_ids:
                raise serializers.ValidationError(
                    f'Invalid or inactive tier id {item["tier_id"]}.',
                )
        return value


class CompanySerializer(serializers.ModelSerializer):
    supplier_type_name = serializers.CharField(
        source='supplier_type.name',
        read_only=True,
    )
    supplier_tiers = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()
    currency_code = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    logo_upload = serializers.FileField(write_only=True, required=False, allow_null=True)
    max_bookings_per_day = serializers.IntegerField(
        required=False,
        default=1,
        min_value=1,
    )

    class Meta:
        model = Company
        fields = [
            'id',
            'name',
            'supplier_type',
            'supplier_type_name',
            'supplier_tiers',
            'currency_symbol',
            'currency_code',
            'timezone',
            'contact_person',
            'phone_number',
            'mobile_number',
            'address',
            'website',
            'is_active',
            'is_main',
            'kyb_verified',
            'max_bookings_per_day',
            'logo',
            'logo_upload',
            'logo_url',
            'sort_order',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'kyb_verified',
            'logo',
            'logo_url',
            'supplier_type_name',
            'currency_symbol',
            'currency_code',
        ]

    def _country_for_company(self, company):
        account = getattr(company, 'account', None)
        if account is None:
            return None
        return getattr(account, 'country', None)

    def get_currency_symbol(self, obj):
        country = self._country_for_company(obj)
        if country is None:
            return '$'
        return (country.currency_symbol or '').strip() or '$'

    def get_currency_code(self, obj):
        country = self._country_for_company(obj)
        if country is None:
            return 'USD'
        return (country.currency_code or '').strip() or 'USD'

    def get_supplier_tiers(self, obj):
        by_supplier = self.context.get('tier_pricing_by_supplier')
        if not by_supplier:
            return []
        return by_supplier.get(obj.id, [])

    def _supplier_setting_is_active(self, company):
        if not self.context.get('supplier_directory'):
            return company.is_active
        active_by_id = self.context.get('supplier_setting_active_by_id')
        if active_by_id is not None:
            return active_by_id.get(company.id, False)
        request = self.context.get('request')
        if request is not None:
            from users.supplier_price import supplier_setting_is_active

            return supplier_setting_is_active(company.id, request.user.account_id)
        annotated = getattr(company, '_supplier_setting_is_active', None)
        if annotated is not None:
            return annotated
        return False

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.context.get('supplier_directory'):
            data['is_active'] = self._supplier_setting_is_active(instance)
        return data

    def validate_supplier_type(self, value):
        if not SupplierType.objects.filter(pk=value.pk, is_active=True).exists():
            raise serializers.ValidationError('Invalid or inactive supplier type.')
        return value

    def get_logo_url(self, obj):
        return company_logo_public_url(
            obj.logo,
            obj.pk,
            request=self.context.get('request'),
        )

    def validate_name(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Name is required.')
        return value

    def validate_website(self, value):
        return (value or '').strip()

    def validate_timezone(self, value):
        return (value or '').strip()

    def validate_contact_person(self, value):
        return (value or '').strip()

    def validate_phone_number(self, value):
        return (value or '').strip()

    def validate_mobile_number(self, value):
        return (value or '').strip()

    def validate_address(self, value):
        return (value or '').strip()

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            payload = data.copy()
        else:
            payload = dict(data)
        logo_val = payload.get('logo')
        if logo_val is not None and hasattr(logo_val, 'read'):
            payload['logo_upload'] = logo_val
            del payload['logo']
        return super().to_internal_value(payload)

    def _clear_other_main_companies(
        self,
        account_id: int,
        *,
        exclude_pk: int | None = None,
    ) -> None:
        """Unset main on siblings before setting ``is_main=True`` (DB unique constraint)."""
        qs = Company.all_objects.filter(account_id=account_id, is_main=True)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        qs.update(is_main=False)

    def _apply_logo_upload(self, instance, logo_upload):
        if logo_upload is serializers.empty:
            return
        try:
            if logo_upload:
                instance.logo = save_company_logo(
                    instance.account_id,
                    instance.pk,
                    logo_upload,
                    old_logo=instance.logo or '',
                    request=self.context.get('request'),
                )
            else:
                delete_company_logo(
                    instance.logo,
                    account_id=instance.account_id,
                    company_id=instance.pk,
                )
                instance.logo = ''
        except ValueError as exc:
            raise serializers.ValidationError({'logo_upload': str(exc)}) from exc
        instance.save(update_fields=['logo'])

    def _will_be_main(self, validated_data, instance=None) -> bool:
        if 'is_main' in validated_data:
            return bool(validated_data['is_main'])
        return bool(instance and instance.is_main)

    @transaction.atomic
    def create(self, validated_data):
        logo_upload = validated_data.pop('logo_upload', serializers.empty)
        account_id = validated_data.get('account_id')
        if self._will_be_main(validated_data) and account_id is not None:
            self._clear_other_main_companies(account_id)
        instance = super().create(validated_data)
        self._apply_logo_upload(instance, logo_upload)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        logo_upload = validated_data.pop('logo_upload', serializers.empty)
        if self.context.get('supplier_directory') and 'is_active' in validated_data:
            is_active = validated_data.pop('is_active')
            request = self.context.get('request')
            if request is not None:
                from users.supplier_price import set_supplier_setting_active

                set_supplier_setting_active(
                    instance.id,
                    request.user.account_id,
                    is_active,
                )
        if self._will_be_main(validated_data, instance):
            self._clear_other_main_companies(
                instance.account_id,
                exclude_pk=instance.pk,
            )
        instance = super().update(instance, validated_data)
        self._apply_logo_upload(instance, logo_upload)
        return instance
