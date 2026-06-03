#!/usr/bin/env python3
"""One-off codemod: Booking* → Quotation*, API paths, feature keys."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'migrations', 'venv', '.git', '__pycache__', 'node_modules', 'scripts'}

CLASS_RENAMES = [
    ('BookingPaymentReceipt', 'QuotationPaymentReceipt'),
    ('BookingPaymentLink', 'QuotationPaymentLink'),
    ('BookingUniqueIdSequence', 'QuotationUniqueIdSequence'),
    ('BookingStatus', 'QuotationStatus'),
    ('BookingPayment', 'QuotationPayment'),
    ('BookingGroup', 'QuotationGroup'),
    ('BookingItem', 'Quotation'),
    ('BookingLine', 'QuotationLine'),
    ('SupplierBookingCapacityQuerySerializer', 'SupplierQuotationCapacityQuerySerializer'),
    ('SupplierBookingCapacityView', 'SupplierQuotationCapacityView'),
    ('SupplierBookingCapacityTests', 'SupplierQuotationCapacityTests'),
]

STRING_RENAMES = [
    ("'bookings.BookingItem'", "'bookings.Quotation'"),
    ('"bookings.BookingItem"', '"bookings.Quotation"'),
    ("'bookings.BookingStatus'", "'bookings.QuotationStatus'"),
    ("'bookings.BookingPayment'", "'bookings.QuotationPayment'"),
    ("'bookings.BookingLine'", "'bookings.QuotationLine'"),
    ("'bookings.BookingGroup'", "'bookings.QuotationGroup'"),
    ("'bookings.BookingPaymentLink'", "'bookings.QuotationPaymentLink'"),
    ("'bookings.BookingPaymentReceipt'", "'bookings.QuotationPaymentReceipt'"),
    ('booking-items', 'quotation-items'),
    ('booking-statuses', 'quotation-statuses'),
    ('booking-payments', 'quotation-payments'),
    ('booking-payment-links', 'quotation-payment-links'),
    ('booking-payment-receipts', 'quotation-payment-receipts'),
    ('booking-groups', 'quotation-groups'),
    ('booking-lines', 'quotation-lines'),
    ('booking-pdf', 'quotation-pdf'),
    ('booking_pdfs/', 'quotation_pdfs/'),
    ('booking_view', 'quotation_view'),
    ('bookings_group_name', 'quotations_group_name'),
    ("feature_key='bookings'", "feature_key='quotations'"),
    ("feature_key='booking_settings_statuses'", "feature_key='quotation_settings_statuses'"),
    ("'booking_settings_statuses'", "'quotation_settings_statuses'"),
    ('ResourceType.BOOKING', 'ResourceType.QUOTATION'),
    ('EntityType.BOOKING_STATUS', 'EntityType.QUOTATION_STATUS'),
    ('EntityType.BOOKING_LINE', 'EntityType.QUOTATION_LINE'),
    ('EntityType.BOOKING_GROUP', 'EntityType.QUOTATION_GROUP'),
    ('EntityType.BOOKING', 'EntityType.QUOTATION'),
    ("'booking_status'", "'quotation_status'"),
    ("'booking_line'", "'quotation_line'"),
    ("'booking_group'", "'quotation_group'"),
    ("resource_type='booking'", "resource_type='quotation'"),
    ("entity_type='booking'", "entity_type='quotation'"),
    ('email-templates/bookings/', 'email-templates/quotations/'),
    ("template_type='bookings'", "template_type='quotations'"),
    ("type='bookings'", "type='quotations'"),
    ('TYPE_BOOKINGS', 'TYPE_QUOTATIONS'),
    ('admin/booking-payments', 'admin/quotation-payments'),
    ('admin/booking-payment', 'admin/quotation-payment'),
    ('supplier-booking-capacity', 'supplier-quotation-capacity'),
    # FK / query lookups (after class renames)
    ('booking_id', 'quotation_id'),
    ('booking_title', 'quotation_title'),
    ('booking_payment_id', 'quotation_payment_id'),
    ('booking_group_id', 'quotation_group_id'),
    ('booking__', 'quotation__'),
    ('select_related("booking")', 'select_related("quotation")'),
    ("select_related('booking')", "select_related('quotation')"),
    ('prefetch_related("booking")', 'prefetch_related("quotation")'),
    ("prefetch_related('booking')", "prefetch_related('quotation')"),
    ('filter(booking_id=', 'filter(quotation_id='),
    ('.booking_id', '.quotation_id'),
]

# Replace permission feature key only in specific contexts
FEATURE_BOOKINGS = [
    ("permissions.get('bookings'", "permissions.get('quotations'"),
    ("'bookings' in permissions", "'quotations' in permissions"),
    ("feature_key == 'bookings'", "feature_key == 'quotations'"),
    ('FEATURE_BOOKINGS', 'FEATURE_QUOTATIONS'),
    ("'bookings',", "'quotations',"),
    ('"bookings",', '"quotations",'),
]


def should_skip(path: Path) -> bool:
    if any(p in SKIP_DIRS for p in path.parts):
        return True
    return path.suffix != '.py'


def transform(content: str) -> str:
    for old, new in CLASS_RENAMES:
        content = content.replace(old, new)
    for old, new in STRING_RENAMES:
        content = content.replace(old, new)
    for old, new in FEATURE_BOOKINGS:
        content = content.replace(old, new)
    # Field names on models/serializers (not db tables)
    content = content.replace('booking = serializers', 'quotation = serializers')
    content = content.replace('booking = models.ForeignKey', 'quotation = models.ForeignKey')
    content = content.replace(
        "ForeignKey(\n        'bookings.Quotation',\n        on_delete=models.SET_NULL,\n        null=True,\n        blank=True,\n        db_column='quotation_id',\n        related_name='calendar_events',\n    )",
        "quotation = models.ForeignKey(\n        'bookings.Quotation',\n        on_delete=models.SET_NULL,\n        null=True,\n        blank=True,\n        db_column='quotation_id',\n        related_name='calendar_events',\n    )",
    )
    return content


def main() -> None:
    changed = []
    for path in ROOT.rglob('*.py'):
        if should_skip(path):
            continue
        original = path.read_text(encoding='utf-8')
        text = transform(original)
        if text != original:
            path.write_text(text, encoding='utf-8')
            changed.append(path.relative_to(ROOT))
    print(f'Updated {len(changed)} files')


if __name__ == '__main__':
    main()
