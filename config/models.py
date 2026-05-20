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
                fields=['account', 'scope', 'name'],
                name='config_account_scope_name_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.scope}:{self.name}'
