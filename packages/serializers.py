from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from companies.models import Company
from suppliers.models import Package

from .models import PackagePrice, PackageItem, PackageVersion


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


class PackagePriceSerializer(serializers.ModelSerializer):
    items = PackageItemInputSerializer(many=True, required=False, write_only=True)
    package_name = serializers.CharField(source='package.name', read_only=True)

    class Meta:
        model = PackagePrice
        fields = [
            'id',
            'package_version',
            'package',
            'package_name',
            'description',
            'total_price',
            'required_downpayment_amount',
            'company',
            'is_active',
            'items',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'package_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request is not None:
            self.fields['package_version'].queryset = PackageVersion.objects.filter(
                account_id=request.user.account_id,
                deleted_at__isnull=True,
            )
            self.fields['package'].queryset = Package.objects.filter(
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

    def validate_package(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.account_id != request.user.account_id:
            raise serializers.ValidationError('Invalid package.')
        if value.deleted_at is not None:
            raise serializers.ValidationError('Package must be active.')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get('request')
        if request is None:
            return attrs
        version = attrs.get('package_version')
        company = attrs.get('company') or (self.instance.company if self.instance else None)
        package = attrs.get('package')
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
        if package is not None and company is not None and package.company_id != company.id:
            raise serializers.ValidationError(
                {'package': 'Package must belong to the selected company.'},
            )
        elif package is not None and self.instance is not None and package.company_id != self.instance.company_id:
            raise serializers.ValidationError(
                {'package': 'Package must belong to the package company.'},
            )

        company = company or (self.instance.company if self.instance else None)
        package = package or (self.instance.package if self.instance else None)
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
            and downpayment > total_price
        ):
            raise serializers.ValidationError(
                {
                    'required_downpayment_amount': (
                        'Downpayment cannot exceed total price.'
                    ),
                },
            )

        if company is not None and package is not None and version is not None:
            is_active = attrs.get('is_active')
            if is_active is None:
                is_active = self.instance.is_active if self.instance is not None else True
            siblings = self._sibling_packages(company, package, version)
            if self.instance is not None:
                siblings = siblings.exclude(pk=self.instance.pk)
            is_first = not siblings.exists()
            if is_first and not is_active:
                raise serializers.ValidationError(
                    {
                        'is_active': (
                            'The first package for this company, package, and version must be active.'
                        ),
                    },
                )
            if not is_active and not siblings.filter(is_active=True).exists():
                raise serializers.ValidationError(
                    {
                        'is_active': (
                            'At least one package must remain active for this company, package, and version.'
                        ),
                    },
                )
        return attrs

    def _sibling_packages(self, company, package, package_version):
        return PackagePrice.objects.filter(
            company=company,
            package=package,
            package_version=package_version,
            deleted_at__isnull=True,
        )

    @staticmethod
    def _deactivate_other_active_packages(
        *,
        company_id,
        package_id,
        package_version_id,
        exclude_pk=None,
    ):
        qs = PackagePrice.objects.filter(
            company_id=company_id,
            package_id=package_id,
            package_version_id=package_version_id,
            deleted_at__isnull=True,
            is_active=True,
        )
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        qs.update(is_active=False)

    def _create_item_tree(self, package_price, items_data, parent=None, created_by=None):
        for sort_order, item_data in enumerate(items_data):
            children_data = item_data.pop('children', [])
            item = PackageItem.objects.create(
                package_price=package_price,
                parent=parent,
                account_id=package_price.account_id,
                company_id=package_price.company_id,
                created_by=created_by,
                sort_order=sort_order,
                is_active=item_data.get('is_active', True),
                title=item_data['title'],
                price=item_data.get('price', 0),
            )
            if children_data:
                self._create_item_tree(
                    package_price,
                    children_data,
                    parent=item,
                    created_by=created_by,
                )

    def _replace_items(self, package_price, items_data):
        now = timezone.now()
        package_price.items.filter(deleted_at__isnull=True).update(deleted_at=now)
        request = self.context.get('request')
        created_by = request.user if request and request.user.is_authenticated else None
        self._create_item_tree(package_price, items_data, parent=None, created_by=created_by)

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
            validated_data['package'],
            validated_data['package_version'],
        )
        if not siblings.exists():
            validated_data['is_active'] = True
        will_be_active = validated_data.get('is_active', True)
        if will_be_active:
            self._deactivate_other_active_packages(
                company_id=validated_data['company'].pk,
                package_id=validated_data['package'].pk,
                package_version_id=validated_data['package_version'].pk,
            )
        package_price = super().create(validated_data)
        if items_data:
            created_by = request.user if request and request.user.is_authenticated else None
            self._create_item_tree(package_price, items_data, parent=None, created_by=created_by)
        return package_price

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        package = validated_data.get('package', instance.package)
        package_id = package.pk if hasattr(package, 'pk') else package
        is_active = validated_data.get('is_active', instance.is_active)
        if is_active:
            self._deactivate_other_active_packages(
                company_id=instance.company_id,
                package_id=package_id,
                package_version_id=instance.package_version_id,
                exclude_pk=instance.pk,
            )
        package_price = super().update(instance, validated_data)
        if items_data is not None:
            self._replace_items(package_price, items_data)
        return package_price
