from django.utils import timezone
from rest_framework import serializers

from companies.models import Company

from .models import Package, PackageItem, PackageVersion


def _default_package_version_for_company(account_id, company_id, created_by=None):
    version = (
        PackageVersion.objects.filter(
            account_id=account_id,
            company_id=company_id,
            deleted_at__isnull=True,
        )
        .order_by('title', 'id')
        .first()
    )
    if version is not None:
        return version
    return PackageVersion.objects.create(
        title='Default',
        description='',
        effectivity_date=timezone.now(),
        is_active=True,
        account_id=account_id,
        company_id=company_id,
        created_by=created_by,
    )


class PackageVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageVersion
        fields = [
            'id',
            'title',
            'description',
            'effectivity_date',
            'is_active',
            'company',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields['company'].read_only = True

    def validate_company(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.account_id != request.user.account_id:
            raise serializers.ValidationError('Invalid company.')
        if not value.is_active or value.deleted_at is not None:
            raise serializers.ValidationError('Company must be active.')
        return value


class PackageItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageItem
        fields = ['id', 'title', 'price', 'is_active']
        read_only_fields = ['id']

    def validate_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Price must be 0 or greater.')
        return value


class PackageSerializer(serializers.ModelSerializer):
    items = PackageItemSerializer(many=True, required=False)

    class Meta:
        model = Package
        fields = [
            'id',
            'package_version',
            'title',
            'description',
            'total_price',
            'company',
            'is_active',
            'items',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request is not None:
            self.fields['package_version'].queryset = PackageVersion.objects.filter(
                account_id=request.user.account_id,
                deleted_at__isnull=True,
            )
        if self.instance is not None:
            self.fields['company'].read_only = True
            self.fields['package_version'].read_only = True
        elif self.context.get('request'):
            self.fields['package_version'].required = False

    def validate_package_version(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.account_id != request.user.account_id:
            raise serializers.ValidationError('Invalid package version.')
        if not value.is_active or value.deleted_at is not None:
            raise serializers.ValidationError('Package version must be active.')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get('request')
        if request is None:
            return attrs
        version = attrs.get('package_version')
        company = attrs.get('company')
        if version is not None and company is not None:
            if version.company_id != company.id:
                raise serializers.ValidationError(
                    {'package_version': 'Package version must belong to the selected company.'},
                )
        elif version is not None and self.instance is not None:
            if version.company_id != self.instance.company_id:
                raise serializers.ValidationError(
                    {'package_version': 'Package version must belong to the package company.'},
                )
        return attrs

    def validate_company(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.account_id != request.user.account_id:
            raise serializers.ValidationError('Invalid company.')
        if not value.is_active or value.deleted_at is not None:
            raise serializers.ValidationError('Company must be active.')
        return value

    def _create_items(self, package, items_data):
        request = self.context.get('request')
        created_by = request.user if request and request.user.is_authenticated else None
        for item_data in items_data:
            PackageItem.objects.create(
                package=package,
                account_id=package.account_id,
                company_id=package.company_id,
                created_by=created_by,
                is_active=item_data.get('is_active', True),
                title=item_data['title'],
                price=item_data.get('price', 0),
            )

    def _replace_items(self, package, items_data):
        now = timezone.now()
        package.items.filter(deleted_at__isnull=True).update(deleted_at=now)
        self._create_items(package, items_data)

    def create(self, validated_data):
        request = self.context.get('request')
        items_data = validated_data.pop('items', [])
        if validated_data.get('package_version') is None and request is not None:
            company = validated_data['company']
            validated_data['package_version'] = _default_package_version_for_company(
                request.user.account_id,
                company.id,
                created_by=request.user,
            )
        package = super().create(validated_data)
        if items_data:
            self._create_items(package, items_data)
        return package

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        package = super().update(instance, validated_data)
        if items_data is not None:
            self._replace_items(package, items_data)
        return package
