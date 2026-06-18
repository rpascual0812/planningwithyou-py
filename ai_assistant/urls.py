from django.urls import path

from .views import (
    AiAssistantStatusView,
    QuotationAiDraftEmailView,
    QuotationAiSummarizeView,
)

urlpatterns = [
    path('ai/assistant/status/', AiAssistantStatusView.as_view(), name='ai-assistant-status'),
    path(
        'ai/quotations/<int:quotation_id>/summarize/',
        QuotationAiSummarizeView.as_view(),
        name='ai-quotation-summarize',
    ),
    path(
        'ai/quotations/<int:quotation_id>/draft-email/',
        QuotationAiDraftEmailView.as_view(),
        name='ai-quotation-draft-email',
    ),
]
