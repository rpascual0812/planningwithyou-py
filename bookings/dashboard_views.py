from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.models import Config
from config.views import PROFIT_PROGRESS_SCOPE, PROFIT_PROGRESS_TAG_NAME
from planningwithyou.permissions import FeatureAccess, HasAccount

from .dashboard import build_dashboard_for_account, build_profit_progress_for_account


class DashboardSummaryView(APIView):
    """Per-company booking, payment, calendar, and payout metrics."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'dashboard'

    def get(self, request):
        return Response(
            build_dashboard_for_account(
                request.user.account_id,
                user_company_id=getattr(request.user, 'company_id', None),
            ),
        )


class DashboardProfitProgressView(APIView):
    """Total booking amount for statuses tagged with the configured profit tag."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'dashboard'

    def get(self, request):
        row = Config.objects.filter(
            account_id=request.user.account_id,
            scope=PROFIT_PROGRESS_SCOPE,
            name=PROFIT_PROGRESS_TAG_NAME,
        ).first()
        configured = row.value if row else ''
        return Response(
            build_profit_progress_for_account(
                request.user.account_id,
                configured,
            ),
        )
