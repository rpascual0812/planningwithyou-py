from django.shortcuts import get_object_or_404
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from companies.models import Company
from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from django.db import transaction

from planningwithyou.history.core import field_change, request_metadata
from planningwithyou.history.mixin import HistoryListMixin
from planningwithyou.history.record import (
    record_resource_create,
    record_resource_delete,
    record_resource_update,
)
from planningwithyou.history.snapshots import (
    BOOKING_STATUS_FIELDS,
    diff_form_template,
    diff_simple,
    snapshot_form_template,
    snapshot_booking_status,
)

from .history import (
    record_booking_delete,
    record_booking_field_updates,
    record_group_delete,
)
from .models import BookingGroup, BookingItem, BookingStatus, FormTemplate
from .supplier_capacity import supplier_booking_capacity_status
from users.company_access import effective_company_id

from .scope import assert_booking_editable, bookings_for_user
from .serializers import (
    BookingItemSerializer,
    BookingStatusSerializer,
    FormTemplateSerializer,
)


class BookingStatusViewSet(HistoryListMixin, viewsets.ModelViewSet):
    history_resource_type = 'booking_status'
    feature_key = 'booking_settings_statuses'
    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    serializer_class = BookingStatusSerializer

    def get_queryset(self):
        return BookingStatus.objects.filter(account_id=self.request.user.account_id)

    def perform_create(self, serializer):
        aid = self.request.user.account_id
        max_order = (
            BookingStatus.objects.filter(account_id=aid)
            .order_by('-sort_order')
            .values_list('sort_order', flat=True)
            .first()
            or 0
        )
        status = serializer.save(account_id=aid, sort_order=max_order + 1)
        record_resource_create(
            account_id=aid,
            resource_type='booking_status',
            resource_id=status.pk,
            snapshot=snapshot_booking_status(status),
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )

    def perform_update(self, serializer):
        before = snapshot_booking_status(serializer.instance)
        status = serializer.save()
        changes = diff_simple(
            before,
            snapshot_booking_status(status),
            BOOKING_STATUS_FIELDS,
        )
        request = self.request

        def _record():
            record_resource_update(
                account_id=status.account_id,
                resource_type='booking_status',
                resource_id=status.pk,
                changes=changes,
                actor=request.user,
                metadata=request_metadata(request),
            )

        transaction.on_commit(_record)

    def perform_destroy(self, instance):
        record_resource_delete(
            account_id=instance.account_id,
            resource_type='booking_status',
            resource_id=instance.pk,
            changes={'title': instance.title},
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )
        instance.delete()

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        ids = request.data.get('order', [])
        if not isinstance(ids, list):
            return Response(
                {'order': ['Expected a list of status IDs.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        aid = request.user.account_id
        for idx, status_id in enumerate(ids):
            BookingStatus.objects.filter(pk=status_id, account_id=aid).update(sort_order=idx)
        return Response({'status': 'ok'})


class BookingItemViewSet(HistoryListMixin, viewsets.ModelViewSet):
    history_resource_type = 'booking'
    feature_key = 'bookings'
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    serializer_class = BookingItemSerializer

    def get_queryset(self):
        qs = bookings_for_user(self.request.user).select_related(
            'company',
            'status',
        ).prefetch_related(
            'groups',
            'lines__booking_group',
            'lines__company',
        )
        status_id = self.request.query_params.get('status')
        if status_id:
            qs = qs.filter(status_id=status_id)
        return qs

    def update(self, request, *args, **kwargs):
        assert_booking_editable(self.get_object(), request.user)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        assert_booking_editable(self.get_object(), request.user)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        assert_booking_editable(self.get_object(), request.user)
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        record_booking_delete(
            instance,
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )
        instance.delete()

    def perform_create(self, serializer):
        booking_status = serializer.validated_data['status']
        max_order = (
            booking_status.items.filter(
                account_id=self.request.user.account_id,
                company_id=self.request.user.company_id,
            )
            .order_by('-sort_order')
            .values_list('sort_order', flat=True)
            .first()
            or 0
        )
        serializer.save(
            sort_order=max_order + 1,
            created_by=self.request.user,
            company_id=self.request.user.company_id,
        )

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        item = self.get_object()
        assert_booking_editable(item, request.user)
        status_id = request.data.get('status')
        sort_order = request.data.get('sort_order', 0)
        if status_id is None:
            return Response(
                {'status': ['Status ID is required.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        booking_status = BookingStatus.objects.filter(
            pk=status_id,
            account_id=request.user.account_id,
        ).first()
        if booking_status is None:
            return Response(
                {'status': ['Status not found.']},
                status=status.HTTP_404_NOT_FOUND,
            )
        field_changes = {}
        if item.status_id != booking_status.pk:
            delta = field_change(item.status_id, booking_status.pk)
            if delta is not None:
                field_changes['status_id'] = delta
        if item.sort_order != sort_order:
            delta = field_change(item.sort_order, sort_order)
            if delta is not None:
                field_changes['sort_order'] = delta
        if item.account_id != booking_status.account_id:
            delta = field_change(item.account_id, booking_status.account_id)
            if delta is not None:
                field_changes['account_id'] = delta
        item.status = booking_status
        item.account_id = booking_status.account_id
        item.sort_order = sort_order
        item.save(update_fields=['status', 'account_id', 'sort_order'])
        record_booking_field_updates(
            item,
            field_changes,
            actor=request.user,
            metadata=request_metadata(request),
        )
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=['delete'], url_path=r'groups/(?P<group_id>[0-9]+)')
    def delete_group(self, request, pk=None, group_id=None):
        item = self.get_object()
        assert_booking_editable(item, request.user)
        group = get_object_or_404(BookingGroup, pk=group_id, booking=item)
        record_group_delete(
            item,
            group,
            actor=request.user,
            metadata=request_metadata(request),
        )
        group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Bulk-update sort_order (and optionally status) for multiple items."""
        updates = request.data.get('items', [])
        if not isinstance(updates, list):
            return Response(
                {'items': ['Expected a list of {id, status, sort_order}.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        base_qs = self.get_queryset()
        for entry in updates:
            item_id = entry.get('id')
            if item_id is None:
                continue
            booking = base_qs.filter(pk=item_id).first()
            if booking is None:
                continue
            if not booking.company_id == request.user.company_id:
                continue
            fields = {}
            if 'status' in entry:
                new_status_id = entry['status']
                if not BookingStatus.objects.filter(
                    pk=new_status_id,
                    account_id=request.user.account_id,
                ).exists():
                    continue
                fields['status_id'] = new_status_id
                fields['account_id'] = request.user.account_id
            if 'sort_order' in entry:
                fields['sort_order'] = entry['sort_order']
            if fields:
                header_changes = {}
                for key, new_value in fields.items():
                    old_value = getattr(booking, key, None)
                    delta = field_change(old_value, new_value)
                    if delta is not None:
                        header_changes[key] = delta
                base_qs.filter(pk=item_id).update(**fields)
                if header_changes:
                    record_booking_field_updates(
                        booking,
                        header_changes,
                        actor=request.user,
                        metadata=request_metadata(request),
                    )
        return Response({'status': 'ok'})


class SupplierBookingCapacityQuerySerializer(serializers.Serializer):
    supplier_id = serializers.IntegerField()
    date_of_event = serializers.DateField()
    exclude_booking_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_supplier_id(self, value):
        if not Company.objects.filter(pk=value, deleted_at__isnull=True).exists():
            raise serializers.ValidationError('Supplier company not found.')
        return value


class SupplierBookingCapacityView(APIView):
    """Check whether a supplier has reached ``max_bookings_per_day`` for a date."""

    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    feature_key = 'bookings'

    def get(self, request):
        query = SupplierBookingCapacityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        return Response(
            supplier_booking_capacity_status(
                request.user.account_id,
                data['supplier_id'],
                data['date_of_event'],
                exclude_booking_id=data.get('exclude_booking_id'),
            ),
        )


class FormTemplateViewSet(HistoryListMixin, viewsets.ModelViewSet):
    history_resource_type = 'form_template'
    feature_key = 'booking_settings_statuses'
    permission_classes = [IsAuthenticated, HasAccount, FeatureAccess]
    serializer_class = FormTemplateSerializer

    def get_queryset(self):
        qs = FormTemplate.objects.filter(
            account_id=self.request.user.account_id,
        ).prefetch_related('fields__options')
        raw = self.request.query_params.get('company_id', '').strip()
        requested = int(raw) if raw.isdigit() else None
        company_id = effective_company_id(self.request.user, requested)
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def _template_with_relations(self, template: FormTemplate) -> FormTemplate:
        return self.get_queryset().get(pk=template.pk)

    def perform_create(self, serializer):
        template = serializer.save()
        template = self._template_with_relations(template)
        record_resource_create(
            account_id=template.account_id,
            resource_type='form_template',
            resource_id=template.pk,
            snapshot=snapshot_form_template(template),
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )

    def perform_update(self, serializer):
        before = snapshot_form_template(serializer.instance)
        template = serializer.save()
        template = self._template_with_relations(template)
        changes = diff_form_template(before, snapshot_form_template(template))
        request = self.request

        def _record():
            record_resource_update(
                account_id=template.account_id,
                resource_type='form_template',
                resource_id=template.pk,
                changes=changes,
                actor=request.user,
                metadata=request_metadata(request),
            )

        transaction.on_commit(_record)

    def perform_destroy(self, instance):
        record_resource_delete(
            account_id=instance.account_id,
            resource_type='form_template',
            resource_id=instance.pk,
            changes={'name': instance.name},
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )
        instance.delete()
