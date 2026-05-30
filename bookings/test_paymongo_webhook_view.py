import hashlib
import hmac
import json
import time

from django.test import TestCase, override_settings
from django.urls import reverse

from payments.models import WebhookLog


def _paymongo_signature(payload: bytes, secret: str, *, live: bool = False) -> str:
    timestamp = str(int(time.time()))
    signed = f'{timestamp}.{payload.decode("utf-8")}'.encode('utf-8')
    digest = hmac.new(secret.encode('utf-8'), signed, hashlib.sha256).hexdigest()
    if live:
        return f't={timestamp},te=,li={digest}'
    return f't={timestamp},te={digest},li='


@override_settings(PAYMONGO_WEBHOOK_SECRET='whsec_test_platform')
class PayMongoWebhookViewLogTests(TestCase):
    def test_logs_payload_before_signature_validation(self):
        payload = {'data': {'id': 'evt_log_test', 'attributes': {'type': 'test.event'}}}

        response = self.client.post(
            reverse('paymongo-webhook'),
            data=json.dumps(payload),
            content_type='application/json',
        )

        self.assertEqual(WebhookLog.objects.count(), 1)
        log = WebhookLog.objects.get()
        self.assertEqual(log.source, 'paymongo')
        self.assertEqual(log.payload, payload)
        self.assertIsNotNone(log.created_at)
        self.assertIsNotNone(log.processed_at)
        self.assertFalse(log.handled)
        self.assertEqual(log.error_message, 'Invalid signature')
        self.assertEqual(response.status_code, 400)

    def test_logs_non_json_body(self):
        raw = b'not-json'

        response = self.client.post(
            reverse('paymongo-webhook'),
            data=raw,
            content_type='application/json',
        )

        self.assertEqual(WebhookLog.objects.count(), 1)
        log = WebhookLog.objects.get()
        self.assertEqual(log.payload, {'_raw': 'not-json'})
        self.assertEqual(response.status_code, 400)

    def test_accepts_valid_test_mode_signature(self):
        payload = {
            'data': {
                'id': 'evt_ok',
                'attributes': {'type': 'event.not_handled', 'data': None},
            },
        }
        raw = json.dumps(payload).encode('utf-8')
        response = self.client.post(
            reverse('paymongo-webhook'),
            data=raw,
            content_type='application/json',
            HTTP_PAYMONGO_SIGNATURE=_paymongo_signature(raw, 'whsec_test_platform'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['received'])

    def test_accepts_valid_live_mode_signature(self):
        payload = {
            'data': {
                'id': 'evt_live',
                'attributes': {'type': 'event.not_handled', 'data': None},
            },
        }
        raw = json.dumps(payload).encode('utf-8')
        response = self.client.post(
            reverse('paymongo-webhook'),
            data=raw,
            content_type='application/json',
            HTTP_PAYMONGO_SIGNATURE=_paymongo_signature(
                raw,
                'whsec_test_platform',
                live=True,
            ),
        )
        self.assertEqual(response.status_code, 200)
