"""
Central definitions for template placeholder tokens and built-in default copy.

Tokens use curly braces, e.g. ``{name}``. Add new template defaults and names
here as you introduce more system emails.
"""

from __future__ import annotations

# --- User email template ``EmailTemplate.name`` values referenced in code ---
EMAIL_TEMPLATE_PASSWORD_RESET = 'password_reset'

# --- Password-invite / reset (no DB row or empty template fields) -------------
# Placeholders: {name}, {reset_url}, {lifetime}
DEFAULT_PASSWORD_RESET_SUBJECT = 'Set Your Password – Planning With You'

DEFAULT_PASSWORD_RESET_BODY_HTML = (
    '<h3>Hello {name},</h3>'
    '<p>An account has been created for you at Planning With You.</p>'
    '<p>Please click the link below to set your password:</p>'
    '<p><a href="{reset_url}">{reset_url}</a></p>'
    '<p>This link expires in {lifetime} hours.</p>'
    '<p>If you did not expect this email, you can safely ignore it.</p>'
)


def apply_template_placeholders(template: str, context: dict[str, str]) -> str:
    """Replace ``{key}`` for every string *key* in *context*."""
    out = template
    for key, value in context.items():
        out = out.replace('{' + key + '}', value)
    return out
