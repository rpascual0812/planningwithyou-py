from django.db import migrations


def _base_doc(title: str, category: str, hero_bg: str, accent: str):
    return {
        'schemaVersion': 1,
        'meta': {
            'id': f'mkt_{title.lower().replace(" ", "_")}',
            'title': title,
            'name': title,
            'description': f'{title} marketplace starter',
            'category': category,
            'tags': ['marketplace'],
            'version': 1,
            'createdAt': '2026-01-01T00:00:00Z',
            'updatedAt': '2026-01-01T00:00:00Z',
        },
        'globalFonts': ['Playfair Display', 'Lato'],
        'settings': {
            'snapGrid': 8,
            'showGuides': True,
            'defaultPageSize': {'width': 390, 'height': 844},
        },
        'pages': [
            {
                'id': 'pg_hero',
                'name': 'Hero',
                'slug': 'hero',
                'sectionType': 'hero',
                'width': 390,
                'height': 844,
                'background': {'type': 'solid', 'color': hero_bg},
                'elements': [
                    {
                        'id': 'el_title',
                        'type': 'text',
                        'name': 'Couple names',
                        'content': 'Your Names Here',
                        'style': {
                            'fontFamily': 'Playfair Display',
                            'fontSize': 40,
                            'fill': accent,
                            'fontWeight': 'normal',
                            'fontStyle': 'normal',
                            'underline': False,
                            'charSpacing': 0,
                            'textAlign': 'center',
                            'lineHeight': 1.35,
                        },
                        'transform': {
                            'x': 24, 'y': 140, 'width': 342, 'height': 56,
                            'rotation': 0, 'scaleX': 1, 'scaleY': 1,
                            'opacity': 1, 'zIndex': 2,
                        },
                    },
                ],
                'transition': 'fade',
            },
        ],
    }


MARKETPLACE = [
    {
        'title': 'Romantic Blush',
        'slug': 'romantic-blush',
        'category': 'wedding',
        'description': 'Soft blush tones with elegant serif typography.',
        'document': _base_doc('Romantic Blush', 'wedding', '#faf0ee', '#6b3e3e'),
    },
    {
        'title': 'Modern Minimal',
        'slug': 'modern-minimal',
        'category': 'wedding',
        'description': 'Clean white layout with bold modern type.',
        'document': _base_doc('Modern Minimal', 'wedding', '#ffffff', '#111111'),
    },
    {
        'title': 'Garden Estate',
        'slug': 'garden-estate',
        'category': 'wedding',
        'description': 'Earthy greens inspired by outdoor celebrations.',
        'document': _base_doc('Garden Estate', 'wedding', '#f4f7f0', '#2d4a3e'),
    },
]


def seed_marketplace(apps, schema_editor):
    InvitationTemplate = apps.get_model('template_studio', 'InvitationTemplate')
    for item in MARKETPLACE:
        if InvitationTemplate.objects.filter(slug=item['slug'], is_marketplace=True).exists():
            continue
        InvitationTemplate.objects.create(
            title=item['title'],
            slug=item['slug'],
            category=item['category'],
            description=item['description'],
            document=item['document'],
            is_marketplace=True,
            is_published=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('template_studio', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_marketplace, migrations.RunPython.noop),
    ]
