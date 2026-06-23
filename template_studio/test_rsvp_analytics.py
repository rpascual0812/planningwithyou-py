from datetime import date

from django.test import SimpleTestCase

from template_studio.rsvp_analytics import compute_rsvp_analytics


class RsvpAnalyticsTests(SimpleTestCase):
    def _template(self, document):
        return type(
            'TemplateStub',
            (),
            {'document': document, 'view_count': 25},
        )()

    def test_counts_attendance_and_guests(self):
        document = {
            'meta': {'expectedGuestCount': 8, 'rsvpDeadline': '2030-06-01'},
            'pages': [
                {
                    'elements': [
                        {
                            'type': 'rsvp',
                            'fields': [
                                {
                                    'id': 'attendance',
                                    'label': 'RSVP response',
                                    'type': 'select',
                                    'options': ['Will go', 'Will not go'],
                                },
                                {
                                    'id': 'guest_count',
                                    'label': 'Guests',
                                    'type': 'text',
                                },
                            ],
                        }
                    ]
                }
            ],
        }
        submissions = [
            {'fields_data': {'attendance': 'Will go', 'guest_count': '2'}},
            {'fields_data': {'attendance': 'Will not go', 'guest_count': '1'}},
        ]
        analytics = compute_rsvp_analytics(self._template(document), submissions)
        self.assertEqual(analytics['will_go'], 2)
        self.assertEqual(analytics['will_not_go'], 1)
        self.assertEqual(analytics['awaiting_reply'], 5)
        self.assertEqual(analytics['expected_visitors'], 8)
        self.assertEqual(analytics['total_views'], 25)

    def test_defaults_without_expected_guest_count(self):
        document = {
            'pages': [
                {
                    'elements': [
                        {
                            'type': 'rsvp',
                            'fields': [
                                {'id': 'first_name', 'label': 'First Name', 'type': 'text'},
                            ],
                        }
                    ]
                }
            ],
        }
        analytics = compute_rsvp_analytics(
            self._template(document),
            [{'fields_data': {'first_name': 'Jane'}}],
        )
        self.assertEqual(analytics['will_go'], 1)
        self.assertEqual(analytics['awaiting_reply'], 0)
        self.assertEqual(analytics['expected_visitors'], 1)

    def test_days_remaining_from_confirmation_deadline(self):
        future = date.today().replace(year=date.today().year + 1)
        document = {
            'pages': [
                {
                    'elements': [
                        {
                            'type': 'rsvp',
                            'rsvpDeadline': future.isoformat(),
                        }
                    ]
                }
            ],
        }
        analytics = compute_rsvp_analytics(self._template(document), [])
        self.assertGreater(analytics['days_remaining'], 200)
