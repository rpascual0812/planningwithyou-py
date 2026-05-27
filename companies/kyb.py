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
    return (
        kyb is not None
        and kyb.status == CompanyKybVerification.Status.APPROVED
    )


def paymongo_business_type(business_type: str) -> str:
    """
    Map internal business type to PayMongo ``/v1/merchants/children`` business.type.

    Values match our KYB choices (e.g. ``sole_proprietor`` per PayMongo API).
    """
    valid = {choice.value for choice in CompanyKybVerification.BusinessType}
    if business_type in valid:
        return business_type
    return CompanyKybVerification.BusinessType.SOLE_PROPRIETOR
