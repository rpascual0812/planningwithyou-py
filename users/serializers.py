from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Account
from .supplier_price import (
    build_supplier_tiers_by_account,
    get_supplier_account_tier_pricing,
    parse_price_value,
    save_supplier_account_tier_pricing,
    set_supplier_tier_pricing,
)

User = get_user_model()


class SupplierAccountTierPricingItemSerializer(serializers.Serializer):
    tier_id = serializers.IntegerField()
    tier_name = serializers.CharField(read_only=True)
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True,
    )
    mark_up = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True,
    )
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True,
    )


class SupplierAccountTierPricingSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    tiers = SupplierAccountTierPricingItemSerializer(many=True)

    def validate_tiers(self, value):
        request = self.context.get('request')
        tenant_account_id = getattr(request.user, 'account_id', None) if request else None
        if tenant_account_id is None:
            raise serializers.ValidationError('No account context for tiers.')
        from suppliers.models import Tier

        valid_ids = set(
            Tier.objects.filter(
                account_id=tenant_account_id,
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


class SupplierTierSummarySerializer(serializers.Serializer):
    tier_id = serializers.IntegerField()
    tier_name = serializers.CharField()
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    mark_up = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )


class AccountSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    country_iso_code = serializers.CharField(source='country.iso_code', read_only=True)
    country_iso2_code = serializers.CharField(source='country.iso2_code', read_only=True)
    country_currency = serializers.CharField(source='country.currency', read_only=True)
    country_currency_symbol = serializers.CharField(
        source='country.currency_symbol',
        read_only=True,
    )
    country_currency_code = serializers.CharField(
        source='country.currency_code',
        read_only=True,
    )
    supplier_type_name = serializers.CharField(
        source='supplier_type.name',
        read_only=True,
    )
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    tier_id = serializers.IntegerField(required=False, allow_null=True)
    supplier_tiers = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            'id',
            'name',
            'status',
            'is_active',
            'country',
            'country_name',
            'country_iso_code',
            'country_iso2_code',
            'country_currency',
            'country_currency_symbol',
            'country_currency_code',
            'discount',
            'price_adjustment',
            'price',
            'tier_id',
            'supplier_tiers',
            'supplier_type',
            'supplier_type_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'country_name',
            'country_iso_code',
            'country_iso2_code',
            'country_currency',
            'country_currency_symbol',
            'country_currency_code',
            'supplier_type_name',
        ]

    def get_supplier_tiers(self, obj):
        by_supplier = self.context.get('tier_pricing_by_supplier')
        if not by_supplier:
            return []
        return by_supplier.get(obj.id, [])

    def create(self, validated_data):
        validated_data.pop('price', None)
        return super().create(validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        annotated_tier_id = getattr(instance, 'tier_id', None)
        if annotated_tier_id is not None:
            data['tier_id'] = annotated_tier_id
        elif data.get('tier_id') is None:
            data['tier_id'] = None
        return data

    def validate_tier_id(self, value):
        if value is None:
            return value
        request = self.context.get('request')
        tenant_account_id = getattr(request.user, 'account_id', None) if request else None
        if tenant_account_id is None:
            raise serializers.ValidationError('No account context for tier.')
        from suppliers.models import Tier

        if not Tier.objects.filter(
            pk=value,
            account_id=tenant_account_id,
            is_active=True,
            deleted_at__isnull=True,
        ).exists():
            raise serializers.ValidationError('Invalid or inactive tier.')
        return value

    def update(self, instance, validated_data):
        tier_id = validated_data.pop('tier_id', serializers.empty)
        price = validated_data.pop('price', serializers.empty)
        instance = super().update(instance, validated_data)
        request = self.context.get('request')
        tenant_account_id = getattr(request.user, 'account_id', None) if request else None
        if tenant_account_id and (
            tier_id is not serializers.empty or price is not serializers.empty
        ):
            set_supplier_tier_pricing(
                instance.id,
                tenant_account_id,
                tier_id=None if tier_id is serializers.empty else tier_id,
                price=parse_price_value(price) if price is not serializers.empty else None,
                price_unset=price is serializers.empty,
            )
        return instance


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Accepts the same JSON shape as the planningwithyou-react client:
    { "username": "<email>", "email": "<email>", "password": "..." }.
    Looks up the user by email (case-insensitive), then by username, so the
    login field can be either value.
    """

    default_error_messages = {
        'no_active_account': 'No active account found with the given credentials.',
    }

    def validate(self, attrs):
        email = attrs.get('email') or attrs.get('username')
        password = attrs.get('password')
        if not email or not password:
            raise serializers.ValidationError(
                {'detail': 'Must include email and password.'},
            )

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.filter(username__iexact=email).first()

        if user is None or not user.is_active or user.deleted_at is not None:
            raise serializers.ValidationError(
                {'detail': self.error_messages['no_active_account']},
            )
        if not user.check_password(password):
            raise serializers.ValidationError(
                {'detail': self.error_messages['no_active_account']},
            )

        refresh = self.get_token(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'account',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'is_admin',
            'last_login',
            'created_at',
            'updated_at',
            'deleted_at',
        ]
        read_only_fields = [
            'id',
            'account',
            'last_login',
            'created_at',
            'updated_at',
            'deleted_at',
        ]

    def validate_email(self, value):
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_username(self, value):
        qs = User.objects.filter(username__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return value

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            aid = request.user.account_id or 1
            instance.account_id = aid
            instance.save(update_fields=['account_id'])
        return instance


class UserCreateSerializer(UserSerializer):
    """Creates a user with an unusable password. A password-setup email is
    sent separately by the view after the user is saved."""

    def create(self, validated_data):
        request = self.context['request']
        validated_data['account_id'] = request.user.account_id or 1
        user = User(**validated_data)
        user.set_unusable_password()
        user.save()
        return user


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    password = serializers.CharField(min_length=8)

    def validate_token(self, value):
        from .models import PasswordResetToken

        try:
            reset = PasswordResetToken.objects.get(token=value)
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError('Invalid or expired token.')
        if not reset.is_valid:
            raise serializers.ValidationError('Invalid or expired token.')
        self.context['reset'] = reset
        return value

    def save(self):
        reset = self.context['reset']
        user = reset.user
        user.set_password(self.validated_data['password'])
        user.save()
        reset.used = True
        reset.save(update_fields=['used'])
