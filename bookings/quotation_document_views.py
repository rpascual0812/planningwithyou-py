"""Quotation-scoped documents (not visible in File Manager)."""

from __future__ import annotations

import mimetypes
import os

from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from rest_framework import parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.models import Document
from documents.scope import file_manager_documents_for_user, quotation_documents_for_user
from documents.serializers import DocumentSerializer
from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .history import (
    record_quotation_document_attached,
    record_quotation_document_removed,
    record_quotation_document_uploaded,
)
from .models import Quotation
from .scope import assert_booking_editable, bookings_for_user


def _quotation_for_user(user, quotation_id: int) -> Quotation:
    return get_object_or_404(bookings_for_user(user), pk=quotation_id)


def _serialize_documents(docs, request):
    serializer = DocumentSerializer(docs, many=True, context={'request': request})
    return serializer.data


def copy_file_manager_document_for_quotation(
    *,
    source: Document,
    quotation: Quotation,
    actor,
) -> Document:
    source.file.open('rb')
    try:
        content = source.file.read()
    finally:
        source.file.close()

    doc = Document(
        account_id=quotation.account_id,
        company_id=quotation.company_id,
        quotation=quotation,
        original_name=source.original_name,
        mime_type=source.mime_type,
        size=source.size,
        folder=None,
        uploaded_by=actor,
    )
    filename = os.path.basename(source.file.name) or source.original_name
    doc.file.save(filename, ContentFile(content), save=False)
    doc.save()
    return doc


class QuotationDocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'quotations'
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get(self, request, quotation_id: int):
        quotation = _quotation_for_user(request.user, quotation_id)
        docs = quotation_documents_for_user(request.user, quotation.pk).filter(
            is_deleted=False,
        ).order_by('-created_at')
        return Response(_serialize_documents(docs, request))

    def post(self, request, quotation_id: int):
        quotation = _quotation_for_user(request.user, quotation_id)
        assert_booking_editable(quotation, request.user)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response(
                {'file': ['No file was submitted.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mime, _ = mimetypes.guess_type(uploaded.name)
        doc = Document.objects.create(
            file=uploaded,
            original_name=uploaded.name,
            mime_type=mime or uploaded.content_type or '',
            size=uploaded.size,
            folder=None,
            quotation=quotation,
            uploaded_by=request.user,
            account_id=quotation.account_id,
            company_id=quotation.company_id,
        )
        record_quotation_document_uploaded(quotation, doc, actor=request.user)
        return Response(
            DocumentSerializer(doc, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class QuotationDocumentAttachView(APIView):
    """Copy an existing File Manager document onto this quotation."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'quotations'

    def post(self, request, quotation_id: int):
        quotation = _quotation_for_user(request.user, quotation_id)
        assert_booking_editable(quotation, request.user)

        source_id = request.data.get('document_id')
        if source_id in (None, ''):
            return Response(
                {'document_id': ['Document ID is required.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        source = file_manager_documents_for_user(request.user).filter(
            pk=source_id,
            is_deleted=False,
        ).first()
        if source is None:
            return Response(
                {'document_id': ['Document not found in File Manager.']},
                status=status.HTTP_404_NOT_FOUND,
            )

        doc = copy_file_manager_document_for_quotation(
            source=source,
            quotation=quotation,
            actor=request.user,
        )
        record_quotation_document_attached(
            quotation,
            doc,
            source_document=source,
            actor=request.user,
        )
        return Response(
            DocumentSerializer(doc, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class QuotationDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'quotations'

    def delete(self, request, quotation_id: int, document_id: int):
        quotation = _quotation_for_user(request.user, quotation_id)
        assert_booking_editable(quotation, request.user)

        doc = quotation_documents_for_user(request.user, quotation.pk).filter(
            pk=document_id,
            is_deleted=False,
        ).first()
        if doc is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        name = doc.original_name
        doc_id = doc.pk
        doc.file.delete(save=False)
        doc.delete()
        record_quotation_document_removed(
            quotation,
            document_id=doc_id,
            document_name=name,
            actor=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
