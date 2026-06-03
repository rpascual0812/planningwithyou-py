"""DRF helpers: serialize datetimes in ``companies.timezone``."""

from __future__ import annotations

from django.utils import timezone as dj_timezone
from rest_framework import serializers

from companies.middleware import request_company_id
from companies.timezone import UTC, company_id_for_instance, zoneinfo_for_company_id


class CompanyTimezoneDateTimeField(serializers.DateTimeField):
    """Output datetimes as ISO strings in the related company's IANA zone."""

    def to_representation(self, value):
        if value is None:
            return None
        instance = getattr(self.parent, 'instance', None)
        company_id = company_id_for_instance(instance) if instance is not None else None
        if company_id is None:
            request = self.context.get('request')
            if request is not None:
                company_id = request_company_id(request)
        tz = zoneinfo_for_company_id(company_id)
        if dj_timezone.is_aware(value):
            return value.astimezone(tz).isoformat()
        return dj_timezone.make_aware(value, UTC).astimezone(tz).isoformat()


def patch_drf_model_serializer_datetime_fields() -> None:
    """Use :class:`CompanyTimezoneDateTimeField` for all ``ModelSerializer`` datetimes."""
    from django.db import models
    from rest_framework import serializers

    mapping = serializers.ModelSerializer.serializer_field_mapping.copy()
    mapping[models.DateTimeField] = CompanyTimezoneDateTimeField
    serializers.ModelSerializer.serializer_field_mapping = mapping
