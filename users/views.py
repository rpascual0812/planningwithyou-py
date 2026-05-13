from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    EmailTokenObtainPairSerializer,
    UserCreateSerializer,
    UserSerializer,
)

User = get_user_model()


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'username', 'email', 'date_joined']
    ordering = ['id']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        qs = User.objects.all()
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return qs
