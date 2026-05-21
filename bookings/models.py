from django.conf import settings
from django.db import models


class BookingStatus(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    color = models.CharField(max_length=20, default='#1f3a5f')
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'booking_statuses'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.title


class BookingItem(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,
        db_column='company_id',
        related_name='bookings',
    )
    status = models.ForeignKey(
        BookingStatus,
        on_delete=models.CASCADE,
        related_name='items',
        db_column='status_id',
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        db_column='contact_id',
    )
    unique_id = models.CharField(max_length=7)
    title = models.CharField(max_length=255)
    date_of_event = models.DateTimeField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    required_downpayment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    notes = models.TextField(blank=True, default='')
    pdf = models.TextField(
        blank=True,
        default='',
        help_text='Absolute API URL for the secured booking PDF download route.',
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bookings'
        ordering = ['sort_order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'unique_id'],
                name='bookings_account_unique_id_uniq',
            ),
        ]

    def __str__(self):
        return self.unique_id or self.title


class BookingPayment(models.Model):
    booking = models.ForeignKey(
        BookingItem,
        on_delete=models.CASCADE,
        related_name='payments',
        db_column='booking_id',
    )
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,
        db_column='company_id',
        related_name='booking_payments',
    )
    payment_method = models.CharField(max_length=63, blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transaction_id = models.CharField(max_length=255, blank=True, default='')
    transaction_status = models.CharField(max_length=63, blank=True, default='', db_index=True)
    notes = models.TextField(blank=True, default='')
    api_response = models.JSONField(null=True, blank=True, default=None)
    transaction_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'booking_payments'
        ordering = ['-transaction_date', '-created_at']

    def __str__(self):
        return f'Payment {self.pk} booking={self.booking_id}'


class BookingPaymentLink(models.Model):
    """Public PayMongo checkout link for a booking (platform merchant account)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'

    booking = models.ForeignKey(
        BookingItem,
        on_delete=models.CASCADE,
        related_name='payment_links',
        db_column='booking_id',
    )
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,
        db_column='company_id',
        related_name='booking_payment_links',
    )
    public_token = models.UUIDField(unique=True, db_index=True)
    paymongo_checkout_session_id = models.CharField(max_length=255, blank=True, default='')
    paymongo_checkout_url = models.URLField(max_length=2048, blank=True, default='')
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    processing_fee_estimate = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    charge_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='PHP')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    expires_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booking_payment_links_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'booking_payment_links'
        ordering = ['-created_at']

    def __str__(self):
        return f'Payment link {self.public_token} booking={self.booking_id}'


class BookingUniqueIdSequence(models.Model):
    """Per-company, per-year counter for ``BookingItem.unique_id`` (YY-####)."""

    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        db_column='company_id',
        related_name='+',
    )
    year = models.PositiveSmallIntegerField()
    last_sequence = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'booking_unique_id_sequences'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'year'],
                name='booking_unique_id_seq_company_year_uniq',
            ),
        ]

    def __str__(self):
        return f'account={self.account_id} year={self.year} seq={self.last_sequence}'


class BookingGroup(models.Model):
    booking = models.ForeignKey(
        BookingItem,
        on_delete=models.CASCADE,
        related_name='groups',
        db_column='booking_id',
    )
    name = models.TextField()

    class Meta:
        db_table = 'booking_groups'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['booking', 'name'],
                name='booking_groups_booking_name_uniq',
            ),
        ]

    def __str__(self):
        return self.name


class BookingLine(models.Model):
    """Per-booking custom field row; stored in the ``booking_items`` table."""

    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    FIELD_TYPES = [
        ('text', 'Text'),
        ('textarea', 'Text Area'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('time', 'Time'),
        ('select', 'Dropdown'),
        ('checkbox', 'Checkbox'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('supplier', 'Supplier'),
    ]

    booking = models.ForeignKey(
        BookingItem,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='company_id',
        related_name='booking_lines',
    )
    tier = models.ForeignKey(
        'suppliers.Tier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tier_id',
        related_name='booking_lines',
    )
    package_version = models.ForeignKey(
        'packages.PackageVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='package_version_id',
        related_name='booking_lines',
    )
    label = models.CharField(max_length=255)
    booking_group = models.ForeignKey(
        BookingGroup,
        on_delete=models.CASCADE,
        related_name='lines',
        db_column='booking_group_id',
    )
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='text')
    is_required = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    required_downpayment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    value = models.TextField(blank=True, default='')
    options = models.JSONField(default=list, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'booking_items'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.label}: {self.value}'


class FormTemplate(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='form_templates',
        db_column='company_id',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'form_templates'
        ordering = ['name']

    def __str__(self):
        return self.name


class FormTemplateField(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    FIELD_TYPES = [
        ('text', 'Text'),
        ('textarea', 'Text Area'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('time', 'Time'),
        ('select', 'Dropdown'),
        ('checkbox', 'Checkbox'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('supplier', 'Supplier'),
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
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
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
