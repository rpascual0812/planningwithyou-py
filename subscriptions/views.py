from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from planningwithyou.permissions import HasAccount

from .models import Subscription
from .serializers import SubscriptionSerializer


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """Subscription plans for Settings → Subscription."""

    permission_classes = [IsAuthenticated, HasAccount]
    serializer_class = SubscriptionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['sort_order', 'plan', 'base_price']
    ordering = ['sort_order', 'plan']

    def get_queryset(self):
        qs = Subscription.objects.filter(is_active=True)
        billing_cycle = self.request.query_params.get('billing_cycle', '').strip()
        if billing_cycle in Subscription.BillingCycle.values:
            qs = qs.filter(billing_cycle=billing_cycle)
        return qs
