import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone


class AccountQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class AccountManager(models.Manager.from_queryset(AccountQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AccountAllManager(models.Manager.from_queryset(AccountQuerySet)):
    pass


class Account(models.Model):
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    contact_person = models.CharField(max_length=255, blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')
    contact_mobile_number = models.CharField(max_length=32, blank=True, default='')
    timezone = models.CharField(max_length=63, blank=True, default='')
    country = models.ForeignKey(
        'countries.Country',
        on_delete=models.PROTECT,
        db_column='country_id',
        related_name='accounts',
    )
    paymongo_customer_id = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = AccountManager()
    all_objects = AccountAllManager()

    class Meta:
        db_table = 'accounts'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError('The username must be set.')
        if not email:
            raise ValueError('The email must be set.')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_active', True)
        return self.create_user(username, email, password, **extra_fields)


class UserAllManager(BaseUserManager):
    """Unfiltered manager (e.g. admin or rare maintenance)."""

    pass


class User(AbstractBaseUser):
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='users',
        db_column='account_id',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,
        related_name='users',
        db_column='company_id',
    )
    username = models.CharField(max_length=150, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True, default='')
    last_name = models.CharField(max_length=150, blank=True, default='')
    photo = models.CharField(
        max_length=512,
        blank=True,
        default='',
        help_text='Secured API URL for the user profile photo download route.',
    )
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    token_version = models.PositiveIntegerField(
        default=0,
        help_text='Incremented on each login to invalidate JWTs from previous sessions.',
    )
    role = models.ForeignKey(
        'users.Role',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users',
        db_column='role_id',
    )
    tour_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the user finished or skipped the in-app product tour.',
    )
    account_restricted = models.BooleanField(
        default=False,
        help_text='When true, the user is read-only in the Users list (no edit/delete).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()
    all_objects = UserAllManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        db_table = 'users'
        ordering = ['username']

    def __str__(self):
        return self.username

    @property
    def is_staff(self):
        from users.roles import is_platform_admin

        return is_platform_admin(self)

    @property
    def is_superuser(self):
        return self.is_staff

    def has_module_perms(self, app_label):
        return self.is_staff

    def has_perm(self, perm, obj=None):
        return self.is_staff


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_verification_tokens',
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        db_table = 'email_verification_tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} – {self.token}'

    @property
    def is_expired(self):
        lifetime = getattr(settings, 'EMAIL_VERIFICATION_TOKEN_LIFETIME_HOURS', 72)
        return timezone.now() > self.created_at + timedelta(hours=lifetime)

    @property
    def is_valid(self):
        return not self.used and not self.is_expired


class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_reset_tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} – {self.token}'

    @property
    def is_expired(self):
        lifetime = getattr(settings, 'PASSWORD_RESET_TOKEN_LIFETIME_HOURS', 24)
        return timezone.now() > self.created_at + timedelta(hours=lifetime)

    @property
    def is_valid(self):
        return not self.used and not self.is_expired


class Role(models.Model):
    """Per-account role that groups feature permissions."""

    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='roles',
        db_column='account_id',
    )
    name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'roles'
        unique_together = (('account', 'name'),)
        ordering = ['account_id', 'name']

    def __str__(self):
        return f'{self.account_id}:{self.name}'


class RolePermission(models.Model):
    class AccessLevel(models.TextChoices):
        NONE = 'none', 'None'
        READ = 'read', 'Read'
        WRITE = 'write', 'Write'

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='permissions',
        db_column='role_id',
    )
    feature_key = models.CharField(max_length=100)
    access = models.CharField(
        max_length=10,
        choices=AccessLevel.choices,
        default=AccessLevel.NONE,
    )

    class Meta:
        db_table = 'role_permissions'
        unique_together = (('role', 'feature_key'),)
        ordering = ['role_id', 'feature_key']

    def __str__(self):
        return f'{self.role_id}:{self.feature_key}={self.access}'
