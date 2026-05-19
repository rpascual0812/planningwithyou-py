from django.db import transaction
from rest_framework import serializers

from planningwithyou.file_storage import company_logo_public_url

from .logo_image import delete_company_logo, save_company_logo
from .models import Company


class CompanySerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    logo_upload = serializers.FileField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Company
        fields = [
            'id',
            'name',
            'timezone',
            'website',
            'is_active',
            'is_main',
            'logo',
            'logo_upload',
            'logo_url',
            'sort_order',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'logo', 'logo_url']

    def get_logo_url(self, obj):
        return company_logo_public_url(
            obj.logo,
            obj.pk,
            request=self.context.get('request'),
        )

    def validate_name(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Name is required.')
        return value

    def validate_website(self, value):
        return (value or '').strip()

    def validate_timezone(self, value):
        return (value or '').strip()

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            payload = data.copy()
        else:
            payload = dict(data)
        logo_val = payload.get('logo')
        if logo_val is not None and hasattr(logo_val, 'read'):
            payload['logo_upload'] = logo_val
            del payload['logo']
        return super().to_internal_value(payload)

    def _clear_other_main_companies(
        self,
        account_id: int,
        *,
        exclude_pk: int | None = None,
    ) -> None:
        """Unset main on siblings before setting ``is_main=True`` (DB unique constraint)."""
        qs = Company.all_objects.filter(account_id=account_id, is_main=True)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        qs.update(is_main=False)

    def _apply_logo_upload(self, instance, logo_upload):
        if logo_upload is serializers.empty:
            return
        try:
            if logo_upload:
                instance.logo = save_company_logo(
                    instance.account_id,
                    instance.pk,
                    logo_upload,
                    old_logo=instance.logo or '',
                    request=self.context.get('request'),
                )
            else:
                delete_company_logo(
                    instance.logo,
                    account_id=instance.account_id,
                    company_id=instance.pk,
                )
                instance.logo = ''
        except ValueError as exc:
            raise serializers.ValidationError({'logo_upload': str(exc)}) from exc
        instance.save(update_fields=['logo'])

    def _will_be_main(self, validated_data, instance=None) -> bool:
        if 'is_main' in validated_data:
            return bool(validated_data['is_main'])
        return bool(instance and instance.is_main)

    @transaction.atomic
    def create(self, validated_data):
        logo_upload = validated_data.pop('logo_upload', serializers.empty)
        account_id = validated_data.get('account_id')
        if self._will_be_main(validated_data) and account_id is not None:
            self._clear_other_main_companies(account_id)
        instance = super().create(validated_data)
        self._apply_logo_upload(instance, logo_upload)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        logo_upload = validated_data.pop('logo_upload', serializers.empty)
        if self._will_be_main(validated_data, instance):
            self._clear_other_main_companies(
                instance.account_id,
                exclude_pk=instance.pk,
            )
        instance = super().update(instance, validated_data)
        self._apply_logo_upload(instance, logo_upload)
        return instance
