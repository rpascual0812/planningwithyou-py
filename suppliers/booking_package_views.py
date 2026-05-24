"""Package items for the booking supplier field (same resolution as booking PDF)."""

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.package_items import nested_package_items_for_api
from bookings.supplier_line import _package_query_for_supplier_line
from companies.models import Company
from planningwithyou.permissions import HasAccount
from suppliers.models import SupplierSetting, Tier
from users.supplier_price import resolve_active_package_for_supplier_tier


class _OptionalQueryIntField(serializers.IntegerField):
    """Treat blank query values as omitted (e.g. ``package_version_id=``)."""

    def to_internal_value(self, data):
        if data in ('', None):
            return None
        return super().to_internal_value(data)


class BookingSupplierPackageQuerySerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    tier_id = serializers.IntegerField()
    package_version_id = _OptionalQueryIntField(required=False, allow_null=True)

    def validate(self, attrs):
        request = self.context['request']
        account_id = request.user.account_id
        company_id = attrs['company_id']
        tier_id = attrs['tier_id']

        if not Company.objects.filter(pk=company_id, deleted_at__isnull=True).exists():
            raise serializers.ValidationError({'company_id': 'Invalid company.'})
        if not SupplierSetting.objects.filter(
            supplier_id=company_id,
            account_id=account_id,
            is_active=True,
        ).exists():
            raise serializers.ValidationError(
                {'company_id': 'Supplier is not active in supplier settings.'},
            )
        if not Tier.objects.filter(
            pk=tier_id,
            company_id=company_id,
            deleted_at__isnull=True,
        ).exists():
            raise serializers.ValidationError({'tier_id': 'Invalid tier for supplier.'})
        return attrs


class BookingSupplierPackageView(APIView):
    """
    Return package metadata and nested items for a supplier selection.

    Resolves the package the same way as booking PDF
    (``package_for_supplier_booking_line`` / ``_package_query_for_supplier_line``).
    """

    permission_classes = [IsAuthenticated, HasAccount]

    def get(self, request):
        query = BookingSupplierPackageQuerySerializer(
            data=request.query_params,
            context={'request': request},
        )
        query.is_valid(raise_exception=True)
        company_id = query.validated_data['company_id']
        tier_id = query.validated_data['tier_id']
        package_version_id = query.validated_data.get('package_version_id')

        package = _package_query_for_supplier_line(
            company_id,
            tier_id,
            package_version_id,
        )
        if package is None:
            package = resolve_active_package_for_supplier_tier(company_id, tier_id)
        if package is None:
            return Response(None, status=status.HTTP_200_OK)

        tier_name = package.tier.name if package.tier_id else ''
        return Response(
            {
                'id': package.id,
                'tier': package.tier_id,
                'tier_name': tier_name,
                'description': package.description or '',
                'total_price': package.total_price,
                'required_downpayment_amount': package.required_downpayment_amount,
                'items': nested_package_items_for_api(package, include_inactive=True),
            },
            status=status.HTTP_200_OK,
        )
