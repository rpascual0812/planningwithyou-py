from django.db.models import Q
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Contact
from .serializers import ContactSerializer


class ContactViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ContactSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'first_name', 'last_name', 'email', 'company', 'created_at']
    ordering = ['first_name', 'last_name']

    def get_queryset(self):
        qs = Contact.objects.prefetch_related('phone_numbers', 'addresses').all()
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(company__icontains=search)
                | Q(phone_numbers__number__icontains=search)
            ).distinct()
        return qs
