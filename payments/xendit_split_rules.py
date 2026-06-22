"""Xendit xenPlatform split rules for quotation payment link platform fees."""

from __future__ import annotations

from django.conf import settings

from subscriptions.xendit_client import XenditError, _request, xendit_configured

SETTING_KEY = 'xendit_platform_fee_split_rule_id'


def platform_fee_percent() -> float:
    """Percent of net settlement routed to the master (platform) account."""
    raw = getattr(settings, 'XENDIT_PLATFORM_FEE_PERCENT', '1') or '1'
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 1.0
    return max(0.0, min(100.0, value))


def get_platform_fee_split_rule_id() -> str:
    """
    Return the xenPlatform split rule id for platform fee collection.

    Uses ``XENDIT_PLATFORM_SPLIT_RULE_ID`` when set; otherwise reuses a stored
    rule id or creates one via the Split Rules API (master account).
    """
    if not xendit_configured():
        return ''
    if platform_fee_percent() <= 0:
        return ''

    explicit = (getattr(settings, 'XENDIT_PLATFORM_SPLIT_RULE_ID', None) or '').strip()
    if explicit:
        return explicit

    from system_settings.models import SystemSetting

    row = SystemSetting.objects.filter(name=SETTING_KEY).first()
    if row and (row.value or '').strip():
        return row.value.strip()

    return _create_and_store_split_rule()


def _create_and_store_split_rule() -> str:
    percent = platform_fee_percent()
    payload = {
        'name': 'Planning With You platform fee',
        'description': (
            f'{percent:g}% of net settlement to platform master account '
            '(quotation payment links).'
        ),
        'routes': [
            {
                'percent_amount': percent,
                'currency': 'PHP',
                'reference_id': 'platform-fee',
            },
        ],
    }
    result = _request('POST', '/split_rules', payload)
    rule_id = str(result.get('id') or result.get('split_rule_id') or '').strip()
    if not rule_id:
        raise XenditError('Xendit did not return a split rule id.')

    from system_settings.models import SystemSetting

    SystemSetting.objects.update_or_create(
        name=SETTING_KEY,
        defaults={'value': rule_id},
    )
    return rule_id
