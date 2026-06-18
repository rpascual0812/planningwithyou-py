"""Clone a quotation with groups and line items (no payments or PDF)."""

from __future__ import annotations

from django.db import transaction

from planningwithyou.history.core import request_metadata

from .history import record_quotation_create
from .models import Quotation, QuotationGroup, QuotationLine
from .serializers import DEFAULT_BOOKING_GROUP_NAME
from .tasks import generate_booking_pdf_task
from .unique_id import allocate_booking_unique_id


def duplicate_quotation(
    source: Quotation,
    *,
    user,
    title: str | None = None,
    request=None,
) -> Quotation:
    """
    Create a copy of ``source`` owned by the same company.

    Does not copy payments, payment links, or calendar events.
    Does not send new-quotation notification emails.
    """
    source = (
        Quotation.objects.filter(pk=source.pk)
        .prefetch_related('groups', 'lines__quotation_group')
        .first()
    )
    if source is None:
        raise Quotation.DoesNotExist

    with transaction.atomic():
        max_order = (
            Quotation.objects.filter(
                account_id=source.account_id,
                company_id=source.company_id,
                status_id=source.status_id,
            )
            .order_by('-sort_order')
            .values_list('sort_order', flat=True)
            .first()
            or 0
        )

        base_title = (source.title or '').strip() or 'Untitled quotation'
        new_title = (title or '').strip() or f'Copy of {base_title}'
        new_title = new_title[:255]

        copy = Quotation.objects.create(
            account_id=source.account_id,
            company_id=source.company_id,
            status_id=source.status_id,
            contact_id=source.contact_id,
            unique_id=allocate_booking_unique_id(
                source.company_id,
                source.account_id,
            ),
            title=new_title,
            date_of_event=source.date_of_event,
            total_amount=source.total_amount,
            required_downpayment_amount=source.required_downpayment_amount,
            notes=source.notes,
            pdf='',
            sort_order=max_order + 1,
            created_by=user,
        )

        group_map: dict[int, QuotationGroup] = {}
        for group in source.groups.all():
            group_map[group.pk] = QuotationGroup.objects.create(
                quotation=copy,
                name=group.name,
            )

        for line in source.lines.all().order_by('sort_order', 'id'):
            group = group_map.get(line.quotation_group_id)
            if group is None:
                fallback_name = (
                    line.quotation_group.name
                    if line.quotation_group_id
                    else DEFAULT_BOOKING_GROUP_NAME
                )
                group, _created = QuotationGroup.objects.get_or_create(
                    quotation=copy,
                    name=fallback_name or DEFAULT_BOOKING_GROUP_NAME,
                )
            QuotationLine.objects.create(
                quotation=copy,
                account_id=copy.account_id,
                quotation_group=group,
                label=line.label,
                company_id=line.company_id,
                tier_id=line.tier_id,
                package_version_id=line.package_version_id,
                field_type=line.field_type,
                is_required=line.is_required,
                price=line.price,
                required_downpayment=line.required_downpayment,
                supplier_type_id=line.supplier_type_id,
                value=line.value,
                options=list(line.options or []),
                sort_order=line.sort_order,
            )

        copy_id = copy.pk
        transaction.on_commit(
            lambda: generate_booking_pdf_task.delay(copy_id),
        )
        metadata = request_metadata(request) if request is not None else {}
        transaction.on_commit(
            lambda: record_quotation_create(
                Quotation.objects.get(pk=copy_id),
                actor=user,
                metadata=metadata,
            ),
        )

    return Quotation.objects.get(pk=copy.pk)
