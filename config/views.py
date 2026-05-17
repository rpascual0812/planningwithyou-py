from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.permissions import HasAccount

from .models import Config

BOOKING_VIEW_SCOPE = 'account'
BOOKING_VIEW_NAME = 'booking_view'
BOOKING_VIEW_DEFAULT = 'board'
BOOKING_VIEW_CHOICES = frozenset({'board', 'cards', 'list'})


class BookingViewConfigView(APIView):
    permission_classes = [IsAuthenticated, HasAccount]

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
