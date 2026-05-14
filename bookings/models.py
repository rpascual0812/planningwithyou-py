from django.db import models


class FormTemplate(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'form_templates'
        ordering = ['name']

    def __str__(self):
        return self.name


class FormTemplateField(models.Model):
    FIELD_TYPES = [
        ('text', 'Text'),
        ('textarea', 'Text Area'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('select', 'Dropdown'),
        ('checkbox', 'Checkbox'),
        ('email', 'Email'),
        ('phone', 'Phone'),
    ]

    template = models.ForeignKey(
        FormTemplate,
        on_delete=models.CASCADE,
        related_name='fields',
    )
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='text')
    is_required = models.BooleanField(default=False)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'form_template_fields'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.label} ({self.get_field_type_display()})'


class FormTemplateFieldOption(models.Model):
    field = models.ForeignKey(
        FormTemplateField,
        on_delete=models.CASCADE,
        related_name='options',
    )
    label = models.CharField(max_length=255)
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'form_template_field_options'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.label
