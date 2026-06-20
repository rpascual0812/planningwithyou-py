from django.conf import settings
from rest_framework import permissions as drf_permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from bookings.scope import assert_booking_editable, bookings_for_user
from planningwithyou.permissions import HasAccount, HasCompany

from .access import (
    ai_assistant_available_for_user,
    ai_assistant_configured,
    ai_assistant_plans,
)
from .client import AiAssistantError, AiAssistantNotConfigured
from .models import AiRequestLog
from .permissions import AI_ASSISTANT_PERMISSIONS
from .quotation_context import build_quotation_ai_context
from .services import draft_quotation_email, summarize_quotation


def _get_owned_quotation(request, quotation_id: int):
    quotation = (
        bookings_for_user(request.user)
        .filter(pk=quotation_id, company_id=request.user.company_id)
        .first()
    )
    if quotation is None:
        return None
    assert_booking_editable(quotation, request.user)
    return quotation


def _log_request(
    *,
    request,
    quotation,
    action: str,
    usage: dict,
) -> None:
    AiRequestLog.objects.create(
        account_id=request.user.account_id,
        company_id=request.user.company_id,
        user=request.user,
        quotation=quotation,
        action=action,
        model=getattr(settings, 'AI_ASSISTANT_MODEL', 'gpt-4o-mini'),
        prompt_tokens=usage.get('prompt_tokens'),
        completion_tokens=usage.get('completion_tokens'),
    )


class AiAssistantStatusView(APIView):
    permission_classes = [
        drf_permissions.IsAuthenticated,
        HasAccount,
        HasCompany,
    ]

    def get(self, request):
        from users.roles import has_feature_write

        configured = ai_assistant_configured()
        has_permission = has_feature_write(request.user, 'ai_assistant')
        plan_eligible = ai_assistant_available_for_user(request.user)
        available = configured and plan_eligible and has_permission
        return Response(
            {
                'configured': configured,
                'plan_eligible': plan_eligible,
                'available': available,
                'plans': sorted(ai_assistant_plans()),
            },
        )


class QuotationAiSummarizeView(APIView):
    permission_classes = AI_ASSISTANT_PERMISSIONS

    def post(self, request, quotation_id: int):
        quotation = _get_owned_quotation(request, quotation_id)
        if quotation is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        prompt = (request.data.get('prompt') or '').strip()
        try:
            context = build_quotation_ai_context(quotation)
            result, usage = summarize_quotation(context, user_prompt=prompt)
        except AiAssistantNotConfigured:
            return Response(
                {'detail': 'AI assistant is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (AiAssistantError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        _log_request(
            request=request,
            quotation=quotation,
            action=AiRequestLog.Action.SUMMARIZE,
            usage=usage,
        )
        return Response(result)


class QuotationAiDraftEmailView(APIView):
    permission_classes = AI_ASSISTANT_PERMISSIONS

    def post(self, request, quotation_id: int):
        quotation = _get_owned_quotation(request, quotation_id)
        if quotation is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        prompt = (request.data.get('prompt') or '').strip()
        try:
            context = build_quotation_ai_context(quotation)
            result, usage = draft_quotation_email(context, user_prompt=prompt)
        except AiAssistantNotConfigured:
            return Response(
                {'detail': 'AI assistant is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (AiAssistantError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        _log_request(
            request=request,
            quotation=quotation,
            action=AiRequestLog.Action.DRAFT_EMAIL,
            usage=usage,
        )
        return Response(result)
