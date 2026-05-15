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
    status = models.CharField(max_length=64, default='active')
    is_active = models.BooleanField(default=True)
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    price_adjustment = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    supplier_type = models.ForeignKey(
        'suppliers.SupplierType',
        on_delete=models.PROTECT,
        db_column='supplier_type_id',
        related_name='accounts',
    )
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
        extra_fields.setdefault('is_admin', True)
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
    username = models.CharField(max_length=150, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True, default='')
    last_name = models.CharField(max_length=150, blank=True, default='')
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
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
        return self.is_admin

    @property
    def is_superuser(self):
        return self.is_admin

    def has_module_perms(self, app_label):
        return self.is_admin

    def has_perm(self, perm, obj=None):
        return self.is_admin


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
