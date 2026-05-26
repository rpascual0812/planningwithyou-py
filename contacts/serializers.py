from rest_framework import serializers

from companies.models import Company

from .models import Contact, ContactAddress, ContactNumber


def _ensure_single_default(items: list[dict]) -> list[dict]:
    if not items:
        return items
    chosen = next((i for i, item in enumerate(items) if item.get('is_default')), 0)
    for i, item in enumerate(items):
        item['is_default'] = i == chosen
    return items


class ContactNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactNumber
        fields = ['id', 'number', 'label', 'is_default']


class ContactAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactAddress
        fields = [
            'id', 'label', 'street', 'city', 'state', 'zip_code', 'country',
            'is_default',
        ]


class ContactSerializer(serializers.ModelSerializer):
    phone_numbers = ContactNumberSerializer(many=True, required=False, default=[])
    addresses = ContactAddressSerializer(many=True, required=False, default=[])
    company_id = serializers.PrimaryKeyRelatedField(
        source='company_org',
        queryset=Company.objects.none(),
    )
    company_name = serializers.CharField(source='company_org.name', read_only=True)

    class Meta:
        model = Contact
        fields = [
            'id',
            'first_name',
            'last_name',
            'email',
            'company',
            'company_id',
            'company_name',
            'notes',
            'phone_numbers',
            'addresses',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request is not None:
            self.fields['company_id'].queryset = Company.objects.filter(
                account_id=request.user.account_id,
                deleted_at__isnull=True,
                is_active=True,
            )

    def validate_company_id(self, value):
        request = self.context.get('request')
        if request is None:
            return value
        if value.account_id != request.user.account_id:
            raise serializers.ValidationError('Invalid company.')
        if not value.is_active or value.deleted_at is not None:
            raise serializers.ValidationError('Company must be active.')
        from users.company_access import can_change_company

        if (
            value.pk != request.user.company_id
            and not can_change_company(request.user)
        ):
            raise serializers.ValidationError(
                'You may only assign contacts to your own company.',
            )
        return value

    def create(self, validated_data):
        numbers_data = validated_data.pop('phone_numbers', [])
        addresses_data = validated_data.pop('addresses', [])
        request = self.context['request']
        validated_data['account_id'] = request.user.account_id
        if 'company_org' not in validated_data:
            validated_data['company_org'] = Company.objects.get(
                pk=request.user.company_id,
            )
        contact = Contact.objects.create(**validated_data)
        for num in _ensure_single_default(numbers_data):
            ContactNumber.objects.create(
                contact=contact,
                account_id=contact.account_id,
                **num,
            )
        for addr in _ensure_single_default(addresses_data):
            ContactAddress.objects.create(
                contact=contact,
                account_id=contact.account_id,
                **addr,
            )
        return contact

    def update(self, instance, validated_data):
        numbers_data = validated_data.pop('phone_numbers', None)
        addresses_data = validated_data.pop('addresses', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if numbers_data is not None:
            instance.phone_numbers.all().delete()
            for num in _ensure_single_default(numbers_data):
                ContactNumber.objects.create(
                    contact=instance,
                    account_id=instance.account_id,
                    **num,
                )

        if addresses_data is not None:
            instance.addresses.all().delete()
            for addr in _ensure_single_default(addresses_data):
                ContactAddress.objects.create(
                    contact=instance,
                    account_id=instance.account_id,
                    **addr,
                )

        return instance
