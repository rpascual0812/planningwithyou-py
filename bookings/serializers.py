import json

from django.db import transaction
from rest_framework import serializers

from planningwithyou.file_storage import absolute_file_url, booking_pdf_file_url

from .tasks import generate_booking_pdf_task

from contacts.models import Contact

from .models import (
    BookingGroup,
    BookingItem,
    BookingLine,
    BookingStatus,
    FormTemplate,
    FormTemplateField,
    FormTemplateFieldOption,
)
from .unique_id import allocate_booking_unique_id

DEFAULT_BOOKING_GROUP_NAME = 'Suppliers'


def _normalize_supplier_line(field_value: dict) -> None:
    """Move tier price from JSON value to the line price column."""
    if field_value.get('field_type') != 'supplier':
        return
    raw = field_value.get('value') or ''
    if not str(raw).strip():
        return
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(data, dict):
        return
    json_price = data.pop('price', None)
    if field_value.get('price') in (None, '') and json_price not in (None, ''):
        field_value['price'] = json_price
    tier_id = data.get('tier_id')
    supplier_id = data.get('supplier_id')
    if tier_id is None and supplier_id is None:
        field_value['value'] = ''
    else:
        field_value['value'] = json.dumps(
            {'tier_id': tier_id, 'supplier_id': supplier_id},
        )


class BookingGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingGroup
        fields = ['id', 'name']
        read_only_fields = ['id']


class BookingLineSerializer(serializers.ModelSerializer):
    booking_group_id = serializers.IntegerField(read_only=True)
    group_name = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = BookingLine
        fields = [
            'id',
            'label',
            'booking_group_id',
            'group_name',
            'field_type',
            'is_required',
            'price',
            'value',
            'options',
            'sort_order',
        ]
        read_only_fields = ['id', 'booking_group_id']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['group_name'] = (
            instance.booking_group.name
            if instance.booking_group_id
            else DEFAULT_BOOKING_GROUP_NAME
        )
        if instance.booking_group_id:
            data['booking_group_id'] = instance.booking_group_id
        if instance.field_type == 'supplier' and data.get('value'):
            payload = dict(data)
            _normalize_supplier_line(payload)
            data['value'] = payload['value']
        return data


class BookingItemSerializer(serializers.ModelSerializer):
    field_values = BookingLineSerializer(
        source='lines',
        many=True,
        required=False,
        default=[],
    )
    groups = BookingGroupSerializer(many=True, required=False)
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = BookingItem
        fields = [
            'id', 'unique_id', 'status', 'contact', 'title', 'date_of_event',
            'groups', 'field_values', 'notes', 'sort_order', 'created_by',
            'pdf_url', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'unique_id', 'created_by', 'pdf_url', 'created_at', 'updated_at',
        ]

    def get_pdf_url(self, obj):
        pdf = (obj.pdf or '').strip()
        if not pdf:
            return ''
        if pdf.startswith(('http://', 'https://')):
            return pdf
        if pdf.startswith('/'):
            request = self.context.get('request')
            return absolute_file_url(request, pdf)
        request = self.context.get('request')
        return booking_pdf_file_url(obj.pk, request=request)

    def _enqueue_pdf_generation(self, booking):
        booking_id = booking.pk
        transaction.on_commit(
            lambda: generate_booking_pdf_task.delay(booking_id),
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        aid = getattr(request.user, 'account_id', None) if request and request.user.is_authenticated else None
        if aid is not None:
            self.fields['status'].queryset = BookingStatus.objects.filter(account_id=aid)
            self.fields['contact'].queryset = Contact.objects.filter(account_id=aid)

    def _pop_field_values(self, validated_data):
        """Nested lines use ``source='lines'``, so validated_data key is ``lines``."""
        if 'lines' in validated_data:
            return validated_data.pop('lines')
        return validated_data.pop('field_values', None)

    def _pop_groups(self, validated_data):
        if 'groups' in validated_data:
            return validated_data.pop('groups')
        return None

    def _save_groups(self, booking, groups_data):
        for entry in groups_data:
            raw_name = entry.get('name') if isinstance(entry, dict) else entry
            name = (raw_name or '').strip() or DEFAULT_BOOKING_GROUP_NAME
            BookingGroup.objects.get_or_create(booking=booking, name=name)

    def _resolve_booking_group(self, booking, fv):
        fv.pop('booking_group', None)
        fv.pop('booking_group_id', None)
        group_name = (fv.pop('group_name', None) or '').strip() or DEFAULT_BOOKING_GROUP_NAME

        group, _created = BookingGroup.objects.get_or_create(
            booking=booking,
            name=group_name,
        )
        return group

    def _save_field_values(self, booking, field_values_data):
        for idx, fv in enumerate(field_values_data):
            fv.setdefault('sort_order', idx)
            _normalize_supplier_line(fv)
            booking_group = self._resolve_booking_group(booking, fv)
            BookingLine.objects.create(
                booking=booking,
                account_id=booking.account_id,
                booking_group=booking_group,
                **fv,
            )

    def validate(self, attrs):
        request = self.context.get('request')
        aid = getattr(request.user, 'account_id', None) if request and request.user.is_authenticated else None
        if aid is None:
            return attrs
        booking_status = attrs.get('status') or (
            self.instance.status if self.instance else None
        )
        if booking_status is not None and booking_status.account_id != aid:
            raise serializers.ValidationError({'status': ['Invalid status for this account.']})
        contact = attrs.get('contact')
        if contact is None and self.instance is not None:
            contact = self.instance.contact
        if contact is not None and contact.account_id != aid:
            raise serializers.ValidationError({'contact': ['Invalid contact for this account.']})
        return attrs

    def create(self, validated_data):
        validated_data.pop('unique_id', None)
        field_values_data = self._pop_field_values(validated_data) or []
        groups_data = self._pop_groups(validated_data) or []
        booking_status = validated_data['status']
        account_id = booking_status.account_id
        validated_data['unique_id'] = allocate_booking_unique_id(account_id)
        booking = BookingItem.objects.create(
            **validated_data,
            account_id=account_id,
        )
        self._save_groups(booking, groups_data)
        self._save_field_values(booking, field_values_data)
        self._enqueue_pdf_generation(booking)
        return booking

    def update(self, instance, validated_data):
        field_values_data = self._pop_field_values(validated_data)
        groups_data = self._pop_groups(validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.account_id = instance.status.account_id
        instance.save()
        if field_values_data is not None:
            instance.lines.all().delete()
            instance.groups.all().delete()
            if groups_data is not None:
                self._save_groups(instance, groups_data)
            self._save_field_values(instance, field_values_data)
        elif groups_data is not None:
            instance.groups.all().delete()
            self._save_groups(instance, groups_data)
        self._enqueue_pdf_generation(instance)
        return instance


class BookingStatusSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = BookingStatus
        fields = [
            'id', 'title', 'description', 'color',
            'sort_order', 'item_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        return obj.items.count()


class FormTemplateFieldOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormTemplateFieldOption
        fields = ['id', 'label', 'price', 'sort_order']


class FormTemplateFieldSerializer(serializers.ModelSerializer):
    options = FormTemplateFieldOptionSerializer(many=True, required=False, default=[])

    class Meta:
        model = FormTemplateField
        fields = ['id', 'label', 'field_type', 'is_required', 'price', 'options', 'sort_order']


class FormTemplateSerializer(serializers.ModelSerializer):
    fields = FormTemplateFieldSerializer(many=True, required=False, default=[])

    class Meta:
        model = FormTemplate
        fields = [
            'id', 'name', 'description', 'is_active', 'is_default',
            'fields', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _save_fields(self, template, fields_data):
        for idx, field_data in enumerate(fields_data):
            options_data = field_data.pop('options', [])
            field_data.setdefault('sort_order', idx)
            field_obj = FormTemplateField.objects.create(
                template=template,
                account_id=template.account_id,
                **field_data,
            )
            for opt_idx, opt in enumerate(options_data):
                opt.setdefault('sort_order', opt_idx)
                FormTemplateFieldOption.objects.create(
                    field=field_obj,
                    account_id=template.account_id,
                    **opt,
                )

    def _clear_other_defaults(self, template):
        if template.is_default:
            FormTemplate.objects.filter(
                is_default=True,
                account_id=template.account_id,
            ).exclude(pk=template.pk).update(is_default=False)

    def create(self, validated_data):
        fields_data = validated_data.pop('fields', [])
        request = self.context['request']
        validated_data['account_id'] = request.user.account_id
        template = FormTemplate.objects.create(**validated_data)
        self._clear_other_defaults(template)
        self._save_fields(template, fields_data)
        return template

    def update(self, instance, validated_data):
        fields_data = validated_data.pop('fields', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self._clear_other_defaults(instance)

        if fields_data is not None:
            instance.fields.all().delete()
            self._save_fields(instance, fields_data)

        return instance
