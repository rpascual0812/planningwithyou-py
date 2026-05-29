"""Helpers for RSVP widgets stored in invitation template JSON documents."""


def iter_document_elements(document):
    if not isinstance(document, dict):
        return
    for page in document.get('pages') or []:
        if not isinstance(page, dict):
            continue
        for element in page.get('elements') or []:
            if isinstance(element, dict):
                yield element


def find_rsvp_element(document, element_id: str) -> dict | None:
    for element in iter_document_elements(document):
        if element.get('type') == 'rsvp' and element.get('id') == element_id:
            return element
    return None


def collect_rsvp_elements(document) -> list[dict]:
    return [element for element in iter_document_elements(document) if element.get('type') == 'rsvp']


def rsvp_field_columns(document, submissions: list | None = None) -> list[dict]:
    """Ordered RSVP field columns from template config, with fallback to submission keys."""
    columns: list[dict] = []
    seen: set[str] = set()

    for element in collect_rsvp_elements(document):
        for field in normalize_rsvp_fields(element):
            field_id = str(field.get('id') or '').strip()
            if not field_id or field_id in seen:
                continue
            seen.add(field_id)
            columns.append({'id': field_id, 'label': str(field.get('label') or field_id)})

    if columns:
        return columns

    for submission in submissions or []:
        fields_data = submission.get('fields_data') if isinstance(submission, dict) else None
        if not isinstance(fields_data, dict):
            continue
        for field_id in fields_data:
            key = str(field_id).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            columns.append({'id': key, 'label': key.replace('_', ' ').title()})

    return columns


def get_public_invitation_template(slug: str):
    from .models import InvitationTemplate

    return (
        InvitationTemplate.objects.filter(
            slug=slug,
            is_published=True,
            is_deleted=False,
            is_marketplace=False,
        )
        .select_related('company')
        .first()
    )


def normalize_rsvp_fields(element: dict) -> list[dict]:
    fields = element.get('fields')
    if isinstance(fields, list) and fields:
        return [f for f in fields if isinstance(f, dict)]
    return [
        {
            'id': 'first_name',
            'label': 'First Name',
            'type': 'text',
            'required': True,
        },
        {
            'id': 'last_name',
            'label': 'Last Name',
            'type': 'text',
            'required': True,
        },
        {
            'id': 'mobile_number',
            'label': 'Mobile Number',
            'type': 'tel',
            'required': False,
        },
        {
            'id': 'email_address',
            'label': 'Email Address',
            'type': 'email',
            'required': True,
        },
    ]


def validate_rsvp_submission(element: dict, fields_payload: dict) -> dict:
    """Return cleaned field values or raise ValueError with message."""
    if not isinstance(fields_payload, dict):
        raise ValueError('fields must be an object.')

    config = normalize_rsvp_fields(element)
    cleaned: dict[str, str] = {}
    errors: dict[str, str] = {}

    for field in config:
        field_id = str(field.get('id') or '').strip()
        if not field_id:
            continue
        label = str(field.get('label') or field_id)
        required = bool(field.get('required'))
        raw = fields_payload.get(field_id)
        value = '' if raw is None else str(raw).strip()

        if required and not value:
            errors[field_id] = f'{label} is required.'
            continue

        if value:
            field_type = field.get('type') or 'text'
            if field_type == 'email' and '@' not in value:
                errors[field_id] = f'{label} must be a valid email address.'
                continue
            if field_type == 'select':
                options = field.get('options') or []
                if options and value not in options:
                    errors[field_id] = f'{label} has an invalid selection.'
                    continue

        cleaned[field_id] = value

    if errors:
        raise ValueError(errors)

    return cleaned
