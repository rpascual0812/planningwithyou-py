from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.permissions import FeatureAccess

from .impersonation import end_impersonation, start_impersonation
from .jwt import is_impersonation_request


class ImpersonateStartView(APIView):
    """Issue impersonation JWTs for a target tenant user."""

    feature_key = 'platform_admin'
    permission_classes = [IsAuthenticated, FeatureAccess]

    def post(self, request):
        raw_user_id = request.data.get('user_id')
        try:
            target_user_id = int(raw_user_id)
        except (TypeError, ValueError):
            return Response(
                {'user_id': ['A valid user id is required.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = start_impersonation(
            admin_user=request.user,
            target_user_id=target_user_id,
            request=request,
        )
        return Response(payload)


class ImpersonateEndView(APIView):
    """End the current impersonation session and blacklist its refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_impersonation_request(request):
            return Response(
                {'detail': 'Not in an impersonation session.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh_token = request.data.get('refresh', '')
        if not isinstance(refresh_token, str):
            refresh_token = ''
        end_impersonation(request=request, refresh_token=refresh_token)
        return Response({'detail': 'Impersonation ended.'})
