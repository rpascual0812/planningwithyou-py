from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import LEGAL_DOCUMENT_NAMES
from .models import SystemSetting


class SystemLegalPublicView(APIView):
    """Public read for platform legal HTML (no auth)."""

    permission_classes = [AllowAny]

    def get(self, request, name: str):
        if name not in LEGAL_DOCUMENT_NAMES:
            return Response({'detail': 'Not found.'}, status=404)
        row = SystemSetting.objects.filter(name=name).first()
        return Response(
            {
                'id': row.id if row else None,
                'name': name,
                'value': row.value if row else '',
            },
        )
