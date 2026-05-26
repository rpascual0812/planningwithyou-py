from django.db import transaction
from django.db.models import Count
from rest_framework import serializers

from .models import Role, RolePermission
from .roles import (
    ADMIN_FEATURE_KEYS,
    FEATURE_KEYS,
    TENANT_FEATURE_KEYS,
    assignable_feature_keys,
    feature_catalog_keys_for_user,
    has_platform_admin_read,
)


FEATURE_LABELS = {
    'dashboard': 'Dashboard',
    'calendar': 'Calendar',
    'bookings': 'Bookings',
    'contacts': 'Contacts',
    'users': 'Users',
    'emails': 'Emails',
    'file_manager': 'File Manager',
    'reports': 'Reports',
    'settings': 'Settings > Integrations',
    'account_settings': 'Settings > Account Settings',
    'companies_settings': 'Settings > Company Settings',
    'supplier_settings': 'Settings > Supplier Settings',
    'booking_settings_statuses': 'Settings > Booking Settings',
    'email_templates': 'Settings > Email Templates',
    'roles_permissions': 'Settings > Roles and Permissions',
    'calendar_settings': 'Settings > Calendar Settings',
    'change_company': 'Change Company',
    'platform_admin': 'Admin',
    'admin_company_verification': 'Admin > Company Verification',
    'admin_emails': 'Admin > Emails',
    'admin_payouts': 'Admin > Payouts',
    'admin_system_notifications': 'Admin > System Notifications',
    'admin_support': 'Admin > Support',
}


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Role
        fields = [
            'id',
            'name',
            'is_default',
            'permissions',
            'user_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_permissions(self, obj: Role) -> dict[str, str]:
        rows = obj.permissions.all()
        perms = {p.feature_key: p.access for p in rows}
        for key in TENANT_FEATURE_KEYS:
            perms.setdefault(key, 'none')
        return perms


class RoleWriteSerializer(serializers.ModelSerializer):
    """Write payload uses ``permissions``; avoid the model's ``permissions`` relation on output."""

    permissions = serializers.DictField(
        child=serializers.ChoiceField(choices=['none', 'read', 'write']),
        write_only=True,
    )

    class Meta:
        model = Role
        fields = ['id', 'name', 'is_default', 'permissions']
        read_only_fields = ['id']

    def to_representation(self, instance):
        return RoleSerializer(instance, context=self.context).data

    def validate_name(self, value: str) -> str:
        name = value.strip()
        if not name:
            raise serializers.ValidationError('Name is required.')
        qs = Role.objects.filter(
            account_id=self._account_id(),
            name__iexact=name,
        )
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A role with this name already exists.')
        return name

    def validate_permissions(self, value: dict) -> dict:
        request = self.context.get('request')
        allowed = set(assignable_feature_keys())
        if request is not None and not has_platform_admin_read(request.user):
            allowed -= set(ADMIN_FEATURE_KEYS)
        unknown = set(value.keys()) - allowed
        if unknown:
            raise serializers.ValidationError(
                f'Unknown feature keys: {", ".join(sorted(unknown))}',
            )
        return value

    def _normalized_permissions(self, value: dict) -> dict[str, str]:
        request = self.context.get('request')
        keys = assignable_feature_keys()
        if request is not None and not has_platform_admin_read(request.user):
            keys = TENANT_FEATURE_KEYS
        return {key: value.get(key, 'none') for key in keys}

    def _sync_permissions(self, role: Role, perms: dict[str, str]) -> None:
        for key, access in perms.items():
            RolePermission.objects.update_or_create(
                role=role,
                feature_key=key,
                defaults={'access': access},
            )

    def _account_id(self) -> int:
        request = self.context['request']
        return request.user.account_id

    @transaction.atomic
    def create(self, validated_data):
        perms = self._normalized_permissions(validated_data.pop('permissions'))
        is_default = validated_data.pop('is_default', False)
        account_id = self._account_id()
        if is_default:
            Role.objects.filter(account_id=account_id, is_default=True).update(
                is_default=False,
            )
        role = Role.objects.create(account_id=account_id, **validated_data)
        if is_default:
            role.is_default = True
            role.save(update_fields=['is_default'])
        self._sync_permissions(role, perms)
        return role

    @transaction.atomic
    def update(self, instance, validated_data):
        perms = None
        if instance.name == 'Owner':
            validated_data.pop('name', None)
            validated_data.pop('is_default', None)
            if 'permissions' in validated_data:
                validated_data.pop('permissions')
            perms = {key: 'write' for key in FEATURE_KEYS}
        else:
            perms_data = validated_data.pop('permissions', None)
            if perms_data is not None:
                perms = self._normalized_permissions(perms_data)
        is_default = validated_data.pop('is_default', None)
        account_id = instance.account_id
        if is_default is True:
            Role.objects.filter(account_id=account_id, is_default=True).exclude(
                pk=instance.pk,
            ).update(is_default=False)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if is_default is not None:
            instance.is_default = is_default
        instance.save()
        if perms is not None:
            self._sync_permissions(instance, perms)
        return instance


def roles_queryset_for_account(account_id: int):
    return (
        Role.objects.filter(account_id=account_id)
        .prefetch_related('permissions')
        .annotate(user_count=Count('users'))
        .order_by('name')
    )
