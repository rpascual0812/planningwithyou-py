import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_reset_tokens'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} – {self.token}'

    @property
    def is_expired(self):
        lifetime = getattr(settings, 'PASSWORD_RESET_TOKEN_LIFETIME_HOURS', 24)
        return timezone.now() > self.created_at + timedelta(hours=lifetime)

    @property
    def is_valid(self):
        return not self.used and not self.is_expired
