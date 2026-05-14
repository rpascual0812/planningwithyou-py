from django.db import models


class BookingColumn(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    color = models.CharField(max_length=20, default='#1f3a5f')
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'booking_columns'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.title


class BookingItem(models.Model):
    column = models.ForeignKey(
        BookingColumn,
        on_delete=models.CASCADE,
        related_name='items',
    )
    title = models.CharField(max_length=255)
    date_of_event = models.DateTimeField(null=True, blank=True)
    form_template = models.ForeignKey(
        'FormTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
    )
    notes = models.TextField(blank=True, default='')
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bookings'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.title


class BookingFieldValue(models.Model):
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

    booking = models.ForeignKey(
        BookingItem,
        on_delete=models.CASCADE,
        related_name='field_values',
    )
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='text')
    is_required = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    value = models.TextField(blank=True, default='')
    options = models.JSONField(default=list, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'booking_field_values'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.label}: {self.value}'


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
