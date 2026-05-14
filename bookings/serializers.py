from rest_framework import serializers

from .models import (
    BookingColumn,
    BookingItem,
    FormTemplate,
    FormTemplateField,
    FormTemplateFieldOption,
)


class BookingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingItem
        fields = ['id', 'column', 'title', 'notes', 'sort_order', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


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
            'id', 'name', 'description', 'is_active',
            'fields', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _save_fields(self, template, fields_data):
        for idx, field_data in enumerate(fields_data):
            options_data = field_data.pop('options', [])
            field_data.setdefault('sort_order', idx)
            field_obj = FormTemplateField.objects.create(
                template=template, **field_data,
            )
            for opt_idx, opt in enumerate(options_data):
                opt.setdefault('sort_order', opt_idx)
                FormTemplateFieldOption.objects.create(field=field_obj, **opt)

    def create(self, validated_data):
        fields_data = validated_data.pop('fields', [])
        template = FormTemplate.objects.create(**validated_data)
        self._save_fields(template, fields_data)
        return template

    def update(self, instance, validated_data):
        fields_data = validated_data.pop('fields', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if fields_data is not None:
            instance.fields.all().delete()
            self._save_fields(instance, fields_data)

        return instance
