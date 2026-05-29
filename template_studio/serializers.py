from django.utils.text import slugify
from rest_framework import serializers

from template_studio.models import InvitationTemplate


def unique_slug_for_company(company_id: int, title: str, exclude_pk: int | None = None) -> str:
    base = slugify(title)[:100] or 'invitation'
    slug = base
    n = 1
    while True:
        qs = InvitationTemplate.objects.filter(
            company_id=company_id,
            slug=slug,
            is_deleted=False,
        )
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return slug
        n += 1
        slug = f'{base}-{n}'[:120]


class InvitationTemplateSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    title = serializers.CharField(max_length=255, required=True, allow_blank=False)

    class Meta:
        model = InvitationTemplate
        fields = [
            'id',
            'title',
            'slug',
            'category',
            'description',
            'document',
            'is_published',
            'published_at',
            'is_marketplace',
            'marketplace_preview_url',
            'company_id',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'slug',
            'is_published',
            'published_at',
            'is_marketplace',
            'marketplace_preview_url',
            'company_id',
            'created_by_name',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'document': {'required': False},
            'description': {'required': False, 'allow_blank': True},
            'category': {'required': False},
        }

    def get_created_by_name(self, obj: InvitationTemplate) -> str:
        user = obj.created_by
        if not user:
            return ''
        full = f'{user.first_name or ""} {user.last_name or ""}'.strip()
        return full or user.username or user.email or ''

    def validate_document(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Document must be a JSON object.')
        if value.get('schemaVersion') != 1:
            raise serializers.ValidationError('Unsupported schema version.')
        return value

    def validate(self, attrs):
        title = attrs.get('title') or (self.instance.title if self.instance else None)
        if not title or not str(title).strip():
            raise serializers.ValidationError({'title': 'Title is required.'})
        return attrs


class PublicInvitationSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = InvitationTemplate
        fields = [
            'title',
            'slug',
            'category',
            'description',
            'document',
            'company_name',
            'published_at',
        ]


class MarketplaceTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvitationTemplate
        fields = [
            'id',
            'title',
            'slug',
            'category',
            'description',
            'marketplace_preview_url',
            'document',
        ]
