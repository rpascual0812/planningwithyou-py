from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from subscriptions.account_plan import active_subscription_plan_for_account

from companies.models import Company

from .models import Account

User = get_user_model()


def user_may_login(user) -> bool:
    """True when the user and linked account/company are active and not soft-deleted."""
    if user is None or not user.is_active or user.deleted_at is not None:
        return False
    account = getattr(user, 'account', None)
    if account is None or not account.is_active or account.deleted_at is not None:
        return False
    company = (
        Company.all_objects.filter(pk=user.company_id).first()
        if user.company_id
        else None
    )
    if company is None or not company.is_active or company.deleted_at is not None:
        return False
    if not getattr(user, 'is_verified', False):
        return False
    return True


class AccountSerializer(serializers.ModelSerializer):
    subscription_plan = serializers.SerializerMethodField()
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
    class Meta:
        model = Account
        fields = [
            'id',
            'name',
            'is_active',
            'contact_person',
            'contact_email',
            'contact_mobile_number',
            'timezone',
            'country',
            'country_name',
            'country_iso_code',
            'country_iso2_code',
            'country_currency',
            'country_currency_symbol',
            'country_currency_code',
            'subscription_plan',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'subscription_plan',
            'created_at',
            'updated_at',
            'country_name',
            'country_iso_code',
            'country_iso2_code',
            'country_currency',
            'country_currency_symbol',
            'country_currency_code',
        ]

    def get_subscription_plan(self, obj: Account) -> str:
        return active_subscription_plan_for_account(obj.pk)


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

        user = (
            User.objects.filter(email__iexact=email)
            .select_related('account')
            .first()
        )
        if user is None:
            user = (
                User.objects.filter(username__iexact=email)
                .select_related('account')
                .first()
            )

        if user is None or not user.is_active or user.deleted_at is not None:
            raise serializers.ValidationError(
                {'detail': self.error_messages['no_active_account']},
            )
        if not user.check_password(password):
            raise serializers.ValidationError(
                {'detail': self.error_messages['no_active_account']},
            )
        account = getattr(user, 'account', None)
        if account is None or not account.is_active or account.deleted_at is not None:
            raise serializers.ValidationError(
                {'detail': self.error_messages['no_active_account']},
            )
        company = (
            Company.all_objects.filter(pk=user.company_id).first()
            if user.company_id
            else None
        )
        if company is None or not company.is_active or company.deleted_at is not None:
            raise serializers.ValidationError(
                {'detail': self.error_messages['no_active_account']},
            )
        if not user.is_verified:
            raise serializers.ValidationError(
                {
                    'detail': (
                        'Please verify your email address before logging in. '
                        'Check your inbox for the verification link.'
                    ),
                },
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
            'company',
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
            'company',
            'last_login',
            'created_at',
            'updated_at',
            'deleted_at',
        ]

    def _users_in_company(self):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return User.objects.all()
        return User.objects.filter(company_id=request.user.company_id)

    def validate_email(self, value):
        qs = self._users_in_company().filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_username(self, value):
        qs = self._users_in_company().filter(username__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return value

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            instance.account_id = request.user.account_id or 1
            instance.company_id = request.user.company_id
            instance.save(update_fields=['account_id', 'company_id'])
        return instance


class UserCreateSerializer(UserSerializer):
    """Creates a user with an unusable password. A password-setup email is
    sent separately by the view after the user is saved."""

    def create(self, validated_data):
        request = self.context['request']
        validated_data['account_id'] = request.user.account_id or 1
        validated_data.setdefault('company_id', request.user.company_id)
        validated_data['is_verified'] = True
        user = User(**validated_data)
        user.set_unusable_password()
        user.save()
        return user


class EmailVerifySerializer(serializers.Serializer):
    token = serializers.UUIDField()

    def validate_token(self, value):
        from .models import EmailVerificationToken

        try:
            verification = EmailVerificationToken.objects.select_related(
                'user',
                'user__account',
            ).get(token=value)
        except EmailVerificationToken.DoesNotExist:
            raise serializers.ValidationError('Invalid or expired verification link.')
        if not verification.is_valid:
            raise serializers.ValidationError('Invalid or expired verification link.')
        self.context['verification'] = verification
        return value

    def save(self):
        verification = self.context['verification']
        user = verification.user
        if not user.is_verified:
            user.is_verified = True
            user.save(update_fields=['is_verified', 'updated_at'])
        verification.used = True
        verification.save(update_fields=['used'])
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
