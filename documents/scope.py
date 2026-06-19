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


def file_manager_documents_for_user(user):
    """Documents visible in File Manager (excludes quotation-only files)."""
    return documents_for_user(user).filter(quotation__isnull=True)


def quotation_documents_for_user(user, quotation_id: int):
    return documents_for_user(user).filter(quotation_id=quotation_id)
