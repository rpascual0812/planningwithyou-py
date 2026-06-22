"""PayMongo merchant onboarding (KYB) helpers."""

from __future__ import annotations

from .models import CompanyKybVerification


def missing_kyb_application_fields(kyb: CompanyKybVerification) -> list[str]:
    """Fields required before redirecting to PayMongo onboarding."""
    missing: list[str] = []
    if not kyb.business_type:
        missing.append('Business type')
        return missing
    if not (kyb.merchant_business_name or '').strip():
        missing.append('Business name')
    if not (kyb.merchant_email or '').strip():
        missing.append('Business email')
    if not (kyb.merchant_mobile_number or '').strip():
        missing.append('Mobile number')
    return missing


def live_payments_allowed(kyb: CompanyKybVerification | None) -> bool:
    if kyb is None:
        return False
    return (
        kyb.paymongo_status == CompanyKybVerification.PaymongoStatus.APPROVED
        or kyb.xendit_status == CompanyKybVerification.XenditStatus.APPROVED
    )


PAYMONGO_STATUS_LABELS = {
    CompanyKybVerification.PaymongoStatus.DRAFT: 'Draft',
    CompanyKybVerification.PaymongoStatus.PENDING_PAYMONGO: 'Pending PayMongo verification',
    CompanyKybVerification.PaymongoStatus.APPROVED: 'Verified',
    CompanyKybVerification.PaymongoStatus.REJECTED: 'Rejected',
}

XENDIT_STATUS_LABELS = {
    CompanyKybVerification.XenditStatus.DRAFT: 'Draft',
    CompanyKybVerification.XenditStatus.PENDING: 'Pending Xendit verification',
    CompanyKybVerification.XenditStatus.APPROVED: 'Verified',
    CompanyKybVerification.XenditStatus.REJECTED: 'Rejected',
}


def provider_verification_payload(kyb: CompanyKybVerification) -> dict:
    paymongo_verified = kyb.paymongo_status == CompanyKybVerification.PaymongoStatus.APPROVED
    xendit_verified = kyb.xendit_status == CompanyKybVerification.XenditStatus.APPROVED
    verified_providers: list[str] = []
    if paymongo_verified:
        verified_providers.append('paymongo')
    if xendit_verified:
        verified_providers.append('xendit')
    return {
        'paymongo': {
            'provider': 'paymongo',
            'provider_label': 'PayMongo',
            'status': kyb.paymongo_status,
            'status_label': PAYMONGO_STATUS_LABELS.get(
                kyb.paymongo_status,
                kyb.paymongo_status,
            ),
            'verified': paymongo_verified,
            'merchant_id': kyb.paymongo_merchant_id or '',
            'onboarding_url': kyb.onboarding_url or '',
            'rejection_notes': kyb.rejection_notes or '',
        },
        'xendit': {
            'provider': 'xendit',
            'provider_label': 'Xendit',
            'status': kyb.xendit_status,
            'status_label': XENDIT_STATUS_LABELS.get(kyb.xendit_status, kyb.xendit_status),
            'verified': xendit_verified,
            'account_id': kyb.xendit_account_id or '',
            'onboarding_url': '',
            'verification_flow': 'email_invitation',
            'invitation_email': (kyb.merchant_email or '').strip(),
            'rejection_notes': kyb.xendit_rejection_notes or '',
        },
        'verified_providers': verified_providers,
        'any_provider_verified': bool(verified_providers),
    }


def provider_verifications_for_company(company: Company) -> dict:
    kyb = getattr(company, 'kyb_verification', None)
    if kyb is None:
        return {
            'paymongo': {
                'provider': 'paymongo',
                'provider_label': 'PayMongo',
                'status': CompanyKybVerification.PaymongoStatus.DRAFT,
                'status_label': PAYMONGO_STATUS_LABELS[CompanyKybVerification.PaymongoStatus.DRAFT],
                'verified': False,
                'merchant_id': '',
                'onboarding_url': '',
                'rejection_notes': '',
            },
            'xendit': {
                'provider': 'xendit',
                'provider_label': 'Xendit',
                'status': CompanyKybVerification.XenditStatus.DRAFT,
                'status_label': XENDIT_STATUS_LABELS[CompanyKybVerification.XenditStatus.DRAFT],
                'verified': False,
                'account_id': '',
                'onboarding_url': '',
                'verification_flow': 'email_invitation',
                'invitation_email': '',
                'rejection_notes': '',
            },
            'verified_providers': [],
            'any_provider_verified': False,
        }
    return provider_verification_payload(kyb)


def paymongo_business_type(business_type: str) -> str:
    """
    Map internal business type to PayMongo ``/v1/merchants/children`` business.type.

    Values match our KYB choices (e.g. ``sole_proprietor`` per PayMongo API).
    """
    valid = {choice.value for choice in CompanyKybVerification.BusinessType}
    if business_type in valid:
        return business_type
    return CompanyKybVerification.BusinessType.SOLE_PROPRIETOR
