from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.permissions import HasAccount

from .dashboard import build_dashboard_for_account


class DashboardSummaryView(APIView):
    """Per-company booking, payment, calendar, and payout metrics."""

    permission_classes = [IsAuthenticated, HasAccount]

    def get(self, request):
        return Response(
            build_dashboard_for_account(
                request.user.account_id,
                user_company_id=getattr(request.user, 'company_id', None),
            ),
        )
