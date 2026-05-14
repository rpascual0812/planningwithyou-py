from django.contrib import admin

from .models import PasswordResetToken


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'token', 'created_at', 'used')
    list_filter = ('used',)
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at',)
