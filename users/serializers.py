from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from subscriptions.account_plan import (
    active_subscription_plan_for_account,
    current_subscription_plan_for_account,
)

from companies.models import Company
from companies.scope import company_belongs_to_account
from planningwithyou.file_storage import company_logo_public_url, user_photo_public_url

from .jwt import issue_tokens_for_user
from .user_photo import delete_user_photo, save_user_photo

from .models import Account, Role

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
                {'detail': 'Must include username or email and password.'},
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

        return issue_tokens_for_user(user)


class UserSerializer(serializers.ModelSerializer):
    subscription_plan = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    company_timezone = serializers.SerializerMethodField()
    company_logo_url = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    role_name = serializers.CharField(source='role.name', read_only=True, default='')
    photo_upload = serializers.FileField(write_only=True, required=False, allow_null=True)
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.none(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            'id',
            'account',
            'company',
            'company_name',
            'company_timezone',
            'company_logo_url',
            'photo',
            'photo_url',
            'photo_upload',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'role',
            'role_name',
            'permissions',
            'subscription_plan',
            'tour_completed_at',
            'last_login',
            'created_at',
            'updated_at',
            'deleted_at',
        ]
        read_only_fields = [
            'id',
            'account',
            'company',
            'company_name',
            'company_timezone',
            'company_logo_url',
            'photo',
            'photo_url',
            'subscription_plan',
            'tour_completed_at',
            'last_login',
            'created_at',
            'updated_at',
            'deleted_at',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            self.fields['role'].queryset = Role.objects.filter(
                account_id=request.user.account_id,
            )

    def validate_role(self, role):
        if role is None:
            return role
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError('Authentication required.')
        if role.account_id != request.user.account_id:
            raise serializers.ValidationError('Invalid role for this account.')
        return role

    def get_subscription_plan(self, obj: User) -> str:
        return current_subscription_plan_for_account(obj.account_id)

    def get_company_name(self, obj: User) -> str:
        company = getattr(obj, 'company', None)
        if company is None:
            return ''
        return company.name

    def get_company_timezone(self, obj: User) -> str:
        from companies.timezone import normalize_company_timezone_name

        company = getattr(obj, 'company', None)
        if company is None:
            return 'UTC'
        return normalize_company_timezone_name(company.timezone)

    def get_company_logo_url(self, obj: User) -> str:
        company = getattr(obj, 'company', None)
        if company is None:
            return ''
        return company_logo_public_url(
            company.logo,
            company.pk,
            request=self.context.get('request'),
        )

    def get_permissions(self, obj: User) -> dict[str, str]:
        from .roles import effective_feature_permissions

        return effective_feature_permissions(obj)

    def get_photo_url(self, obj: User) -> str:
        return user_photo_public_url(
            obj.photo,
            obj.pk,
            request=self.context.get('request'),
        )

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            payload = data.copy()
        else:
            payload = dict(data)
        photo_val = payload.get('photo')
        if photo_val is not None and hasattr(photo_val, 'read'):
            payload['photo_upload'] = photo_val
            del payload['photo']
        return super().to_internal_value(payload)

    def _apply_photo_upload(self, instance, photo_upload) -> None:
        if photo_upload is serializers.empty:
            return
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            raise serializers.ValidationError(
                {'photo_upload': 'Authentication required.'},
            )
        if instance.pk != request.user.pk:
            raise serializers.ValidationError(
                {'photo_upload': 'You can only change your own profile photo.'},
            )
        try:
            if photo_upload:
                instance.photo = save_user_photo(
                    instance.account_id,
                    instance.pk,
                    photo_upload,
                    old_photo=instance.photo or '',
                    request=request,
                )
            else:
                delete_user_photo(
                    instance.photo,
                    account_id=instance.account_id,
                    user_id=instance.pk,
                )
                instance.photo = ''
        except ValueError as exc:
            raise serializers.ValidationError({'photo_upload': str(exc)}) from exc
        instance.save(update_fields=['photo', 'updated_at'])

    def _target_company_id(self) -> int | None:
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return None
        if self.instance is not None:
            return self.instance.company_id
        initial = getattr(self, 'initial_data', None) or {}
        raw = initial.get('company')
        if raw is not None and raw != '':
            try:
                company_id = int(raw)
            except (TypeError, ValueError):
                return request.user.company_id
            if company_belongs_to_account(company_id, request.user.account_id):
                from .company_access import can_change_company

                if can_change_company(request.user) or company_id == request.user.company_id:
                    return company_id
        return request.user.company_id

    def _users_in_company(self):
        company_id = self._target_company_id()
        if company_id is None:
            return User.objects.none()
        return User.objects.filter(company_id=company_id)

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
        photo_upload = validated_data.pop('photo_upload', serializers.empty)
        instance = super().update(instance, validated_data)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from .roles import has_feature_write

            instance.account_id = request.user.account_id or 1
            if not has_feature_write(request.user, 'users'):
                instance.company_id = request.user.company_id
            instance.save(update_fields=['account_id', 'company_id'])
        self._apply_photo_upload(instance, photo_upload)
        return instance


class UserCreateSerializer(UserSerializer):
    """Creates a user with an unusable password. A password-setup email is
    sent separately by the view after the user is saved."""

    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.none(),
        required=False,
        allow_null=True,
    )

    class Meta(UserSerializer.Meta):
        read_only_fields = [
            f
            for f in UserSerializer.Meta.read_only_fields
            if f != 'company'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            self.fields['company'].queryset = Company.objects.filter(
                account_id=request.user.account_id,
                deleted_at__isnull=True,
            )

    def validate_company(self, company):
        request = self.context['request']
        if company is None:
            return company
        if not company_belongs_to_account(company.pk, request.user.account_id):
            raise serializers.ValidationError('Invalid company for this account.')
        from .company_access import can_change_company

        if not can_change_company(request.user) and company.pk != request.user.company_id:
            raise serializers.ValidationError(
                'You may only add users to your own company.',
            )
        return company

    def create(self, validated_data):
        request = self.context['request']
        company = validated_data.pop('company', None)
        validated_data['account_id'] = request.user.account_id or 1
        validated_data['company_id'] = (
            company.pk if company is not None else request.user.company_id
        )
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


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=8, write_only=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate(self, attrs):
        if attrs['current_password'] == attrs['new_password']:
            raise serializers.ValidationError(
                {'new_password': 'New password must be different from your current password.'},
            )
        return attrs

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password', 'updated_at'])
        return user
