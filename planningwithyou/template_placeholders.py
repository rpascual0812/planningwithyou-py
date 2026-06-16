"""
Central definitions for template placeholder tokens and built-in default copy.

Tokens use curly braces, e.g. ``{name}``. Add new template defaults and names
here as you introduce more system emails.
"""

from __future__ import annotations

# --- User email template ``EmailTemplate.name`` values referenced in code ---
EMAIL_TEMPLATE_PASSWORD_RESET = 'password_reset'
EMAIL_TEMPLATE_VERIFY_EMAIL = 'verify_email'
EMAIL_TEMPLATE_PAYMENT_LINK = 'payment_link'
EMAIL_TEMPLATE_NEW_QUOTATION = 'new_quotation'
EMAIL_TEMPLATE_UPDATED_QUOTATION = 'updated_quotation'
EMAIL_TEMPLATE_QUOTATION_STATUS_COMPANY = 'quotation_status_company'
EMAIL_TEMPLATE_QUOTATION_STATUS_CONTACT = 'quotation_status_contact'

DEFAULT_QUOTATION_STATUS_CONTACT_SUBJECT = (
    '{company_name} – Quotation {quotation_unique_id} is now {status_title}'
)
DEFAULT_QUOTATION_STATUS_CONTACT_BODY_HTML = (
    '<p>Hi {first_name} {last_name},</p>'
    '<p>Your quotation <strong>{quotation_title}</strong> ({quotation_unique_id}) '
    'has been updated from <strong>{previous_status}</strong> to '
    '<strong>{status_title}</strong>.</p>'
    '<p>Thank you,<br>{company_name}</p>'
)

DEFAULT_NEW_QUOTATION_SUBJECT = '{company_name} - Quotation'
DEFAULT_NEW_QUOTATION_BODY_HTML = (
    '<p>Hi {first_name} {last_name},</p>'
    '<p>Please see the attached file/s</p>'
)

DEFAULT_UPDATED_QUOTATION_SUBJECT = '{company_name} - Updated Quotation'
DEFAULT_UPDATED_QUOTATION_BODY_HTML = (
    '<p>Hi {first_name} {last_name},</p>'
    '<p>Please see the attached file/s</p>'
)

DEFAULT_PAYMENT_LINK_SUBJECT = 'Payment for your booking'

DEFAULT_PAYMENT_LINK_BODY_HTML = (
    '<p>Hello,</p>'
    '<p>Please complete your payment using the link below:</p>'
    '<p><a href="{payment_link}">{payment_link}</a></p>'
    '<p>Thank you.</p>'
)

# --- Password-invite / reset (no DB row or empty template fields) -------------
# User: {name}, {first_name}, {last_name}, {email_address}, {mobile_number}
# Company: {company_name}, {company_contact_person}, {company_phone_number},
#          {company_mobile_number}, {company_address}
# Other: {reset_url}, {verify_url}, {lifetime}, {payment_link} (booking emails)
DEFAULT_VERIFY_EMAIL_SUBJECT = 'Verify your email – {company_name}'

DEFAULT_VERIFY_EMAIL_BODY_HTML = (
    '<h3>Hello {first_name},</h3>'
    '<p>Thank you for registering with Planning With You.</p>'
    '<p>Please click the link below to verify your email address and sign in:</p>'
    '<p><a href="{verify_url}">{verify_url}</a></p>'
    '<p>This link expires in {lifetime} hours.</p>'
    '<p>If you did not create this account, you can safely ignore this email.</p>'
)

DEFAULT_PASSWORD_RESET_SUBJECT = 'Set Your Password – Planning With You'

DEFAULT_PASSWORD_RESET_BODY_HTML = (
    '<h3>Hello {name},</h3>'
    '<p>An account has been created for you at Planning With You.</p>'
    '<p>Please click the link below to set your password:</p>'
    '<p><a href="{reset_url}">{reset_url}</a></p>'
    '<p>This link expires in {lifetime} hours.</p>'
    '<p>If you did not expect this email, you can safely ignore it.</p>'
)


def company_template_context(company) -> dict[str, str]:
    """Placeholder values from a ``companies.Company`` (or None)."""
    if company is None:
        return {
            'company_name': '',
            'company_contact_person': '',
            'company_phone_number': '',
            'company_mobile_number': '',
            'company_address': '',
        }
    return {
        'company_name': (company.name or '').strip(),
        'company_contact_person': (company.contact_person or '').strip(),
        'company_phone_number': (company.phone_number or '').strip(),
        'company_mobile_number': (company.mobile_number or '').strip(),
        'company_address': (company.address or '').strip(),
    }


def user_template_context(user) -> dict[str, str]:
    """Common user/recipient placeholders for email templates."""
    first = (getattr(user, 'first_name', None) or '').strip()
    last = (getattr(user, 'last_name', None) or '').strip()
    name = f'{first} {last}'.strip() or (getattr(user, 'username', None) or '').strip()
    return {
        'name': name,
        'first_name': first,
        'last_name': last,
        'email_address': (getattr(user, 'email', None) or '').strip(),
        'mobile_number': '',
    }


def apply_template_placeholders(template: str, context: dict[str, str]) -> str:
    """Replace ``{key}`` for every string *key* in *context*."""
    out = template
    for key, value in context.items():
        out = out.replace('{' + key + '}', value)
    return out
