from rest_framework import serializers

from .models import (
    BookingColumn,
    BookingItem,
    BookingLine,
    FormTemplate,
    FormTemplateField,
    FormTemplateFieldOption,
)


class BookingLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingLine
        fields = [
            'id', 'label', 'field_type', 'is_required', 'price', 'value', 'options', 'sort_order',
        ]
        read_only_fields = ['id']


class BookingItemSerializer(serializers.ModelSerializer):
    field_values = BookingLineSerializer(
        source='lines',
        many=True,
        required=False,
        default=[],
    )

    class Meta:
        model = BookingItem
        fields = [
            'id', 'column', 'title', 'date_of_event', 'form_template',
            'field_values', 'notes', 'sort_order', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        aid = getattr(request.user, 'account_id', None) if request and request.user.is_authenticated else None
        if aid is not None:
            self.fields['column'].queryset = BookingColumn.objects.filter(account_id=aid)
            self.fields['form_template'].queryset = FormTemplate.objects.filter(account_id=aid)

    def _pop_field_values(self, validated_data):
        """Nested lines use ``source='lines'``, so validated_data key is ``lines``."""
        if 'lines' in validated_data:
            return validated_data.pop('lines')
        return validated_data.pop('field_values', None)

    def _save_field_values(self, booking, field_values_data):
        for idx, fv in enumerate(field_values_data):
            fv.setdefault('sort_order', idx)
            BookingLine.objects.create(
                booking=booking,
                account_id=booking.account_id,
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
        ft = attrs.get('form_template', serializers.empty)
        if ft is serializers.empty:
            ft = self.instance.form_template if self.instance else None
        if ft is not None and column is not None and ft.account_id != column.account_id:
            raise serializers.ValidationError(
                {'form_template': ['Template must belong to the same account as the column.']},
            )
        return attrs

    def create(self, validated_data):
        field_values_data = self._pop_field_values(validated_data) or []
        column = validated_data['column']
        booking = BookingItem.objects.create(
            **validated_data,
            account_id=column.account_id,
        )
        self._save_field_values(booking, field_values_data)
        return booking

    def update(self, instance, validated_data):
        field_values_data = self._pop_field_values(validated_data)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.account_id = instance.column.account_id
        instance.save()
        if field_values_data is not None:
            instance.lines.all().delete()
            self._save_field_values(instance, field_values_data)
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
