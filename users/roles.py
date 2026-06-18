"""Role helpers for tenant RBAC."""

from __future__ import annotations

from users.models import Account, Role, RolePermission

TENANT_FEATURE_KEYS = (
    'dashboard',
    'calendar',
    'quotations',
    'contacts',
    'users',
    'emails',
    'file_manager',
    'template_studio',
    'reports',
    'settings',
    'account_settings',
    'companies_settings',
    'supplier_settings',
    'quotation_settings_statuses',
    'email_templates',
    'roles_permissions',
    'calendar_settings',
    'change_company',
    'ai_assistant',
)

# Cross-tenant staff tools (shown in role editor only to users with Admin read).
ADMIN_FEATURE_KEYS = (
    'platform_admin',
    'admin_accounts',
    'admin_company_verification',
    'admin_emails',
    'admin_payouts',
    'admin_system_notifications',
    'admin_support',
    'admin_error_logs',
    'admin_legal',
)

PLATFORM_FEATURE_KEYS = ADMIN_FEATURE_KEYS

FEATURE_KEYS = TENANT_FEATURE_KEYS + ADMIN_FEATURE_KEYS

PLATFORM_ADMIN_KEY = 'platform_admin'

# Safe (GET/HEAD/OPTIONS) requests on these features may also be allowed when the
# user has read or write on any of the listed grant keys (first match wins).
GET_READ_GRANTS: dict[str, tuple[str, ...]] = {
    'quotation_settings_statuses': ('quotations',),
    'email_templates': ('emails',),
    'calendar_settings': ('calendar',),
    'companies_settings': ('change_company',),
}


def ensure_owner_role(account: Account) -> Role:
    """Ensure the account has an Owner role with write on all features."""
    role, _created = Role.objects.get_or_create(
        account=account,
        name='Owner',
        defaults={'is_default': True},
    )
    if not role.is_default:
        role.is_default = True
        role.save(update_fields=['is_default'])

    for key in TENANT_FEATURE_KEYS:
        RolePermission.objects.update_or_create(
            role=role,
            feature_key=key,
            defaults={'access': 'write'},
        )
    return role


def default_role_for_account(account_id: int) -> Role | None:
    """Return the account's default role, falling back to Owner."""
    return (
        Role.objects.filter(account_id=account_id, is_default=True).first()
        or Role.objects.filter(account_id=account_id, name='Owner').first()
    )


def effective_feature_permissions(user) -> dict[str, str]:
    """
    Map feature_key -> access level for a user.

    Users without a role receive ``none`` on every feature. Missing role rows
    default to ``none``.
    """
    role_id = getattr(user, 'role_id', None)
    if not role_id:
        return {key: 'none' for key in FEATURE_KEYS}

    perms: dict[str, str] = {}
    role = getattr(user, 'role', None)
    if role is not None:
        rows = role.permissions.all()
        perms = {p.feature_key: p.access for p in rows}
    else:
        perms = {
            p.feature_key: p.access
            for p in RolePermission.objects.filter(role_id=role_id)
        }

    return {key: perms.get(key, 'none') for key in FEATURE_KEYS}


def feature_access_level(user, feature_key: str) -> str:
    return effective_feature_permissions(user).get(feature_key, 'none')


def feature_access_level_for_request(
    user,
    feature_key: str,
    *,
    safe_method: bool,
) -> str:
    """
    Effective access for a feature, optionally honoring GET read grants.

    Unsafe methods only use the declared feature (write required).
    Safe methods also accept read/write on keys listed in ``GET_READ_GRANTS``.
    """
    access = effective_feature_permissions(user)
    level = access.get(feature_key, 'none')
    if not safe_method:
        return level if level == 'write' else 'none'
    if level in ('read', 'write'):
        return level
    for grant_key in GET_READ_GRANTS.get(feature_key, ()):
        grant_level = access.get(grant_key, 'none')
        if grant_level in ('read', 'write'):
            return grant_level
    return 'none'


def has_feature_write(user, feature_key: str) -> bool:
    return feature_access_level(user, feature_key) == 'write'


def has_feature_read(user, feature_key: str) -> bool:
    return feature_access_level(user, feature_key) in ('read', 'write')


def has_platform_admin_read(user) -> bool:
    """Can access the Admin area and see admin features in the role editor."""
    return has_feature_read(user, PLATFORM_ADMIN_KEY)


def is_platform_admin(user) -> bool:
    """Cross-tenant staff with full admin write (legacy helper)."""
    return has_feature_write(user, PLATFORM_ADMIN_KEY)


def feature_catalog_keys_for_user(user) -> tuple[str, ...]:
    """Tenant features plus admin features when the editor has Admin read."""
    if has_platform_admin_read(user):
        return TENANT_FEATURE_KEYS + ADMIN_FEATURE_KEYS
    return TENANT_FEATURE_KEYS


def assignable_feature_keys() -> tuple[str, ...]:
    """All feature keys that may be stored on a role."""
    return FEATURE_KEYS
