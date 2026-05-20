"""Know Your Business (KYB) verification helpers."""

from __future__ import annotations

from .models import CompanyKybVerification


SOLE_PROPRIETOR_REQUIRED = (
    'government_id_file',
    'dti_registration_file',
    'sole_prop_business_address',
    'sole_prop_mobile_number',
    'bank_account_same_name',
)

CORPORATION_REQUIRED = (
    'sec_registration_file',
    'articles_of_incorporation_file',
    'bir_registration_file',
    'owner_director_id_files',
    'business_website_social',
    'company_email_domain',
)

ADDITIONAL_REQUIRED = (
    'proof_of_address_file',
    'business_description',
)


def kyb_field_values(kyb: CompanyKybVerification) -> dict[str, object]:
    return {
        'government_id_file': kyb.government_id_file,
        'dti_registration_file': kyb.dti_registration_file,
        'sole_prop_business_address': kyb.sole_prop_business_address,
        'sole_prop_mobile_number': kyb.sole_prop_mobile_number,
        'bank_account_same_name': kyb.bank_account_same_name,
        'sec_registration_file': kyb.sec_registration_file,
        'articles_of_incorporation_file': kyb.articles_of_incorporation_file,
        'bir_registration_file': kyb.bir_registration_file,
        'owner_director_id_files': kyb.owner_director_id_files,
        'business_website_social': kyb.business_website_social,
        'company_email_domain': kyb.company_email_domain,
        'proof_of_address_file': kyb.proof_of_address_file,
        'business_description': kyb.business_description,
    }


def _is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        return len(value) > 0
    return bool(str(value).strip())


def missing_kyb_fields(kyb: CompanyKybVerification) -> list[str]:
    """Return human-readable missing field names for submission."""
    values = kyb_field_values(kyb)
    missing: list[str] = []
    if not kyb.business_type:
        missing.append('business_type')
        return missing

    if kyb.business_type == CompanyKybVerification.BusinessType.SOLE_PROPRIETOR:
        required = SOLE_PROPRIETOR_REQUIRED + ADDITIONAL_REQUIRED
    else:
        required = CORPORATION_REQUIRED + ADDITIONAL_REQUIRED

    labels = {
        'government_id_file': 'Valid government ID',
        'dti_registration_file': 'DTI registration',
        'sole_prop_business_address': 'Business address',
        'sole_prop_mobile_number': 'Mobile number',
        'bank_account_same_name': 'Bank account under same name',
        'sec_registration_file': 'SEC registration',
        'articles_of_incorporation_file': 'Articles of Incorporation',
        'bir_registration_file': 'BIR registration',
        'owner_director_id_files': 'Valid IDs of owners/directors',
        'business_website_social': 'Business website/social pages',
        'company_email_domain': 'Company email domain',
        'proof_of_address_file': 'Proof of address',
        'business_description': 'Business description',
    }
    for key in required:
        if not _is_filled(values.get(key)):
            missing.append(labels.get(key, key))
    return missing


def live_payments_allowed(kyb: CompanyKybVerification | None) -> bool:
    return (
        kyb is not None
        and kyb.status == CompanyKybVerification.Status.APPROVED
    )
