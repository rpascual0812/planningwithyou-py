from rest_framework import serializers

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

    class Meta:
        model = Contact
        fields = [
            'id', 'first_name', 'last_name', 'email', 'company', 'notes',
            'phone_numbers', 'addresses', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        numbers_data = validated_data.pop('phone_numbers', [])
        addresses_data = validated_data.pop('addresses', [])
        request = self.context['request']
        validated_data['account_id'] = request.user.account_id
        validated_data['company_org_id'] = request.user.company_id
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
