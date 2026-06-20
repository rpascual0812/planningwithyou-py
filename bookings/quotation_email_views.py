"""Quotation-scoped email logs."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from emails.scope import email_logs_for_user
from emails.serializers import EmailLogSerializer
from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .scope import bookings_for_user


def _quotation_for_user(user, quotation_id: int):
    return get_object_or_404(bookings_for_user(user), pk=quotation_id)


class QuotationEmailLogListView(APIView):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'emails'

    def get(self, request, quotation_id: int):
        quotation = _quotation_for_user(request.user, quotation_id)
        logs = (
            email_logs_for_user(request.user)
            .filter(quotation_id=quotation.pk)
            .order_by('-created_at')
        )
        serializer = EmailLogSerializer(logs, many=True, context={'request': request})
        return Response(serializer.data)
