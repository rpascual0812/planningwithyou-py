# Generated manually — renames tables/columns and model state (no data loss).

from django.db import migrations, models
import django.db.models.deletion


def forwards_data(apps, schema_editor):
    History = apps.get_model('bookings', 'History')
    History.objects.filter(resource_type='booking').update(resource_type='quotation')
    History.objects.filter(resource_type='booking_status').update(
        resource_type='quotation_status',
    )
    entity_map = {
        'booking': 'quotation',
        'booking_line': 'quotation_line',
        'booking_group': 'quotation_group',
        'booking_status': 'quotation_status',
    }
    for old, new in entity_map.items():
        History.objects.filter(entity_type=old).update(entity_type=new)

    try:
        RolePermission = apps.get_model('users', 'RolePermission')
    except LookupError:
        RolePermission = None
    if RolePermission is not None:
        RolePermission.objects.filter(feature_key='bookings').update(feature_key='quotations')
        RolePermission.objects.filter(feature_key='booking_settings_statuses').update(
            feature_key='quotation_settings_statuses',
        )

    try:
        EmailTemplate = apps.get_model('emails', 'EmailTemplate')
    except LookupError:
        EmailTemplate = None
    if EmailTemplate is not None:
        EmailTemplate.objects.filter(template_type='bookings').update(template_type='quotations')

    try:
        Config = apps.get_model('config', 'Config')
    except LookupError:
        Config = None
    if Config is not None:
        Config.objects.filter(scope='account', name='booking_view').update(name='quotation_view')
        Config.objects.filter(scope='account', name='bookings_group_name').update(
            name='quotations_group_name',
        )


def backwards_data(apps, schema_editor):
    History = apps.get_model('bookings', 'History')
    History.objects.filter(resource_type='quotation').update(resource_type='booking')
    History.objects.filter(resource_type='quotation_status').update(
        resource_type='booking_status',
    )
    entity_map = {
        'quotation': 'booking',
        'quotation_line': 'booking_line',
        'quotation_group': 'booking_group',
        'quotation_status': 'booking_status',
    }
    for old, new in entity_map.items():
        History.objects.filter(entity_type=old).update(entity_type=new)

    RolePermission = apps.get_model('users', 'RolePermission')
    RolePermission.objects.filter(feature_key='quotations').update(feature_key='bookings')
    RolePermission.objects.filter(feature_key='quotation_settings_statuses').update(
        feature_key='booking_settings_statuses',
    )

    EmailTemplate = apps.get_model('emails', 'EmailTemplate')
    EmailTemplate.objects.filter(template_type='quotations').update(template_type='bookings')

    Config = apps.get_model('config', 'Config')
    Config.objects.filter(scope='account', name='quotation_view').update(name='booking_view')
    Config.objects.filter(scope='account', name='quotations_group_name').update(
        name='bookings_group_name',
    )


RENAME_SQL = """
ALTER TABLE booking_statuses RENAME TO quotation_statuses;
ALTER TABLE IF EXISTS booking_statuses_tags RENAME TO quotation_statuses_tags;
ALTER TABLE IF EXISTS quotation_statuses_tags
    RENAME COLUMN bookingstatus_id TO quotationstatus_id;

ALTER TABLE bookings RENAME TO quotations;
ALTER TABLE booking_groups RENAME TO quotation_groups;
ALTER TABLE booking_items RENAME TO quotation_lines;
ALTER TABLE booking_payments RENAME TO quotation_payments;
ALTER TABLE booking_payment_links RENAME TO quotation_payment_links;
ALTER TABLE booking_payment_receipts RENAME TO quotation_payment_receipts;
ALTER TABLE booking_unique_id_sequences RENAME TO quotation_unique_id_sequences;

ALTER TABLE quotation_groups RENAME COLUMN booking_id TO quotation_id;
ALTER TABLE quotation_lines RENAME COLUMN booking_id TO quotation_id;
ALTER TABLE quotation_lines RENAME COLUMN booking_group_id TO quotation_group_id;
ALTER TABLE quotation_payments RENAME COLUMN booking_id TO quotation_id;
ALTER TABLE quotation_payment_links RENAME COLUMN booking_id TO quotation_id;
ALTER TABLE quotation_payment_receipts RENAME COLUMN booking_id TO quotation_id;
ALTER TABLE quotation_payment_receipts RENAME COLUMN booking_payment_id TO quotation_payment_id;

ALTER TABLE history RENAME COLUMN booking_id TO quotation_id;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'bookings_account_unique_id_uniq'
    ) THEN
        ALTER TABLE quotations
            RENAME CONSTRAINT bookings_account_unique_id_uniq
            TO quotations_account_unique_id_uniq;
    ELSIF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'bookings_company_unique_id_uniq'
    ) THEN
        ALTER TABLE quotations
            RENAME CONSTRAINT bookings_company_unique_id_uniq
            TO quotations_account_unique_id_uniq;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'booking_groups_booking_name_uniq'
    ) THEN
        ALTER TABLE quotation_groups
            RENAME CONSTRAINT booking_groups_booking_name_uniq
            TO quotation_groups_quotation_name_uniq;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'booking_unique_id_seq_company_year_uniq'
    ) THEN
        ALTER TABLE quotation_unique_id_sequences
            RENAME CONSTRAINT booking_unique_id_seq_company_year_uniq
            TO quotation_unique_id_seq_company_year_uniq;
    END IF;
END $$;

ALTER INDEX IF EXISTS history_booking_02b548_idx RENAME TO history_quotati_a0bab6_idx;
"""

REVERSE_SQL = """
ALTER INDEX IF EXISTS history_quotati_a0bab6_idx RENAME TO history_booking_02b548_idx;

ALTER TABLE quotation_unique_id_sequences
    RENAME CONSTRAINT quotation_unique_id_seq_company_year_uniq
    TO booking_unique_id_seq_company_year_uniq;
ALTER TABLE quotation_groups
    RENAME CONSTRAINT quotation_groups_quotation_name_uniq TO booking_groups_booking_name_uniq;
ALTER TABLE quotations
    RENAME CONSTRAINT quotations_account_unique_id_uniq TO bookings_account_unique_id_uniq;

ALTER TABLE history RENAME COLUMN quotation_id TO booking_id;

ALTER TABLE quotation_payment_receipts RENAME COLUMN quotation_payment_id TO booking_payment_id;
ALTER TABLE quotation_payment_receipts RENAME COLUMN quotation_id TO booking_id;
ALTER TABLE quotation_payment_links RENAME COLUMN quotation_id TO booking_id;
ALTER TABLE quotation_payments RENAME COLUMN quotation_id TO booking_id;
ALTER TABLE quotation_lines RENAME COLUMN quotation_group_id TO booking_group_id;
ALTER TABLE quotation_lines RENAME COLUMN quotation_id TO booking_id;
ALTER TABLE quotation_groups RENAME COLUMN quotation_id TO booking_id;

ALTER TABLE quotation_unique_id_sequences RENAME TO booking_unique_id_sequences;
ALTER TABLE quotation_payment_receipts RENAME TO booking_payment_receipts;
ALTER TABLE quotation_payment_links RENAME TO booking_payment_links;
ALTER TABLE quotation_payments RENAME TO booking_payments;
ALTER TABLE quotation_lines RENAME TO booking_items;
ALTER TABLE quotation_groups RENAME TO booking_groups;
ALTER TABLE quotations RENAME TO bookings;

ALTER TABLE IF EXISTS quotation_statuses_tags
    RENAME COLUMN quotationstatus_id TO bookingstatus_id;
ALTER TABLE IF EXISTS quotation_statuses_tags RENAME TO booking_statuses_tags;
ALTER TABLE quotation_statuses RENAME TO booking_statuses;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0055_alter_history_resource_type'),
        ('calendars', '0007_google_calendar_integration'),
        ('users', '0034_admin_error_logs_permission'),
        ('emails', '0024_alter_emailtemplate_template_type'),
        ('config', '0002_config_account'),
    ]

    operations = [
        migrations.RunSQL(RENAME_SQL, REVERSE_SQL),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameModel('BookingStatus', 'QuotationStatus'),
                migrations.RenameModel('BookingItem', 'Quotation'),
                migrations.RenameModel('BookingPayment', 'QuotationPayment'),
                migrations.RenameModel('BookingPaymentReceipt', 'QuotationPaymentReceipt'),
                migrations.RenameModel('BookingPaymentLink', 'QuotationPaymentLink'),
                migrations.RenameModel('BookingUniqueIdSequence', 'QuotationUniqueIdSequence'),
                migrations.RenameModel('BookingGroup', 'QuotationGroup'),
                migrations.RenameModel('BookingLine', 'QuotationLine'),
                migrations.AlterModelTable('QuotationStatus', 'quotation_statuses'),
                migrations.AlterModelTable('Quotation', 'quotations'),
                migrations.AlterModelTable('QuotationPayment', 'quotation_payments'),
                migrations.AlterModelTable('QuotationPaymentReceipt', 'quotation_payment_receipts'),
                migrations.AlterModelTable('QuotationPaymentLink', 'quotation_payment_links'),
                migrations.AlterModelTable('QuotationUniqueIdSequence', 'quotation_unique_id_sequences'),
                migrations.AlterModelTable('QuotationGroup', 'quotation_groups'),
                migrations.AlterModelTable('QuotationLine', 'quotation_lines'),
                migrations.RenameField(
                    model_name='quotationpayment',
                    old_name='booking',
                    new_name='quotation',
                ),
                migrations.RenameField(
                    model_name='quotationpaymentlink',
                    old_name='booking',
                    new_name='quotation',
                ),
                migrations.RenameField(
                    model_name='quotationpaymentreceipt',
                    old_name='booking',
                    new_name='quotation',
                ),
                migrations.RenameField(
                    model_name='quotationpaymentreceipt',
                    old_name='booking_payment',
                    new_name='quotation_payment',
                ),
                migrations.RenameField(
                    model_name='quotationgroup',
                    old_name='booking',
                    new_name='quotation',
                ),
                migrations.RenameField(
                    model_name='quotationline',
                    old_name='booking',
                    new_name='quotation',
                ),
                migrations.RenameField(
                    model_name='quotationline',
                    old_name='booking_group',
                    new_name='quotation_group',
                ),
                migrations.RenameField(
                    model_name='history',
                    old_name='booking',
                    new_name='quotation',
                ),
                migrations.AlterField(
                    model_name='history',
                    name='resource_type',
                    field=models.CharField(
                        choices=[
                            ('quotation', 'Quotation'),
                            ('account', 'Account'),
                            ('company', 'Company'),
                            ('user', 'User'),
                            ('contact', 'Contact'),
                            ('supplier_setting', 'Supplier setting'),
                            ('quotation_status', 'Quotation status'),
                            ('email_template', 'Email template'),
                            ('form_template', 'Form template'),
                        ],
                        default='quotation',
                        max_length=32,
                    ),
                ),
                migrations.RenameIndex(
                    model_name='history',
                    new_name='history_quotati_a0bab6_idx',
                    old_name='history_booking_02b548_idx',
                ),
            ],
        ),
        migrations.RunPython(forwards_data, backwards_data),
    ]
