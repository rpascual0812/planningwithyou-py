import mimetypes

from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework import parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planningwithyou.file_storage import read_template_asset_file, template_asset_public_url
from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .models import InvitationTemplate, TemplateAsset
from .scope import templates_for_user
from .serializers import (
    InvitationTemplateSerializer,
    MarketplaceTemplateSerializer,
    PublicInvitationSerializer,
    unique_slug_for_company,
)


class InvitationTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'template_studio'
    serializer_class = InvitationTemplateSerializer

    def get_queryset(self):
        return templates_for_user(self.request.user).filter(is_deleted=False)

    def perform_create(self, serializer):
        user = self.request.user
        title = serializer.validated_data['title']
        slug = unique_slug_for_company(user.company_id, title)
        doc = serializer.validated_data.get('document') or {}
        if isinstance(doc, dict):
            meta = doc.setdefault('meta', {})
            meta['title'] = title
            meta['name'] = title
            meta['updatedAt'] = timezone.now().isoformat()
        serializer.save(
            account_id=user.account_id,
            company_id=user.company_id,
            slug=slug,
            created_by=user,
        )

    def perform_update(self, serializer):
        instance = serializer.instance
        title = serializer.validated_data.get('title', instance.title)
        doc = serializer.validated_data.get('document')
        if doc is not None and isinstance(doc, dict):
            meta = doc.setdefault('meta', {})
            meta['title'] = title
            meta['name'] = title
            meta['updatedAt'] = timezone.now().isoformat()
        # Keep slug stable so republishing updates the same public URL.
        serializer.save(slug=instance.slug)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.is_published = False
        instance.save(update_fields=['is_deleted', 'deleted_at', 'is_published', 'updated_at'])

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        tpl = self.get_object()
        if request.data:
            serializer = self.get_serializer(tpl, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            tpl.refresh_from_db()
        tpl.is_published = True
        if not tpl.published_at:
            tpl.published_at = timezone.now()
        tpl.save(update_fields=['is_published', 'published_at', 'updated_at'])
        return Response(InvitationTemplateSerializer(tpl).data)

    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        tpl = self.get_object()
        tpl.is_published = False
        tpl.save(update_fields=['is_published', 'updated_at'])
        return Response(InvitationTemplateSerializer(tpl).data)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        src = self.get_object()
        title = f'{src.title} copy'
        slug = unique_slug_for_company(src.company_id, title)
        doc = src.document
        if isinstance(doc, dict):
            doc = {**doc, 'meta': {**doc.get('meta', {}), 'title': title, 'name': title}}
        copy = InvitationTemplate.objects.create(
            account_id=src.account_id,
            company_id=src.company_id,
            title=title,
            slug=slug,
            category=src.category,
            description=src.description,
            document=doc,
            created_by=request.user,
        )
        return Response(
            InvitationTemplateSerializer(copy).data,
            status=status.HTTP_201_CREATED,
        )


class MarketplaceTemplateListView(APIView):
    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'template_studio'

    def get(self, request):
        qs = InvitationTemplate.objects.filter(
            is_marketplace=True,
            is_deleted=False,
        ).order_by('category', 'title')
        category = request.query_params.get('category', '').strip()
        if category:
            qs = qs.filter(category=category)
        return Response(MarketplaceTemplateSerializer(qs, many=True).data)


TEMPLATE_IMAGE_MAX_BYTES = 10 * 1024 * 1024
TEMPLATE_IMAGE_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
}


class TemplateAssetUploadView(APIView):
    """Upload an image for template studio (stored in S3/local default storage)."""

    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    feature_key = 'template_studio'
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response(
                {'file': ['No file was submitted.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if uploaded.size > TEMPLATE_IMAGE_MAX_BYTES:
            return Response(
                {'file': ['Image must be 10 MB or smaller.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mime = (uploaded.content_type or '').split(';')[0].strip().lower()
        if not mime:
            mime, _ = mimetypes.guess_type(uploaded.name)
            mime = (mime or '').lower()
        if mime not in TEMPLATE_IMAGE_TYPES:
            return Response(
                {'file': ['Allowed types: JPEG, PNG, WebP, GIF.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        asset = TemplateAsset.objects.create(
            file=uploaded,
            original_name=uploaded.name,
            mime_type=mime,
            size=uploaded.size,
            account_id=request.user.account_id,
            company_id=request.user.company_id,
            created_by=request.user,
        )
        url = template_asset_public_url(asset.uuid, request=request)
        return Response(
            {
                'id': asset.pk,
                'uuid': str(asset.uuid),
                'url': url,
                'original_name': asset.original_name,
                'mime_type': asset.mime_type,
                'size': asset.size,
            },
            status=status.HTTP_201_CREATED,
        )


class PublicTemplateAssetView(APIView):
    """Serve a template asset by UUID (used in saved/published invitation JSON)."""

    permission_classes = [AllowAny]

    def get(self, request, asset_uuid):
        try:
            data, filename, content_type = read_template_asset_file(asset_uuid)
        except FileNotFoundError as exc:
            raise Http404(str(exc)) from exc
        except ValueError as exc:
            return HttpResponse(str(exc), status=413)

        response = HttpResponse(data, content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{filename.replace(chr(34), "")}"'
        response['Content-Length'] = len(data)
        response['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response


class PublicInvitationView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        tpl = (
            InvitationTemplate.objects.filter(
                slug=slug,
                is_published=True,
                is_deleted=False,
                is_marketplace=False,
            )
            .select_related('company')
            .first()
        )
        if tpl is None:
            return Response({'detail': 'Invitation not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(PublicInvitationSerializer(tpl).data)
