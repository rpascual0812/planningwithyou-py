from django.db import migrations, models

SUPPLIER_TYPE_NAMES = [
    'Ceremony venue',
    'Reception venue',
    'Coordinator',
    'Caterer',
    'Florist',
    'Events stylist',
    'Host/Emcee',
    'Musician',
    'Photographer',
    'Videographer',
    'Lights & sounds',
    'Bridal car',
    'Suit & gown',
    'Cake supplier',
    'Hairstylist',
    'Make up artist',
    'Invitations',
    'Souvenirs',
    'Photobooth',
    'Crew meals',
    'Decoration/ Stylings',
    'Ring bearer pillow',
    'Flower girl basket',
    'Veil, Candle, Cord',
    'Ushers',
    'Bridal gown',
    'Jewelry',
    'Bridal headpiece/ veil',
    'Bridal shoes',
    'Bridesmaid dresses',
    'Bridesmaid accessories',
    'Bridesmaid shoes',
    "Groom's suit",
    'Groomsmen suits',
    'Garters',
    'Dress/ suit alterations',
    'Pre-nup outfits',
    'Honeymoon clothes',
    "Children's apparel",
    "Bride's bouquet",
    'Bridesmaid bouquets',
    'Flower girls flower',
    'Throw away bouquet',
    'Corsages',
    'Boutonniere',
    'Altarpiece',
    'Chair bows',
    'Venue',
    'Caterer',
    'Decorations',
    'Sound system',
    'Guest parking',
    'Servers',
    'Wedding Bands',
    'Engagement Ring',
    'Engraving',
    'Prenup shoot',
    'Photo albums',
    'Bridal portraits',
    'Same day edit photos or videos',
    'Guest book',
    'Save the date cards',
    'Postage',
    'Thank you notes',
    'Guests parking',
    'Transportation',
    'Prizes',
    'Extra chair/ tables',
    'Fireworks/ sparklers/ wands',
    'Principal sponsors gift',
    'Entourage gift',
    'Gift for fiancee',
    'Suppliers gift',
    'Marriage License',
    'Manicure/pedicure',
    'Preparation venue',
    'Buffer',
]


def seed_supplier_types(apps, schema_editor):
    SupplierType = apps.get_model('suppliers', 'SupplierType')
    SupplierType.objects.bulk_create(
        [SupplierType(name=name, is_active=True) for name in SUPPLIER_TYPE_NAMES],
    )


def unseed_supplier_types(apps, schema_editor):
    SupplierType = apps.get_model('suppliers', 'SupplierType')
    SupplierType.objects.filter(name__in=SUPPLIER_TYPE_NAMES).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SupplierType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'db_table': 'supplier_types',
                'ordering': ['name'],
            },
        ),
        migrations.RunPython(seed_supplier_types, unseed_supplier_types),
    ]
