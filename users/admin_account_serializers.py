from rest_framework import serializers

from .models import Account


class AdminAccountListSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    company_count = serializers.IntegerField(read_only=True)
    user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Account
        fields = (
            'id',
            'name',
            'is_active',
            'contact_person',
            'contact_email',
            'contact_mobile_number',
            'timezone',
            'country',
            'country_name',
            'paymongo_customer_id',
            'company_count',
            'user_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields
