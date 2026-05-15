from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Account

User = get_user_model()


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
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        allow_null=True,
        required=False,
    )

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


class UserCreateSerializer(UserSerializer):
    """Creates a user with an unusable password. A password-setup email is
    sent separately by the view after the user is saved."""

    def create(self, validated_data):
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
