"""Marketplace document: Tan Beige Modern Elegance (Eric & Li Canva clone)."""

CANVA_SOURCE_URL = 'https://planningwithyoutest1.my.canva.site/'

# Palette from Canva "Tan Beige Modern Elegance"
CREAM = '#F7F3ED'
TAN = '#EDE6DC'
WARM_BROWN = '#8B7355'
DEEP_BROWN = '#5C4A3A'
INK = '#2C2419'
WHITE = '#FFFFFF'

HERO_IMAGE = (
    'https://images.unsplash.com/photo-1519741497674-611481863552'
    '?auto=format&fit=crop&w=800&q=80'
)


def _text(
    el_id: str,
    name: str,
    content: str,
    x: float,
    y: float,
    w: float,
    h: float,
    z: int,
    *,
    font_size: int = 16,
    fill: str = INK,
    align: str = 'center',
    font: str = 'Cormorant Garamond',
    weight: str = 'normal',
    line_height: float = 1.45,
):
    return {
        'id': el_id,
        'type': 'text',
        'name': name,
        'content': content,
        'style': {
            'fontFamily': font,
            'fontSize': font_size,
            'fill': fill,
            'fontWeight': weight,
            'fontStyle': 'normal',
            'underline': False,
            'charSpacing': 0,
            'textAlign': align,
            'lineHeight': line_height,
        },
        'transform': {
            'x': x,
            'y': y,
            'width': w,
            'height': h,
            'rotation': 0,
            'scaleX': 1,
            'scaleY': 1,
            'opacity': 1,
            'zIndex': z,
        },
    }


def _countdown(el_id: str, y: float, z: int):
    return {
        'id': el_id,
        'type': 'countdown',
        'name': 'Wedding countdown',
        'targetDate': '2030-10-10T15:00:00',
        'label': 'Until we say I do',
        'transform': {
            'x': 48,
            'y': y,
            'width': 294,
            'height': 72,
            'rotation': 0,
            'scaleX': 1,
            'scaleY': 1,
            'opacity': 1,
            'zIndex': z,
        },
    }


def _rsvp(el_id: str, y: float, z: int):
    return {
        'id': el_id,
        'type': 'rsvp',
        'name': 'RSVP',
        'heading': "We can't wait to hear from you",
        'submitLabel': 'Send message',
        'successMessage': 'Thank you! Your RSVP has been received.',
        'fields': [
            {
                'id': 'first_name',
                'label': 'First Name',
                'type': 'text',
                'required': True,
                'placeholder': 'First name',
            },
            {
                'id': 'last_name',
                'label': 'Last Name',
                'type': 'text',
                'required': True,
                'placeholder': 'Last name',
            },
            {
                'id': 'mobile_number',
                'label': 'Mobile Number',
                'type': 'tel',
                'required': False,
                'placeholder': 'Mobile number',
            },
            {
                'id': 'email_address',
                'label': 'Email Address',
                'type': 'email',
                'required': True,
                'placeholder': 'Email address',
            },
        ],
        'transform': {
            'x': 24,
            'y': y,
            'width': 342,
            'height': 320,
            'rotation': 0,
            'scaleX': 1,
            'scaleY': 1,
            'opacity': 1,
            'zIndex': z,
        },
    }


def modern_elegance_document() -> dict:
    return {
        'schemaVersion': 1,
        'meta': {
            'id': 'mkt_tan_beige_modern_elegance',
            'title': 'Tan Beige Modern Elegance',
            'name': 'Tan Beige Modern Elegance',
            'description': (
                'Full wedding website inspired by Canva Modern Elegance — '
                'hero monogram, love story, schedule, registry, and guest info.'
            ),
            'category': 'wedding',
            'tags': ['marketplace', 'canva-clone', 'modern-elegance', 'tan', 'beige'],
            'version': 1,
            'marketplaceId': 'tan-beige-modern-elegance',
            'createdAt': '2026-01-01T00:00:00Z',
            'updatedAt': '2026-01-01T00:00:00Z',
        },
        'globalFonts': ['Playfair Display', 'Cormorant Garamond', 'Montserrat'],
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
                'background': {
                    'type': 'image',
                    'imageUrl': HERO_IMAGE,
                    'overlayColor': '#000000',
                    'overlayOpacity': 0.42,
                },
                'transition': 'fade',
                'elements': [
                    _text(
                        'el_monogram',
                        'Monogram',
                        'E  &  L',
                        95,
                        72,
                        200,
                        48,
                        3,
                        font_size=22,
                        fill=WHITE,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_names',
                        'Couple names',
                        'ERIC & LI',
                        24,
                        320,
                        342,
                        64,
                        4,
                        font_size=42,
                        fill=WHITE,
                        font='Playfair Display',
                        weight='normal',
                    ),
                    _text(
                        'el_date',
                        'Wedding date',
                        'October 10, 2030',
                        24,
                        400,
                        342,
                        36,
                        4,
                        font_size=18,
                        fill=WHITE,
                        font='Cormorant Garamond',
                    ),
                    _countdown('el_countdown', 480, 5),
                ],
            },
            {
                'id': 'pg_story',
                'name': 'Our Story',
                'slug': 'story',
                'sectionType': 'story',
                'width': 390,
                'height': 844,
                'background': {'type': 'solid', 'color': WARM_BROWN},
                'transition': 'slide-up',
                'elements': [
                    _text(
                        'el_story_kicker',
                        'Story kicker',
                        'A chance encounter',
                        24,
                        80,
                        342,
                        48,
                        1,
                        font_size=32,
                        fill=WHITE,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_story_body',
                        'Story body',
                        (
                            'Write a paragraph that tells your story as a couple. '
                            'You can include details like how you met, your journey together, '
                            'and what makes your relationship unique. This is your chance to '
                            'share your personality and connect with your guests, giving them '
                            'a glimpse into your love story and what this special day means to you.'
                        ),
                        32,
                        160,
                        326,
                        280,
                        2,
                        font_size=15,
                        fill=CREAM,
                        align='left',
                        line_height=1.6,
                    ),
                ],
            },
            {
                'id': 'pg_promise',
                'name': 'Promise',
                'slug': 'promise',
                'sectionType': 'custom',
                'width': 390,
                'height': 844,
                'background': {'type': 'solid', 'color': TAN},
                'transition': 'fade',
                'elements': [
                    _text(
                        'el_promise_1',
                        'Promise line 1',
                        'A promise',
                        24,
                        100,
                        342,
                        52,
                        1,
                        font_size=36,
                        fill=INK,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_promise_2',
                        'Promise line 2',
                        'for life',
                        24,
                        152,
                        342,
                        52,
                        2,
                        font_size=36,
                        fill=DEEP_BROWN,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_promise_body',
                        'Ceremony details',
                        (
                            'Share details about your ceremony, reception, or any other '
                            'program-related thing here. Share details about your ceremony, '
                            'reception, or any other program-related thing here. Share details '
                            'about your ceremony, reception, or any other program-related thing here.'
                        ),
                        32,
                        240,
                        326,
                        200,
                        3,
                        font_size=14,
                        fill=DEEP_BROWN,
                        align='left',
                        line_height=1.55,
                    ),
                ],
            },
            {
                'id': 'pg_events',
                'name': 'Events',
                'slug': 'events',
                'sectionType': 'schedule',
                'width': 390,
                'height': 844,
                'background': {'type': 'solid', 'color': CREAM},
                'transition': 'slide-up',
                'elements': [
                    _text(
                        'el_events_date',
                        'Event date',
                        'October 10, 2030',
                        24,
                        48,
                        342,
                        36,
                        1,
                        font_size=20,
                        fill=WARM_BROWN,
                        font='Cormorant Garamond',
                    ),
                    _text(
                        'el_events_title_1',
                        'Events title 1',
                        "The Day's",
                        24,
                        88,
                        342,
                        44,
                        2,
                        font_size=34,
                        fill=INK,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_events_title_2',
                        'Events title 2',
                        'Events',
                        24,
                        132,
                        342,
                        44,
                        3,
                        font_size=34,
                        fill=INK,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_schedule',
                        'Schedule',
                        (
                            '3:00 PM — Vows and I Do\'s\n\n'
                            '4:00 PM — Cocktail Hour\n\n'
                            '5:00 PM — Dinner and Dancing\n\n'
                            '8:00 PM — The Send-off'
                        ),
                        40,
                        200,
                        310,
                        320,
                        4,
                        font_size=16,
                        fill=DEEP_BROWN,
                        align='left',
                        line_height=1.75,
                        font='Montserrat',
                    ),
                ],
            },
            {
                'id': 'pg_registry',
                'name': 'Registry',
                'slug': 'registry',
                'sectionType': 'custom',
                'width': 390,
                'height': 844,
                'background': {'type': 'solid', 'color': TAN},
                'transition': 'fade',
                'elements': [
                    _text(
                        'el_registry_title',
                        'Registry title',
                        'Wedding Registry',
                        24,
                        64,
                        342,
                        48,
                        1,
                        font_size=32,
                        fill=INK,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_registry_intro',
                        'Registry intro',
                        (
                            'We treasure your presence the most, but if you wish to honor us '
                            'with a gift, we have registered at the following stores:'
                        ),
                        32,
                        130,
                        326,
                        100,
                        2,
                        font_size=14,
                        fill=DEEP_BROWN,
                        align='left',
                        line_height=1.5,
                    ),
                    _text(
                        'el_store_1',
                        'Store 1',
                        'Cozy Homes Inc.\nwww.reallygreatsite.com',
                        32,
                        260,
                        326,
                        72,
                        3,
                        font_size=15,
                        fill=INK,
                        align='left',
                    ),
                    _text(
                        'el_store_2',
                        'Store 2',
                        'Blissfully Home Lifestyle Center\nwww.reallygreatsite.com',
                        32,
                        360,
                        326,
                        72,
                        4,
                        font_size=15,
                        fill=INK,
                        align='left',
                    ),
                ],
            },
            {
                'id': 'pg_guest',
                'name': 'Guest Info',
                'slug': 'guest-info',
                'sectionType': 'custom',
                'width': 390,
                'height': 1200,
                'background': {'type': 'solid', 'color': CREAM},
                'transition': 'slide-up',
                'elements': [
                    _text(
                        'el_guest_title',
                        'Guest info title',
                        'Guest information',
                        24,
                        48,
                        342,
                        44,
                        1,
                        font_size=28,
                        fill=INK,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_dress_title',
                        'Dress code title',
                        'Dress Code',
                        24,
                        120,
                        342,
                        36,
                        2,
                        font_size=22,
                        fill=WARM_BROWN,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_dress_body',
                        'Dress code body',
                        (
                            'We kindly request a formal dress code for our wedding celebration. '
                            'Gentlemen should wear either a suit or a tuxedo, while ladies are '
                            'encouraged to don a formal cocktail dress or an evening gown. '
                            "We can't wait to see you looking your finest!"
                        ),
                        32,
                        168,
                        326,
                        160,
                        3,
                        font_size=14,
                        fill=DEEP_BROWN,
                        align='left',
                        line_height=1.5,
                    ),
                    _text(
                        'el_mobile_title',
                        'Mobile-free title',
                        'Mobile-Free Ceremony',
                        24,
                        360,
                        342,
                        36,
                        4,
                        font_size=22,
                        fill=WARM_BROWN,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_mobile_body',
                        'Mobile-free body',
                        (
                            'To ensure everyone fully enjoys the moment and no photos are '
                            'interrupted, we kindly request you to please refrain from using '
                            'your mobile phones during the ceremony. Thank you for your understanding.'
                        ),
                        32,
                        408,
                        326,
                        120,
                        5,
                        font_size=14,
                        fill=DEEP_BROWN,
                        align='left',
                        line_height=1.5,
                    ),
                    _text(
                        'el_contact_heading_1',
                        'Contact heading 1',
                        "We can't wait",
                        24,
                        560,
                        342,
                        40,
                        6,
                        font_size=28,
                        fill=INK,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_contact_heading_2',
                        'Contact heading 2',
                        'to hear from you',
                        24,
                        600,
                        342,
                        40,
                        7,
                        font_size=28,
                        fill=INK,
                        font='Playfair Display',
                    ),
                    _text(
                        'el_organizer',
                        'Organizer',
                        'Li Mei\nWedding Organizer',
                        24,
                        660,
                        342,
                        56,
                        8,
                        font_size=16,
                        fill=DEEP_BROWN,
                    ),
                    _text(
                        'el_phone',
                        'Phone',
                        'Phone\n(123) 456-7890',
                        24,
                        740,
                        342,
                        48,
                        9,
                        font_size=14,
                        fill=DEEP_BROWN,
                        align='left',
                    ),
                    _text(
                        'el_email',
                        'Email',
                        'Email\nhello@reallygreatsite.com',
                        24,
                        800,
                        342,
                        48,
                        10,
                        font_size=14,
                        fill=DEEP_BROWN,
                        align='left',
                    ),
                    _rsvp('el_rsvp', 880, 11),
                ],
            },
        ],
    }


MARKETPLACE_ENTRY = {
    'title': 'Tan Beige Modern Elegance',
    'slug': 'tan-beige-modern-elegance',
    'category': 'wedding',
    'description': (
        'Canva-style full wedding website — hero monogram, love story, schedule, '
        'registry, dress code, and RSVP. Inspired by Modern Elegance in tan & beige.'
    ),
    'marketplace_preview_url': CANVA_SOURCE_URL,
    'document': modern_elegance_document(),
}
