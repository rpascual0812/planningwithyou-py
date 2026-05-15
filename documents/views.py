import mimetypes

from django.utils import timezone
from rest_framework import parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from planningwithyou.permissions import HasAccount

from .models import Document, DocumentFolder
from .serializers import DocumentFolderSerializer, DocumentSerializer


class DocumentFolderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = DocumentFolderSerializer

    def get_queryset(self):
        aid = self.request.user.account_id
        qs = DocumentFolder.objects.filter(account_id=aid)
        deleted = self.request.query_params.get('deleted', '').lower()
        if deleted == 'true':
            qs = qs.filter(is_deleted=True)
        else:
            qs = qs.filter(is_deleted=False)
        return qs

    def perform_create(self, serializer):
        serializer.save(account_id=self.request.user.account_id)

    def perform_destroy(self, instance):
        now = timezone.now()
        instance.is_deleted = True
        instance.deleted_at = now
        instance.save(update_fields=['is_deleted', 'deleted_at'])
        instance.documents.filter(is_deleted=False).update(
            is_deleted=True, deleted_at=now,
        )

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        folder = DocumentFolder.objects.filter(
            pk=pk,
            is_deleted=True,
            account_id=request.user.account_id,
        ).first()
        if folder is None:
            return Response(
                {'detail': 'Not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        folder.is_deleted = False
        folder.deleted_at = None
        folder.save(update_fields=['is_deleted', 'deleted_at'])
        folder.documents.filter(is_deleted=True).update(
            is_deleted=False, deleted_at=None,
        )
        return Response(self.get_serializer(folder).data)


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = DocumentSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        aid = self.request.user.account_id
        qs = Document.objects.select_related('folder').filter(account_id=aid)
        deleted = self.request.query_params.get('deleted', '').lower()
        if deleted == 'true':
            qs = qs.filter(is_deleted=True)
        else:
            qs = qs.filter(is_deleted=False)

        folder_id = self.request.query_params.get('folder')
        if folder_id:
            qs = qs.filter(folder_id=folder_id)

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(original_name__icontains=search)
        return qs

    def create(self, request, *args, **kwargs):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response(
                {'file': ['No file was submitted.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mime, _ = mimetypes.guess_type(uploaded.name)
        aid = request.user.account_id
        folder = None
        if folder_id:
            folder = DocumentFolder.objects.filter(
                pk=folder_id,
                is_deleted=False,
                account_id=aid,
            ).first()

        doc = Document.objects.create(
            file=uploaded,
            original_name=uploaded.name,
            mime_type=mime or uploaded.content_type or '',
            size=uploaded.size,
            folder=folder,
            uploaded_by=request.user,
            account_id=aid,
        )
        serializer = self.get_serializer(doc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at'])

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        doc = Document.objects.filter(
            pk=pk,
            is_deleted=True,
            account_id=request.user.account_id,
        ).first()
        if doc is None:
            return Response(
                {'detail': 'Not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        doc.is_deleted = False
        doc.deleted_at = None
        doc.save(update_fields=['is_deleted', 'deleted_at'])
        return Response(self.get_serializer(doc).data)

    @action(detail=False, methods=['post'], url_path='empty-trash')
    def empty_trash(self, request):
        aid = request.user.account_id
        count, _ = Document.objects.filter(is_deleted=True, account_id=aid).delete()
        folder_count, _ = DocumentFolder.objects.filter(is_deleted=True, account_id=aid).delete()
        return Response({'deleted_documents': count, 'deleted_folders': folder_count})

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        doc = self.get_object()
        folder_id = request.data.get('folder')
        if folder_id is None:
            return Response(
                {'folder': ['Folder ID is required.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        folder = DocumentFolder.objects.filter(
            pk=folder_id,
            is_deleted=False,
            account_id=request.user.account_id,
        ).first()
        if folder is None:
            return Response(
                {'folder': ['Folder not found.']},
                status=status.HTTP_404_NOT_FOUND,
            )
        doc.folder = folder
        doc.save(update_fields=['folder'])
        return Response(self.get_serializer(doc).data)

    @action(detail=True, methods=['post'])
    def rename(self, request, pk=None):
        doc = self.get_object()
        name = request.data.get('name', '').strip()
        if not name:
            return Response(
                {'name': ['Name is required.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        doc.original_name = name
        doc.save(update_fields=['original_name'])
        return Response(self.get_serializer(doc).data)
