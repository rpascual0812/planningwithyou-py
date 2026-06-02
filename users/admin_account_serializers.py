from rest_framework import serializers

from companies.models import Company

from .models import Account


class AdminAccountCompanySerializer(serializers.ModelSerializer):
    max_booking_per_day = serializers.IntegerField(source='max_bookings_per_day')
    user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Company
        fields = (
            'id',
            'name',
            'is_main',
            'contact_person',
            'contact_email',
            'kyb_verified',
            'user_count',
            'max_booking_per_day',
        )
        read_only_fields = fields


class AdminAccountListSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    company_count = serializers.IntegerField(read_only=True)
    user_count = serializers.IntegerField(read_only=True)
    companies = AdminAccountCompanySerializer(many=True, read_only=True)

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
            'companies',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields
