from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.permissions import FeatureAccess, HasAccount

from .models import Config

BOOKING_VIEW_SCOPE = 'account'
BOOKING_VIEW_NAME = 'booking_view'
BOOKING_VIEW_DEFAULT = 'board'
BOOKING_VIEW_CHOICES = frozenset({'board', 'cards', 'list'})

BOOKINGS_GROUP_NAME_SCOPE = 'account'
BOOKINGS_GROUP_NAME_NAME = 'bookings_group_name'
BOOKINGS_GROUP_NAME_MAX_LENGTH = 255


class BookingViewConfigView(APIView):
    feature_key = 'booking_settings_form_templates'
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
    feature_key = 'booking_settings_form_templates'
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
