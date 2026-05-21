from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from companies.models import Company
from suppliers.models import Tier

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
    children = serializers.SerializerMethodField()

    class Meta:
        model = PackageItem
        fields = ['id', 'title', 'price', 'is_active', 'children']
        read_only_fields = ['id']

    def get_children(self, obj):
        children = obj.children.filter(deleted_at__isnull=True).order_by('sort_order', 'id')
        return PackageItemSerializer(children, many=True, context=self.context).data


class PackageItemInputSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        default=0,
    )
    is_active = serializers.BooleanField(required=False, default=True)


PackageItemInputSerializer._declared_fields['children'] = PackageItemInputSerializer(
    many=True,
    required=False,
)


class PackageSerializer(serializers.ModelSerializer):
    items = PackageItemInputSerializer(many=True, required=False, write_only=True)
    tier_name = serializers.CharField(source='tier.name', read_only=True)

    class Meta:
        model = Package
        fields = [
            'id',
            'package_version',
            'tier',
            'tier_name',
            'description',
            'total_price',
            'required_downpayment_amount',
            'company',
            'is_active',
            'items',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'tier_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request is not None:
            self.fields['package_version'].queryset = PackageVersion.objects.filter(
                account_id=request.user.account_id,
                deleted_at__isnull=True,
            )
            self.fields['tier'].queryset = Tier.objects.filter(
                account_id=request.user.account_id,
                deleted_at__isnull=True,
            )
        if self.instance is not None:
            self.fields['company'].read_only = True
            self.fields['package_version'].read_only = True
        elif self.context.get('request'):
            self.fields['package_version'].required = False

    def to_representation(self, instance):
        data = super().to_representation(instance)
        roots = instance.items.filter(
            parent__isnull=True,
            deleted_at__isnull=True,
        ).order_by('sort_order', 'id')
        data['items'] = PackageItemSerializer(roots, many=True, context=self.context).data
        return data

    def validate_package_version(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.account_id != request.user.account_id:
            raise serializers.ValidationError('Invalid package version.')
        if not value.is_active or value.deleted_at is not None:
            raise serializers.ValidationError('Package version must be active.')
        return value

    def validate_company(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.account_id != request.user.account_id:
            raise serializers.ValidationError('Invalid company.')
        if not value.is_active or value.deleted_at is not None:
            raise serializers.ValidationError('Company must be active.')
        return value

    def validate_tier(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.account_id != request.user.account_id:
            raise serializers.ValidationError('Invalid tier.')
        if value.deleted_at is not None:
            raise serializers.ValidationError('Tier must be active.')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get('request')
        if request is None:
            return attrs
        version = attrs.get('package_version')
        company = attrs.get('company') or (self.instance.company if self.instance else None)
        tier = attrs.get('tier')
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
        if tier is not None and company is not None and tier.company_id != company.id:
            raise serializers.ValidationError(
                {'tier': 'Tier must belong to the selected company.'},
            )
        elif tier is not None and self.instance is not None and tier.company_id != self.instance.company_id:
            raise serializers.ValidationError(
                {'tier': 'Tier must belong to the package company.'},
            )

        company = company or (self.instance.company if self.instance else None)
        tier = tier or (self.instance.tier if self.instance else None)
        version = version or (self.instance.package_version if self.instance else None)
        total_price = attrs.get('total_price')
        if total_price is None and self.instance is not None:
            total_price = self.instance.total_price
        downpayment = attrs.get('required_downpayment_amount')
        if downpayment is None and self.instance is not None:
            downpayment = self.instance.required_downpayment_amount
        if (
            total_price is not None
            and downpayment is not None
            and downpayment >= total_price
        ):
            raise serializers.ValidationError(
                {
                    'required_downpayment_amount': (
                        'Downpayment must be less than total price.'
                    ),
                },
            )

        if company is not None and tier is not None and version is not None:
            is_active = attrs.get('is_active')
            if is_active is None:
                is_active = self.instance.is_active if self.instance is not None else True
            siblings = self._sibling_packages(company, tier, version)
            if self.instance is not None:
                siblings = siblings.exclude(pk=self.instance.pk)
            is_first = not siblings.exists()
            if is_first and not is_active:
                raise serializers.ValidationError(
                    {
                        'is_active': (
                            'The first package for this company, tier, and version must be active.'
                        ),
                    },
                )
            if not is_active and not siblings.filter(is_active=True).exists():
                raise serializers.ValidationError(
                    {
                        'is_active': (
                            'At least one package must remain active for this company, tier, and version.'
                        ),
                    },
                )
        return attrs

    def _sibling_packages(self, company, tier, package_version):
        return Package.objects.filter(
            company=company,
            tier=tier,
            package_version=package_version,
            deleted_at__isnull=True,
        )

    @staticmethod
    def _deactivate_other_active_packages(package):
        Package.objects.filter(
            company_id=package.company_id,
            tier_id=package.tier_id,
            package_version_id=package.package_version_id,
            deleted_at__isnull=True,
            is_active=True,
        ).exclude(pk=package.pk).update(is_active=False)

    def _create_item_tree(self, package, items_data, parent=None, created_by=None):
        for sort_order, item_data in enumerate(items_data):
            children_data = item_data.pop('children', [])
            item = PackageItem.objects.create(
                package=package,
                parent=parent,
                account_id=package.account_id,
                company_id=package.company_id,
                created_by=created_by,
                sort_order=sort_order,
                is_active=item_data.get('is_active', True),
                title=item_data['title'],
                price=item_data.get('price', 0),
            )
            if children_data:
                self._create_item_tree(
                    package,
                    children_data,
                    parent=item,
                    created_by=created_by,
                )

    def _replace_items(self, package, items_data):
        now = timezone.now()
        package.items.filter(deleted_at__isnull=True).update(deleted_at=now)
        request = self.context.get('request')
        created_by = request.user if request and request.user.is_authenticated else None
        self._create_item_tree(package, items_data, parent=None, created_by=created_by)

    @transaction.atomic
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
        siblings = self._sibling_packages(
            validated_data['company'],
            validated_data['tier'],
            validated_data['package_version'],
        )
        if not siblings.exists():
            validated_data['is_active'] = True
        package = super().create(validated_data)
        if package.is_active:
            self._deactivate_other_active_packages(package)
        if items_data:
            created_by = request.user if request and request.user.is_authenticated else None
            self._create_item_tree(package, items_data, parent=None, created_by=created_by)
        return package

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        package = super().update(instance, validated_data)
        if package.is_active:
            self._deactivate_other_active_packages(package)
        if items_data is not None:
            self._replace_items(package, items_data)
        return package
