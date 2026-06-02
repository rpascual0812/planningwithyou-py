from django.db import models


class Config(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        related_name='configs',
        db_column='account_id',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='configs',
        db_column='company_id',
    )
    scope = models.TextField()
    name = models.TextField()
    value = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'config'
        ordering = ['scope', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'scope', 'name', 'company'],
                name='config_account_scope_name_company_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.scope}:{self.name}'


class ErrorLog(models.Model):
    method = models.CharField(max_length=16)
    path = models.TextField()
    query_string = models.TextField(blank=True, default='')
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    exception_type = models.CharField(max_length=255, blank=True, default='')
    exception_message = models.TextField(blank=True, default='')
    traceback = models.TextField(blank=True, default='')
    request_body = models.TextField(blank=True, default='')
    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='error_logs',
        db_column='user_id',
    )
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='error_logs',
        db_column='account_id',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_error_logs',
        db_column='resolved_by_id',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'error_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.method} {self.path} ({self.status_code or "?"})'
