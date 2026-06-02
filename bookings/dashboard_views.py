from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.scope import company_belongs_to_account
from config.models import Config
from config.views import (
    ACTIVE_PROJECTS_SCOPE,
    DASHBOARD_TAG_CONFIG_NAME,
    PROFIT_PROGRESS_SCOPE,
)
from planningwithyou.permissions import FeatureAccess, HasAccount

from .dashboard import (
    build_active_projects_for_company,
    build_dashboard_for_account,
    build_profit_progress_for_company,
)


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


def _company_id_from_dashboard_request(request):
    raw = request.query_params.get('company_id', '').strip()
    if raw:
        try:
            company_id = int(raw)
        except ValueError:
            return None, Response(
                {'company_id': ['Invalid company id.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        company_id = getattr(request.user, 'company_id', None)
    if company_id is None:
        return None, Response(
            {'company_id': ['Company is required.']},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not company_belongs_to_account(company_id, request.user.account_id):
        return None, Response(
            {'company_id': ['Company not found.']},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return company_id, None


def _configured_tag_for_scope(request, company_id: int, scope: str) -> str:
    row = Config.objects.filter(
        account_id=request.user.account_id,
        company_id=company_id,
        scope=scope,
        name=DASHBOARD_TAG_CONFIG_NAME,
    ).first()
    return row.value if row else ''


class DashboardProfitProgressView(APIView):
    """Total booking amount for statuses tagged with the configured profit tag."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'dashboard'

    def get(self, request):
        company_id, error = _company_id_from_dashboard_request(request)
        if error is not None:
            return error
        configured = _configured_tag_for_scope(
            request,
            company_id,
            PROFIT_PROGRESS_SCOPE,
        )
        return Response(
            build_profit_progress_for_company(
                request.user.account_id,
                company_id,
                configured,
            ),
        )


class DashboardActiveProjectsView(APIView):
    """Booking count for statuses tagged with the configured active-projects tag."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'dashboard'

    def get(self, request):
        company_id, error = _company_id_from_dashboard_request(request)
        if error is not None:
            return error
        configured = _configured_tag_for_scope(
            request,
            company_id,
            ACTIVE_PROJECTS_SCOPE,
        )
        return Response(
            build_active_projects_for_company(
                request.user.account_id,
                company_id,
                configured,
            ),
        )
