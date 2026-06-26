from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.permissions import FeatureAccess, HasAccount

from .models import Config

BOOKING_VIEW_SCOPE = 'account'
BOOKING_VIEW_NAME = 'quotation_view'
BOOKING_VIEW_DEFAULT = 'board'
BOOKING_VIEW_CHOICES = frozenset({'board', 'cards', 'list'})

BOOKINGS_GROUP_NAME_SCOPE = 'account'
BOOKINGS_GROUP_NAME_NAME = 'quotations_group_name'
BOOKINGS_GROUP_NAME_MAX_LENGTH = 255

PROFIT_PROGRESS_SCOPE = 'profit_progress'
ACTIVE_PROJECTS_SCOPE = 'active_projects'
DASHBOARD_TAG_CONFIG_NAME = 'tag'


def _dashboard_metric_company_id(request):
    from users.company_access import effective_company_id

    raw = request.query_params.get('company_id') or request.data.get('company_id')
    requested = None
    if raw is not None and str(raw).strip() != '':
        try:
            requested = int(raw)
        except (TypeError, ValueError):
            return None, Response(
                {'company_id': ['Invalid company id.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
    company_id = effective_company_id(request.user, requested)
    if company_id is None:
        return None, Response(
            {'company_id': ['Company is required.']},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return company_id, None


class BookingViewConfigView(APIView):
    feature_key = 'quotation_settings_statuses'
    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]

    def get(self, request):
        row = Config.objects.filter(
            account_id=request.user.account_id,
            scope=BOOKING_VIEW_SCOPE,
            name=BOOKING_VIEW_NAME,
        ).first()
        value = row.value if row else BOOKING_VIEW_DEFAULT
        if value not in BOOKING_VIEW_CHOICES:
            value = BOOKING_VIEW_DEFAULT
        return Response({
            'scope': BOOKING_VIEW_SCOPE,
            'name': BOOKING_VIEW_NAME,
            'value': value,
        })

    def put(self, request):
        value = (request.data.get('value') or '').strip()
        if value not in BOOKING_VIEW_CHOICES:
            return Response(
                {'detail': 'value must be one of: board, cards, list.'},
                status=400,
            )
        Config.objects.update_or_create(
            account_id=request.user.account_id,
            scope=BOOKING_VIEW_SCOPE,
            name=BOOKING_VIEW_NAME,
            defaults={'value': value},
        )
        return Response({
            'scope': BOOKING_VIEW_SCOPE,
            'name': BOOKING_VIEW_NAME,
            'value': value,
        })


class BookingsGroupNameConfigView(APIView):
    feature_key = 'quotation_settings_statuses'
    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]

    def get(self, request):
        row = Config.objects.filter(
            account_id=request.user.account_id,
            scope=BOOKINGS_GROUP_NAME_SCOPE,
            name=BOOKINGS_GROUP_NAME_NAME,
        ).first()
        value = row.value if row else ''
        return Response({
            'scope': BOOKINGS_GROUP_NAME_SCOPE,
            'name': BOOKINGS_GROUP_NAME_NAME,
            'value': value,
        })

    def put(self, request):
        raw = request.data.get('value')
        value = '' if raw is None else str(raw).strip()
        if len(value) > BOOKINGS_GROUP_NAME_MAX_LENGTH:
            return Response(
                {
                    'detail': (
                        f'value must be at most {BOOKINGS_GROUP_NAME_MAX_LENGTH} '
                        'characters.'
                    ),
                },
                status=400,
            )
        Config.objects.update_or_create(
            account_id=request.user.account_id,
            scope=BOOKINGS_GROUP_NAME_SCOPE,
            name=BOOKINGS_GROUP_NAME_NAME,
            defaults={'value': value},
        )
        return Response({
            'scope': BOOKINGS_GROUP_NAME_SCOPE,
            'name': BOOKINGS_GROUP_NAME_NAME,
            'value': value,
        })


class _DashboardTagConfigView(APIView):
    """Base API for per-company dashboard tag config (profit progress, active projects)."""

    feature_key = 'dashboard'
    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    config_scope: str = ''

    def get(self, request):
        company_id, error = _dashboard_metric_company_id(request)
        if error is not None:
            return error
        row = Config.objects.filter(
            account_id=request.user.account_id,
            company_id=company_id,
            scope=self.config_scope,
            name=DASHBOARD_TAG_CONFIG_NAME,
        ).first()
        value = row.value if row else ''
        return Response({
            'scope': self.config_scope,
            'name': DASHBOARD_TAG_CONFIG_NAME,
            'company_id': company_id,
            'value': value,
        })

    def put(self, request):
        company_id, error = _dashboard_metric_company_id(request)
        if error is not None:
            return error
        raw = request.data.get('value')
        value = '' if raw is None else str(raw).strip()
        if value:
            from bookings.dashboard import parse_configured_tag_ids
            from bookings.models import Tag

            tag_ids = parse_configured_tag_ids(value)
            if not tag_ids:
                return Response(
                    {'detail': 'Invalid tag.'},
                    status=400,
                )
            for tag_id in tag_ids:
                if not Tag.objects.filter(
                    pk=tag_id,
                    account_id=request.user.account_id,
                    company_id=company_id,
                ).exists():
                    return Response(
                        {'detail': 'Invalid tag.'},
                        status=400,
                    )
            value = ','.join(str(tag_id) for tag_id in tag_ids)
        Config.objects.update_or_create(
            account_id=request.user.account_id,
            company_id=company_id,
            scope=self.config_scope,
            name=DASHBOARD_TAG_CONFIG_NAME,
            defaults={'value': value},
        )
        return Response({
            'scope': self.config_scope,
            'name': DASHBOARD_TAG_CONFIG_NAME,
            'company_id': company_id,
            'value': value,
        })


class ProfitProgressTagConfigView(_DashboardTagConfigView):
    config_scope = PROFIT_PROGRESS_SCOPE


class ActiveProjectsTagConfigView(_DashboardTagConfigView):
    config_scope = ACTIVE_PROJECTS_SCOPE
