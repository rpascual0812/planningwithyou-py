from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from emails.mail import create_and_queue_email
from emails.tasks import send_email_task

from .models import PasswordResetToken
from .serializers import (
    EmailTokenObtainPairSerializer,
    PasswordResetConfirmSerializer,
    UserCreateSerializer,
    UserSerializer,
)

User = get_user_model()


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


def _send_reset_email(user):
    PasswordResetToken.objects.filter(user=user, used=False).update(used=True)
    reset = PasswordResetToken.objects.create(user=user)
    name = (
        f'{user.first_name} {user.last_name}'.strip()
        or user.username
    )
    reset_url = f'{settings.FRONTEND_URL}/reset-password/{reset.token}'
    lifetime = settings.PASSWORD_RESET_TOKEN_LIFETIME_HOURS

    log = create_and_queue_email(
        to=[user.email],
        subject='Set Your Password – Planning With You',
        body_html=(
            f'<h3>Hello {name},</h3>'
            f'<p>An account has been created for you at Planning With You.</p>'
            f'<p>Please click the link below to set your password:</p>'
            f'<p><a href="{reset_url}">{reset_url}</a></p>'
            f'<p>This link expires in {lifetime} hours.</p>'
            f'<p>If you did not expect this email, you can safely ignore it.</p>'
        ),
        body_text=(
            f'Hello {name},\n\n'
            f'An account has been created for you at Planning With You.\n'
            f'Set your password here: {reset_url}\n\n'
            f'This link expires in {lifetime} hours.\n'
            f'If you did not expect this email, you can safely ignore it.'
        ),
    )
    send_email_task.delay(log.pk)


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id', 'username', 'email', 'created_at']
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

    def perform_create(self, serializer):
        user = serializer.save()
        _send_reset_email(user)

    def perform_update(self, serializer):
        old_email = serializer.instance.email
        user = serializer.save()
        if user.email != old_email:
            _send_reset_email(user)

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class PasswordResetConfirmView(GenericAPIView):
    """POST /api/reset-password/confirm/ with { token, password }"""
    permission_classes = [AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'detail': 'Password has been set successfully.'},
            status=status.HTTP_200_OK,
        )
