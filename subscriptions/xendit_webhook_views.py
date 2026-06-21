"""Inbound Xendit webhook endpoint for subscription billing."""

from __future__ import annotations

import json
import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config.error_logging import log_request_error
from payments.webhook_logging import finalize_webhook_log, log_webhook

from .xendit_webhook import handle_xendit_webhook_body, verify_xendit_callback_token

logger = logging.getLogger(__name__)

XENDIT_WEBHOOK_SOURCE = 'xendit'


@method_decorator(csrf_exempt, name='dispatch')
class XenditWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = request.body or b''
        webhook_log = log_webhook(
            XENDIT_WEBHOOK_SOURCE,
            raw,
            meta={
                'content_type': request.headers.get('Content-Type', ''),
                'has_callback_token': bool(request.headers.get('x-callback-token')),
            },
        )
        callback_token = request.headers.get('x-callback-token')
        if not verify_xendit_callback_token(callback_token):
            finalize_webhook_log(
                webhook_log,
                handled=False,
                error_message='Invalid callback token',
            )
            return Response({'detail': 'Invalid callback token.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            body = json.loads(raw.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            finalize_webhook_log(
                webhook_log,
                handled=False,
                error_message='Invalid JSON',
            )
            return Response({'detail': 'Invalid JSON.'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(body, dict):
            finalize_webhook_log(
                webhook_log,
                handled=False,
                error_message='Invalid JSON envelope',
            )
            return Response(
                {'detail': 'Invalid JSON envelope.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        handled = False
        try:
            handled = handle_xendit_webhook_body(body)
            finalize_webhook_log(webhook_log, handled=handled)
        except Exception as exc:
            logger.exception('Xendit webhook processing failed (log_id=%s)', webhook_log.pk)
            log_request_error(request, exception=exc, status_code=500)
            finalize_webhook_log(
                webhook_log,
                handled=False,
                error_message=str(exc),
            )

        return Response({
            'received': True,
            'handled': handled,
            'webhook_log_id': webhook_log.pk,
        })
