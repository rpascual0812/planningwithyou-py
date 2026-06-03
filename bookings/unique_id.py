from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import BookingUniqueIdSequence

MAX_SEQUENCE = 9999


def format_booking_unique_id(year: int, sequence: int) -> str:
    return f'{year % 100:02d}-{sequence:04d}'


def allocate_booking_unique_id(company_id: int, account_id: int, *, when=None) -> str:
    """Next booking reference for a company; sequence resets each calendar year."""
    when = when or timezone.now()
    year = when.year

    with transaction.atomic():
        seq, _created = BookingUniqueIdSequence.objects.select_for_update().get_or_create(
            company_id=company_id,
            year=year,
            defaults={'account_id': account_id, 'last_sequence': 0},
        )
        if seq.last_sequence >= MAX_SEQUENCE:
            raise ValidationError(
                {
                    'unique_id': [
                        f'Quotation ID limit reached for {year} ({MAX_SEQUENCE} per company).',
                    ],
                },
            )
        seq.last_sequence += 1
        seq.save(update_fields=['last_sequence'])
        return format_booking_unique_id(year, seq.last_sequence)
