from django.http import HttpResponse
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
            return redirect(frontend_redirect_url(success=False, message=error))
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        if not code or not state:
            return redirect(
                frontend_redirect_url(success=False, message='missing_code'),
            )
        try:
            complete_oauth_callback(code=code, state=state)
        except (GmailOAuthError, GmailConfigError) as exc:
            return redirect(frontend_redirect_url(success=False, message=str(exc)))
        except Exception:
            return redirect(frontend_redirect_url(success=False, message='oauth_failed'))
        return redirect(frontend_redirect_url(success=True))
