from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .history import (
    record_booking_create,
    record_booking_update,
    snapshot_booking_full,
)
from planningwithyou.history.core import request_metadata

from planningwithyou.file_storage import (
    absolute_file_url,
    booking_pdf_file_url,
    company_logo_public_url,
)

from .tasks import generate_booking_pdf_task

from contacts.scope import contacts_for_user

from .models import (
    BookingGroup,
    BookingItem,
    BookingLine,
    BookingStatus,
    Tag,
    FormTemplate,
    FormTemplateField,
    FormTemplateFieldOption,

)
from .downpayment import (
    sum_booking_required_downpayment,
    validate_field_value_downpayment,
)
from .payment_breakdown import (
    TWOPLACES,
    booking_payment_fee_totals,
    booking_payments_paid_base_total,
    booking_remaining_balance,
)
from .scope import booking_user_can_edit
from .supplier_line import (
    package_for_supplier_booking_line,
    prepare_supplier_field_dict,
    supplier_value_json_for_line,
)
from .unique_id import allocate_booking_unique_id

DEFAULT_BOOKING_GROUP_NAME = 'Suppliers'


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
            'company',
            'tier',
            'package_version',
            'field_type',
            'is_required',
            'price',
            'required_downpayment',
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
        if instance.field_type == 'supplier':
            data['value'] = supplier_value_json_for_line(instance)
            company_id = instance.company_id
            data['company'] = company_id
            data['tier'] = instance.tier_id
            data['package_version'] = instance.package_version_id
            if company_id:
                logo_stored = ''
                company = getattr(instance, 'company', None)
                if company is not None:
                    logo_stored = company.logo or ''
                data['company_logo_url'] = company_logo_public_url(
                    logo_stored,
                    company_id,
                    request=self.context.get('request'),
                )
            else:
                data['company_logo_url'] = ''
            package = package_for_supplier_booking_line(instance)
            if package is not None:
                data['package_required_downpayment_amount'] = str(
                    package.required_downpayment_amount,
                )
            else:
                data['package_required_downpayment_amount'] = '0'
        return data


class BookingItemBoardSerializer(serializers.ModelSerializer):
    """Slim booking payload for kanban board / cards lazy loading."""

    paid_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    status_title = serializers.CharField(source='status.title', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = BookingItem
        fields = [
            'id',
            'unique_id',
            'company',
            'company_name',
            'status',
            'status_title',
            'title',
            'date_of_event',
            'total_amount',
            'notes',
            'sort_order',
            'can_edit',
            'paid_amount',
            'remaining_amount',
        ]
        read_only_fields = fields

    def get_can_edit(self, obj: BookingItem) -> bool:
        request = self.context.get('request')
        if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
            return False
        return booking_user_can_edit(obj, request.user)

    def get_paid_amount(self, obj: BookingItem) -> str:
        annotated = getattr(obj, '_paid_amount', None)
        if annotated is not None:
            return str(Decimal(annotated).quantize(TWOPLACES))
        return str(booking_payments_paid_base_total(obj.pk))

    def get_remaining_amount(self, obj: BookingItem) -> str:
        total = obj.total_amount or Decimal('0')
        annotated = getattr(obj, '_paid_amount', None)
        if annotated is not None:
            paid = Decimal(annotated)
        else:
            paid = booking_payments_paid_base_total(obj.pk)
        remaining = total - paid
        if remaining < Decimal('0'):
            remaining = Decimal('0')
        return str(remaining.quantize(TWOPLACES))


class BookingItemSerializer(serializers.ModelSerializer):
    field_values = BookingLineSerializer(
        source='lines',
        many=True,
        required=False,
        default=[],
    )
    groups = BookingGroupSerializer(many=True, required=False)
    pdf_url = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    paid_charge_amount = serializers.SerializerMethodField()
    paid_processing_fees = serializers.SerializerMethodField()
    paid_platform_fees = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    status_title = serializers.CharField(source='status.title', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)

    class Meta:
        model = BookingItem
        fields = [
            'id', 'unique_id', 'company', 'company_name', 'status', 'status_title', 'contact', 'title', 'date_of_event',
            'total_amount', 'required_downpayment_amount',
            'paid_amount', 'paid_charge_amount', 'paid_processing_fees', 'paid_platform_fees',
            'remaining_amount', 'can_edit',
            'groups', 'field_values', 'notes', 'sort_order', 'created_by',
            'pdf_url', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'unique_id', 'company', 'created_by', 'pdf_url', 'paid_amount',
            'paid_charge_amount', 'paid_processing_fees', 'paid_platform_fees',
            'remaining_amount', 'can_edit', 'created_at', 'updated_at',
        ]

    def get_can_edit(self, obj: BookingItem) -> bool:
        request = self.context.get('request')
        if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
            return False
        return booking_user_can_edit(obj, request.user)

    def _fee_totals(self, obj: BookingItem) -> dict[str, Decimal]:
        if not hasattr(self, '_fee_totals_cache'):
            self._fee_totals_cache = {}
        if obj.pk not in self._fee_totals_cache:
            self._fee_totals_cache[obj.pk] = booking_payment_fee_totals(obj.pk)
        return self._fee_totals_cache[obj.pk]

    def get_paid_amount(self, obj: BookingItem) -> str:
        return str(booking_payments_paid_base_total(obj.pk))

    def get_paid_charge_amount(self, obj: BookingItem) -> str:
        return str(self._fee_totals(obj)['charge_total'])

    def get_paid_processing_fees(self, obj: BookingItem) -> str:
        return str(self._fee_totals(obj)['processing_total'])

    def get_paid_platform_fees(self, obj: BookingItem) -> str:
        return str(self._fee_totals(obj)['platform_total'])

    def get_remaining_amount(self, obj: BookingItem) -> str:
        return str(booking_remaining_balance(obj))

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
        if aid is not None and request and request.user.is_authenticated:
            self.fields['status'].queryset = BookingStatus.objects.filter(account_id=aid)
            self.fields['contact'].queryset = contacts_for_user(request.user)

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

    def _refresh_required_downpayment_amount(self, booking):
        total = sum_booking_required_downpayment(booking)
        if booking.required_downpayment_amount != total:
            booking.required_downpayment_amount = total
            booking.save(update_fields=['required_downpayment_amount', 'updated_at'])

    def _save_field_values(self, booking, field_values_data):
        for idx, fv in enumerate(field_values_data):
            fv.setdefault('sort_order', idx)
            prepare_supplier_field_dict(fv)
            validate_field_value_downpayment(fv)
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
        if contact is not None:
            if contact.account_id != aid:
                raise serializers.ValidationError({'contact': ['Invalid contact for this account.']})
            company_id = getattr(request.user, 'company_id', None)
            if company_id is not None and contact.company_org_id != company_id:
                raise serializers.ValidationError({'contact': ['Invalid contact for this company.']})
        return attrs

    def create(self, validated_data):
        validated_data.pop('unique_id', None)
        field_values_data = self._pop_field_values(validated_data) or []
        groups_data = self._pop_groups(validated_data) or []
        request = self.context['request']
        booking_status = validated_data['status']
        account_id = booking_status.account_id
        company_id = validated_data.get('company_id') or request.user.company_id
        validated_data['unique_id'] = allocate_booking_unique_id(company_id, account_id)
        validated_data.setdefault('company_id', company_id)
        booking = BookingItem.objects.create(
            **validated_data,
            account_id=account_id,
        )
        self._save_groups(booking, groups_data)
        self._save_field_values(booking, field_values_data)
        self._refresh_required_downpayment_amount(booking)
        self._enqueue_pdf_generation(booking)
        request = self.context.get('request')
        transaction.on_commit(
            lambda: record_booking_create(
                booking,
                actor=getattr(request, 'user', None),
                metadata=request_metadata(request),
            ),
        )
        return booking

    def update(self, instance, validated_data):
        field_values_data = self._pop_field_values(validated_data)
        groups_data = self._pop_groups(validated_data)
        include_nested = field_values_data is not None or groups_data is not None
        request = self.context.get('request')
        before = snapshot_booking_full(instance)
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
        if field_values_data is not None:
            self._refresh_required_downpayment_amount(instance)
        self._enqueue_pdf_generation(instance)
        transaction.on_commit(
            lambda: record_booking_update(
                instance,
                before,
                actor=getattr(request, 'user', None),
                include_nested=include_nested,
                metadata=request_metadata(request),
            ),
        )
        return instance


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'tag', 'created_at']
        read_only_fields = ['id', 'created_at']


class TagWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['tag']

    def validate_tag(self, value):
        text = value.strip()
        if not text:
            raise serializers.ValidationError('Tag cannot be empty.')
        return text

    def create(self, validated_data):
        request = self.context['request']
        account_id = request.user.account_id
        tag_text = validated_data['tag']
        existing = (
            Tag.objects.filter(account_id=account_id, tag__iexact=tag_text)
            .order_by('id')
            .first()
        )
        if existing:
            return existing
        company_id = getattr(request.user, 'company_id', None)
        return Tag.objects.create(
            account_id=account_id,
            company_id=company_id,
            tag=tag_text,
            created_by=request.user,
        )


class BookingStatusSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )

    class Meta:
        model = BookingStatus
        fields = [
            'id', 'title', 'description', 'color',
            'sort_order', 'item_count', 'tags', 'tag_ids',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            self.fields['tag_ids'].queryset = Tag.objects.filter(
                account_id=request.user.account_id,
            )

    def get_item_count(self, obj):
        return obj.items.count()

    def _set_tags(self, instance, tag_ids):
        if tag_ids is not None:
            instance.tags.set(tag_ids)

    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        instance = super().create(validated_data)
        self._set_tags(instance, tag_ids)
        return instance

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        instance = super().update(instance, validated_data)
        self._set_tags(instance, tag_ids)
        return instance


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
            'company_id', 'fields', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_company_id(self, value):
        if value is None:
            return value
        request = self.context.get('request')
        if request is None:
            return value
        from companies.scope import company_belongs_to_account

        if not company_belongs_to_account(value, request.user.account_id):
            raise serializers.ValidationError('Company not found.')
        return value

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
        if not template.is_default:
            return
        qs = FormTemplate.objects.filter(
            is_default=True,
            account_id=template.account_id,
        )
        if template.company_id:
            qs = qs.filter(company_id=template.company_id)
        else:
            qs = qs.filter(company_id__isnull=True)
        qs.exclude(pk=template.pk).update(is_default=False)

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
