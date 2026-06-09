"""Store relative proxy paths on quotations.pdf instead of localhost absolute URLs."""

from urllib.parse import urlparse

from django.db import migrations


def normalize_quotation_pdf_urls(apps, schema_editor):
    Quotation = apps.get_model('bookings', 'Quotation')
    for quotation in Quotation.objects.exclude(pdf='').exclude(pdf__isnull=True):
        pdf = (quotation.pdf or '').strip()
        if not pdf or pdf.startswith('/files/b/'):
            continue
        if pdf.startswith(('http://', 'https://')):
            path = urlparse(pdf).path
            if path.startswith('/files/b/'):
                quotation.pdf = path
                quotation.save(update_fields=['pdf'])


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0058_backfill_formtemplate_company'),
    ]

    operations = [
        migrations.RunPython(normalize_quotation_pdf_urls, migrations.RunPython.noop),
    ]
