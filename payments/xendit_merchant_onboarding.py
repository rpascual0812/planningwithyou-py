"""Create Xendit xenPlatform sub-accounts from company KYB applications."""

from __future__ import annotations

from django.utils import timezone

from companies.kyb import missing_kyb_application_fields
from companies.models import Company, CompanyKybVerification

from .xendit_config import xendit_platform_configured
from .xendit_platform_client import (
    XenditPlatformError,
    create_managed_sub_account,
    get_sub_account,
)


class XenditOnboardingError(Exception):
    pass


def _xendit_onboarding_error(exc: XenditPlatformError) -> XenditOnboardingError:
    return XenditOnboardingError(str(exc))


def _is_legacy_onboarding_url(url: str) -> bool:
    """Detect PayMongo-style URLs we incorrectly stored for Xendit."""
    normalized = (url or '').strip().lower()
    return 'onboarding.xendit.com' in normalized


def _clear_legacy_onboarding_url(kyb: CompanyKybVerification) -> bool:
    if not _is_legacy_onboarding_url(kyb.xendit_onboarding_url or ''):
        return False
    kyb.xendit_onboarding_url = ''
    kyb.save(update_fields=['xendit_onboarding_url', 'updated_at'])
    return True


def _map_xendit_account_status(raw_status: str) -> str:
    status = (raw_status or '').strip().upper()
    if status == 'LIVE':
        return CompanyKybVerification.XenditStatus.APPROVED
    if status == 'SUSPENDED':
        return CompanyKybVerification.XenditStatus.REJECTED
    if status in {'INVITED', 'REGISTERED', 'AWAITING_DOCS', 'PENDING_VERIFICATION'}:
        return CompanyKybVerification.XenditStatus.PENDING
    return CompanyKybVerification.XenditStatus.PENDING


def _reset_legacy_owned_account(kyb: CompanyKybVerification) -> CompanyKybVerification:
    """Drop OWNED sub-accounts created by the old hosted-URL flow."""
    account_id = (kyb.xendit_account_id or '').strip()
    if not account_id:
        return kyb
    try:
        account = get_sub_account(account_id)
    except XenditPlatformError:
        return kyb
    if str(account.get('type') or '').upper() != 'OWNED':
        return kyb
    if _map_xendit_account_status(str(account.get('status') or '')) == (
        CompanyKybVerification.XenditStatus.APPROVED
    ):
        return kyb
    kyb.xendit_account_id = ''
    kyb.xendit_status = CompanyKybVerification.XenditStatus.DRAFT
    kyb.save(update_fields=['xendit_account_id', 'xendit_status', 'updated_at'])
    return kyb


def refresh_xendit_kyb_status(kyb: CompanyKybVerification) -> CompanyKybVerification:
    """Sync local Xendit KYB status from the xenPlatform account API."""
    _clear_legacy_onboarding_url(kyb)

    account_id = (kyb.xendit_account_id or '').strip()
    if not account_id or not xendit_platform_configured():
        return kyb
    if kyb.xendit_status in (
        CompanyKybVerification.XenditStatus.APPROVED,
        CompanyKybVerification.XenditStatus.REJECTED,
    ):
        return kyb
    try:
        account = get_sub_account(account_id)
    except XenditPlatformError:
        return kyb
    mapped = _map_xendit_account_status(str(account.get('status') or ''))
    if mapped == kyb.xendit_status:
        return kyb
    kyb.xendit_status = mapped
    if mapped == CompanyKybVerification.XenditStatus.APPROVED:
        kyb.xendit_rejection_notes = ''
    kyb.save(update_fields=['xendit_status', 'xendit_rejection_notes', 'updated_at'])
    return kyb


def start_xendit_merchant_onboarding(
    company: Company,
    *,
    regenerate_link: bool = False,
) -> CompanyKybVerification:
    """
    Create (or reuse) a xenPlatform MANAGED sub-account.

    Xendit does not provide a hosted onboarding URL like PayMongo. For MANAGED
    accounts, Xendit emails an invitation link to ``merchant_email``.
    """
    del regenerate_link

    if not xendit_platform_configured():
        raise XenditOnboardingError('Xendit is not configured on the server.')

    kyb, _ = CompanyKybVerification.objects.get_or_create(company=company)
    had_legacy_url = _is_legacy_onboarding_url(kyb.xendit_onboarding_url or '')
    _clear_legacy_onboarding_url(kyb)
    if had_legacy_url:
        kyb = _reset_legacy_owned_account(kyb)

    missing = missing_kyb_application_fields(kyb)
    if missing:
        raise XenditOnboardingError(
            f'Missing required fields: {", ".join(missing)}.',
        )

    business_name = (kyb.merchant_business_name or company.name).strip()
    email = kyb.merchant_email.strip()

    account_id = (kyb.xendit_account_id or '').strip()
    if not account_id:
        try:
            account = create_managed_sub_account(
                email=email,
                business_name=business_name,
            )
        except XenditPlatformError as exc:
            raise _xendit_onboarding_error(exc) from exc
        account_id = str(account.get('id') or '').strip()
        if not account_id:
            raise XenditOnboardingError('Xendit did not return a sub-account id.')
        kyb.xendit_account_id = account_id
        kyb.xendit_status = _map_xendit_account_status(str(account.get('status') or ''))
    else:
        kyb = refresh_xendit_kyb_status(kyb)
        if kyb.xendit_status == CompanyKybVerification.XenditStatus.APPROVED:
            return kyb
        kyb.xendit_status = CompanyKybVerification.XenditStatus.PENDING

    kyb.xendit_onboarding_url = ''
    if not kyb.xendit_submitted_at:
        kyb.xendit_submitted_at = timezone.now()
    kyb.save(
        update_fields=[
            'xendit_account_id',
            'xendit_status',
            'xendit_onboarding_url',
            'xendit_submitted_at',
            'updated_at',
        ],
    )
    kyb.refresh_from_db()
    return kyb
