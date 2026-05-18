import json

from rest_framework import serializers

from .models import (
    BookingColumn,
    BookingGroup,
    BookingItem,
    BookingLine,
    FormTemplate,
    FormTemplateField,
    FormTemplateFieldOption,
)

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

    class Meta:
        model = BookingItem
        fields = [
            'id', 'column', 'title', 'date_of_event',
            'groups', 'field_values', 'notes', 'sort_order', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        aid = getattr(request.user, 'account_id', None) if request and request.user.is_authenticated else None
        if aid is not None:
            self.fields['column'].queryset = BookingColumn.objects.filter(account_id=aid)

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
        column = attrs.get('column') or (self.instance.column if self.instance else None)
        if column is not None and column.account_id != aid:
            raise serializers.ValidationError({'column': ['Invalid column for this account.']})
        return attrs

    def create(self, validated_data):
        field_values_data = self._pop_field_values(validated_data) or []
        groups_data = self._pop_groups(validated_data) or []
        column = validated_data['column']
        booking = BookingItem.objects.create(
            **validated_data,
            account_id=column.account_id,
        )
        self._save_groups(booking, groups_data)
        self._save_field_values(booking, field_values_data)
        return booking

    def update(self, instance, validated_data):
        field_values_data = self._pop_field_values(validated_data)
        groups_data = self._pop_groups(validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.account_id = instance.column.account_id
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
        return instance


class BookingColumnSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = BookingColumn
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
