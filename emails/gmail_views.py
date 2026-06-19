import logging

from django.shortcuts import redirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.error_logging import log_request_error
from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .gmail_service import (
    GmailConfigError,
    GmailOAuthError,
    build_authorization_url,
    complete_oauth_callback,
    disconnect_integration,
    frontend_redirect_url,
    get_integration_for_user,
    google_oauth_configured,
    integration_status_payload,
    unsign_oauth_state,
)

logger = logging.getLogger(__name__)


def _oauth_context_from_request(request) -> tuple[int | None, int | None]:
    state = request.query_params.get('state') or ''
    if not state:
        return None, None
    try:
        payload = unsign_oauth_state(state)
        return int(payload['account_id']), int(payload['user_id'])
    except GmailOAuthError:
        return None, None


def _log_gmail_oauth_callback_error(
    request,
    *,
    exception: BaseException | None = None,
    message: str = '',
    status_code: int = 400,
) -> None:
    account_id, user_id = _oauth_context_from_request(request)
    exc = exception
    if exc is None and message:
        exc = GmailOAuthError(message)
    log_request_error(
        request,
        exception=exc,
        status_code=status_code,
        account_id=account_id,
        user_id=user_id,
    )

class GmailIntegrationView(APIView):
    """Connect and disconnect Gmail for sending email from the active company."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'settings'

    def get(self, request):
        integration = get_integration_for_user(request.user)
        data = integration_status_payload(integration)
        data['authorization_url'] = None
        return Response(data)

    def put(self, request):
        if not google_oauth_configured():
            return Response(
                {
                    'detail': 'Gmail OAuth is not configured on the server.',
                    'configured': False,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        integration = get_integration_for_user(request.user)
        if integration and (integration.refresh_token_encrypted or '').strip():
            return Response(integration_status_payload(integration))

        try:
            auth_url = build_authorization_url(
                account_id=request.user.account_id,
                company_id=request.user.company_id,
                user_id=request.user.pk,
            )
        except GmailConfigError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        payload = integration_status_payload(integration)
        payload['authorization_url'] = auth_url
        return Response(payload)

    def delete(self, request):
        integration = get_integration_for_user(request.user)
        if integration is None:
            return Response(integration_status_payload(None))
        try:
            disconnect_integration(integration)
        except Exception:
            return Response(
                {'detail': 'Failed to disconnect Gmail.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(integration_status_payload(None))


class GmailOAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        error = request.query_params.get('error')
        if error:
            _log_gmail_oauth_callback_error(
                request,
                message=f'Google OAuth error: {error}',
                status_code=400,
            )
            return redirect(frontend_redirect_url(success=False, message=error))
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        if not code or not state:
            _log_gmail_oauth_callback_error(
                request,
                message='Gmail OAuth callback missing code or state.',
                status_code=400,
            )
            return redirect(
                frontend_redirect_url(success=False, message='missing_code'),
            )
        try:
            complete_oauth_callback(
                code=code,
                state=state,
            )
        except (GmailOAuthError, GmailConfigError) as exc:
            _log_gmail_oauth_callback_error(
                request,
                exception=exc,
                status_code=400,
            )
            return redirect(frontend_redirect_url(success=False, message=str(exc)))
        except Exception as exc:
            logger.exception('Gmail OAuth callback failed')
            _log_gmail_oauth_callback_error(
                request,
                exception=exc,
                status_code=500,
            )
            message = str(exc).strip() or 'oauth_failed'
            return redirect(frontend_redirect_url(success=False, message=message))
        return redirect(frontend_redirect_url(success=True))