from django.contrib.auth import get_user_model
from rest_framework import serializers

from .registration import RegistrationInput, register_tenant

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    company_name = serializers.CharField(max_length=255)
    supplier_type_id = serializers.IntegerField(min_value=1)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    mobile_number = serializers.CharField(max_length=63)
    phone_number = serializers.CharField(
        max_length=63,
        required=False,
        allow_blank=True,
        default='',
    )
    password = serializers.CharField(min_length=6, write_only=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                'An account with this email already exists.',
            )
        return value

    def create(self, validated_data):
        try:
            result = register_tenant(
                RegistrationInput(
                    company_name=validated_data['company_name'],
                    supplier_type_id=validated_data['supplier_type_id'],
                    first_name=validated_data['first_name'],
                    last_name=validated_data['last_name'],
                    email=validated_data['email'],
                    mobile_number=validated_data['mobile_number'],
                    phone_number=validated_data.get('phone_number') or '',
                    password=validated_data['password'],
                ),
            )
        except ValueError as exc:
            raise serializers.ValidationError({'detail': str(exc)}) from exc
        self.context['registration_result'] = result
        return result.user
