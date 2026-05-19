"""Query helpers scoped to the authenticated user's company."""

from __future__ import annotations

from documents.models import Document, DocumentFolder


def document_folders_for_user(user):
    return DocumentFolder.objects.filter(
        account_id=user.account_id,
        company_id=user.company_id,
    )


def documents_for_user(user):
    return Document.objects.filter(
        account_id=user.account_id,
        company_id=user.company_id,
    )
