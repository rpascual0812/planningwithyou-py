from django import forms
from django.contrib import admin

from .models import Account, PasswordResetToken, User


class UserAdminForm(forms.ModelForm):
    """Allow setting a new password in admin (stored hashed)."""

    new_password = forms.CharField(
        label='New password',
        widget=forms.PasswordInput,
        required=False,
        help_text='Leave blank to keep the current password.',
    )

    class Meta:
        model = User
        fields = '__all__'

    def save(self, commit=True):
        user = super().save(commit=False)
        raw = self.cleaned_data.get('new_password')
        if raw:
            user.set_password(raw)
        elif not user.pk:
            user.set_unusable_password()
        if commit:
            user.save()
        return user


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'is_active',
        'contact_person',
        'contact_email',
        'timezone',
        'country',
        'created_at',
        'deleted_at',
    )
    list_filter = ('is_active', 'country')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm
    ordering = ('username',)
    list_display = (
        'id',
        'username',
        'email',
        'account',
        'is_admin',
        'is_active',
        'created_at',
        'deleted_at',
    )
    list_filter = ('is_admin', 'is_active', 'account')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'created_at', 'updated_at', 'password')

    fieldsets = (
        (None, {'fields': ('username', 'new_password', 'password')}),
        ('Personal', {'fields': ('first_name', 'last_name', 'email')}),
        ('Organization', {'fields': ('account',)}),
        ('Permissions', {'fields': ('is_admin', 'is_active')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at', 'deleted_at')}),
    )


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'token', 'created_at', 'used')
    list_filter = ('used',)
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at',)
