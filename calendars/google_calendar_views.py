from django.http import HttpResponse
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .google_calendar_service import (
    GoogleCalendarConfigError,
    GoogleCalendarOAuthError,
    build_authorization_url,
    complete_oauth_callback,
    disconnect_integration,
    find_integration_for_webhook,
    frontend_redirect_url,
    get_integration_for_user,
    google_oauth_configured,
    integration_status_payload,
    run_full_google_sync,
    schedule_inbound_sync,
    update_sync_mode,
)
from .models import GoogleCalendarIntegration


class GoogleCalendarIntegrationView(APIView):
    """Connect, configure, and disconnect Google Calendar for the active company."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'calendar_settings'

    def get(self, request):
        integration = get_integration_for_user(request.user)
        data = integration_status_payload(integration)
        data['authorization_url'] = None
        return Response(data)

    def put(self, request):
        """Start OAuth — returns authorization_url to redirect the user."""
        if not google_oauth_configured():
            return Response(
                {
                    'detail': 'Google Calendar OAuth is not configured on the server.',
                    'configured': False,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        integration = get_integration_for_user(request.user)
        if integration and (integration.refresh_token_encrypted or '').strip():
            return Response(integration_status_payload(integration))

        sync_mode = request.data.get('sync_mode')
        two_way = request.data.get('two_way_sync')
        if two_way is True:
            sync_mode = GoogleCalendarIntegration.SyncMode.TWO_WAY
        elif two_way is False:
            sync_mode = GoogleCalendarIntegration.SyncMode.ONE_WAY
        if sync_mode not in GoogleCalendarIntegration.SyncMode.values:
            sync_mode = GoogleCalendarIntegration.SyncMode.ONE_WAY

        try:
            auth_url = build_authorization_url(
                account_id=request.user.account_id,
                company_id=request.user.company_id,
                user_id=request.user.pk,
                sync_mode=sync_mode,
            )
        except GoogleCalendarConfigError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        payload = integration_status_payload(integration)
        payload['authorization_url'] = auth_url
        return Response(payload)

    def patch(self, request):
        integration = get_integration_for_user(request.user)
        if integration is None or not (integration.refresh_token_encrypted or '').strip():
            return Response(
                {'detail': 'Google Calendar is not connected.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if 'two_way_sync' not in request.data:
            return Response(
                {'detail': 'Provide two_way_sync (boolean).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        two_way = bool(request.data.get('two_way_sync'))
        try:
            update_sync_mode(integration, two_way_sync=two_way)
        except GoogleCalendarOAuthError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(integration_status_payload(integration))

    def delete(self, request):
        integration = get_integration_for_user(request.user)
        if integration is None:
            return Response(integration_status_payload(None))
        try:
            disconnect_integration(integration)
        except Exception:
            return Response(
                {'detail': 'Failed to disconnect Google Calendar.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(integration_status_payload(None))


class GoogleCalendarSyncView(APIView):
    """POST — push all app events to Google and pull changes when two-way is on."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'calendar_settings'

    def post(self, request):
        integration = get_integration_for_user(request.user)
        if integration is None or not (integration.refresh_token_encrypted or '').strip():
            return Response(
                {'detail': 'Google Calendar is not connected.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            run_full_google_sync(integration)
        except GoogleCalendarOAuthError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response(
                {'detail': 'Google Calendar sync failed.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(integration_status_payload(integration))


class GoogleCalendarOAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        error = request.query_params.get('error')
        if error:
            return redirect(
                frontend_redirect_url(success=False, message=error),
            )
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        if not code or not state:
            return redirect(
                frontend_redirect_url(
                    success=False,
                    message='missing_code',
                ),
            )
        try:
            complete_oauth_callback(code=code, state=state)
        except (GoogleCalendarOAuthError, GoogleCalendarConfigError) as exc:
            return redirect(frontend_redirect_url(success=False, message=str(exc)))
        except Exception:
            return redirect(
                frontend_redirect_url(success=False, message='oauth_failed'),
            )
        return redirect(frontend_redirect_url(success=True))


class GoogleCalendarWebhookView(APIView):
    """Google Calendar push notifications (two-way sync)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        channel_id = request.headers.get('X-Goog-Channel-Id', '')
        channel_token = request.headers.get('X-Goog-Channel-Token', '')
        resource_state = request.headers.get('X-Goog-Resource-State', '')

        integration = find_integration_for_webhook(channel_id, channel_token)
        if integration is None:
            return HttpResponse(status=404)

        if resource_state in {'sync', 'exists', 'update'}:
            schedule_inbound_sync(integration.pk)
            try:
                from .tasks import sync_google_calendar_inbound_task

                sync_google_calendar_inbound_task.delay(integration.pk)
            except Exception:
                pass

        return HttpResponse(status=200)
