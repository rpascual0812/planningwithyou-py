import mimetypes

from rest_framework import parsers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Document
from .serializers import DocumentSerializer


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    ordering = ['-created_at']

    def get_queryset(self):
        qs = Document.objects.all()
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

        doc = Document.objects.create(
            file=uploaded,
            original_name=uploaded.name,
            mime_type=mime or uploaded.content_type or '',
            size=uploaded.size,
            uploaded_by=request.user,
        )
        serializer = self.get_serializer(doc)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
