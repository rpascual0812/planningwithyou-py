from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
        from users.company_access import can_change_company

        user_company_id = getattr(request.user, 'company_id', None)
        limit_to_company_id = None
        if not can_change_company(request.user):
            limit_to_company_id = user_company_id
        return Response(
            build_dashboard_for_account(
                request.user.account_id,
                user_company_id=user_company_id,
                limit_to_company_id=limit_to_company_id,
            ),
        )


def _company_id_from_dashboard_request(request):
    from users.company_access import effective_company_id

    raw = request.query_params.get('company_id', '').strip()
    requested = int(raw) if raw.isdigit() else None
    company_id = effective_company_id(request.user, requested)
    if company_id is None:
        return None, Response(
            {'company_id': ['Company is required.']},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return company_id, None


def _configured_tag_for_scope(request, company_id: int, scope: str) -> tuple[str, bool]:
    row = Config.objects.filter(
        account_id=request.user.account_id,
        company_id=company_id,
        scope=scope,
        name=DASHBOARD_TAG_CONFIG_NAME,
    ).first()
    return (row.value if row else '', row is not None)


class DashboardProfitProgressView(APIView):
    """Total booking amount for statuses tagged with the configured profit tag."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'dashboard'

    def get(self, request):
        company_id, error = _company_id_from_dashboard_request(request)
        if error is not None:
            return error
        configured, has_saved_config = _configured_tag_for_scope(
            request,
            company_id,
            PROFIT_PROGRESS_SCOPE,
        )
        return Response(
            build_profit_progress_for_company(
                request.user.account_id,
                company_id,
                configured,
                has_saved_config=has_saved_config,
            ),
        )


class DashboardActiveProjectsView(APIView):
    """Quotation count for statuses tagged with the configured active-projects tag."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'dashboard'

    def get(self, request):
        company_id, error = _company_id_from_dashboard_request(request)
        if error is not None:
            return error
        configured, has_saved_config = _configured_tag_for_scope(
            request,
            company_id,
            ACTIVE_PROJECTS_SCOPE,
        )
        return Response(
            build_active_projects_for_company(
                request.user.account_id,
                company_id,
                configured,
                has_saved_config=has_saved_config,
            ),
        )
