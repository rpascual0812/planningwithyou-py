from django.db import transaction
from django.db.models import Q
from rest_framework import filters, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from planningwithyou.history.core import request_metadata
from planningwithyou.history.mixin import HistoryListMixin
from planningwithyou.history.record import (
    record_resource_create,
    record_resource_delete,
    record_resource_update,
)
from planningwithyou.history.snapshots import diff_contact, snapshot_contact
from planningwithyou.permissions import FeatureAccess, HasAccount, HasCompany

from .scope import contacts_for_user
from .serializers import ContactSerializer


class ContactViewSet(HistoryListMixin, viewsets.ModelViewSet):
    history_resource_type = 'contact'
    feature_key = 'contacts'
    permission_classes = [IsAuthenticated, HasAccount, HasCompany, FeatureAccess]
    serializer_class = ContactSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'first_name', 'last_name', 'email', 'company', 'created_at']
    ordering = ['first_name', 'last_name']

    class Pagination(PageNumberPagination):
        page_size = 10

    pagination_class = Pagination

    def list(self, request, *args, **kwargs):
        paginated = (
            request.query_params.get('paginated', '').strip().lower() in ('1', 'true', 'yes')
            or request.query_params.get('page', '').strip() != ''
        )
        if not paginated:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = (
            contacts_for_user(self.request.user)
            .select_related('company_org')
            .prefetch_related('phone_numbers', 'addresses')
        )
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(company__icontains=search)
                | Q(company_org__name__icontains=search)
                | Q(phone_numbers__number__icontains=search)
            ).distinct()
        return qs

    def _contact_with_relations(self, contact):
        return self.get_queryset().get(pk=contact.pk)

    def perform_create(self, serializer):
        contact = serializer.save()
        contact = self._contact_with_relations(contact)
        record_resource_create(
            account_id=contact.account_id,
            resource_type='contact',
            resource_id=contact.pk,
            snapshot=snapshot_contact(contact),
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )

    def perform_update(self, serializer):
        before = snapshot_contact(serializer.instance)
        contact = serializer.save()
        contact = self._contact_with_relations(contact)
        changes = diff_contact(before, snapshot_contact(contact))
        request = self.request

        def _record():
            record_resource_update(
                account_id=contact.account_id,
                resource_type='contact',
                resource_id=contact.pk,
                changes=changes,
                actor=request.user,
                metadata=request_metadata(request),
            )

        transaction.on_commit(_record)

    def perform_destroy(self, instance):
        record_resource_delete(
            account_id=instance.account_id,
            resource_type='contact',
            resource_id=instance.pk,
            changes={
                'first_name': instance.first_name,
                'last_name': instance.last_name,
                'email': instance.email,
            },
            actor=self.request.user,
            metadata=request_metadata(self.request),
        )
        instance.delete()
