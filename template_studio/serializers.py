from django.utils.text import slugify
from rest_framework import serializers

from template_studio.models import InvitationTemplate


def _active_templates():
    return InvitationTemplate.objects.filter(is_deleted=False)


def title_exists_for_company(
    company_id: int,
    title: str,
    *,
    exclude_pk: int | None = None,
) -> bool:
    qs = _active_templates().filter(
        company_id=company_id,
        is_marketplace=False,
        title__iexact=title.strip(),
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def unique_title_for_company(
    company_id: int,
    base_title: str,
    *,
    exclude_pk: int | None = None,
) -> str:
    """Return a title unique within the company (for duplicate / auto-naming)."""
    title = (base_title or '').strip() or 'Invitation'
    candidate = title
    n = 1
    while title_exists_for_company(company_id, candidate, exclude_pk=exclude_pk):
        n += 1
        suffix = f' ({n})'
        candidate = f'{title[: 255 - len(suffix)]}{suffix}'
    return candidate


def unique_slug_globally(title: str, *, exclude_pk: int | None = None) -> str:
    """Return a slug unique among all active invitation templates."""
    base = slugify(title)[:100] or 'invitation'
    slug = base
    n = 1
    while True:
        qs = _active_templates().filter(slug=slug)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return slug
        n += 1
        slug = f'{base}-{n}'[:120]


# Backward-compatible alias
unique_slug_for_company = unique_slug_globally


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

    def validate_title(self, value: str) -> str:
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Title is required.')

        company_id = self.context.get('company_id')
        if company_id is None and self.instance is not None:
            company_id = self.instance.company_id
        if company_id is None:
            return value

        if title_exists_for_company(
            company_id,
            value,
            exclude_pk=self.instance.pk if self.instance else None,
        ):
            raise serializers.ValidationError(
                'An invitation with this title already exists. Choose a different title.',
            )
        return value


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
