from django.conf import settings
from django.db import models


class TagQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class TagManager(models.Manager.from_queryset(TagQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class TagAllManager(models.Manager.from_queryset(TagQuerySet)):
    pass


class Tag(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='tags',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column='company_id',
        related_name='tags',
    )
    tag = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tags_created',
        db_column='created_by',
    )
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = TagManager()
    all_objects = TagAllManager()

    class Meta:
        db_table = 'tags'
        ordering = ['tag', 'id']

    def __str__(self):
        return self.tag


class QuotationStatus(models.Model):
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
        related_name='quotation_statuses',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    color = models.CharField(max_length=20, default='#1f3a5f')
    sort_order = models.PositiveIntegerField(default=0)
    tags = models.ManyToManyField(Tag, related_name='quotation_statuses', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quotation_statuses'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.title


class Quotation(models.Model):
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
        related_name='quotations',
    )
    status = models.ForeignKey(
        QuotationStatus,
        on_delete=models.CASCADE,
        related_name='items',
        db_column='status_id',
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotations',
        db_column='contact_id',
    )
    unique_id = models.CharField(max_length=7)
    title = models.CharField(max_length=255)
    date_of_event = models.DateTimeField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    discount_type = models.CharField(max_length=16, blank=True, default='')
    total_override_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    required_downpayment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    notes = models.TextField(blank=True, default='')
    pdf = models.TextField(
        blank=True,
        default='',
        help_text='Absolute API URL for the secured quotation PDF download route.',
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotations_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quotations'
        ordering = ['sort_order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'unique_id'],
                name='quotations_account_unique_id_uniq',
            ),
        ]

    def __str__(self):
        return self.unique_id or self.title


class QuotationPayment(models.Model):
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name='payments',
        db_column='quotation_id',
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
        related_name='quotation_payments',
    )
    payment_method = models.CharField(max_length=63, blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    charge_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Gross amount the customer paid (PayMongo ``amount``).',
    )
    base_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Quote portion credited to the quotation balance.',
    )
    platform_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Platform fee (1% of base) from the payment link.',
    )
    processing_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='PayMongo processing fee (``fee`` on the payment).',
    )
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Amount after PayMongo fee (``net_amount`` on the payment).',
    )
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transaction_id = models.CharField(max_length=255, blank=True, default='')
    transaction_status = models.CharField(max_length=63, blank=True, default='', db_index=True)
    notes = models.TextField(blank=True, default='')
    api_response = models.JSONField(null=True, blank=True, default=None)
    transaction_date = models.DateTimeField(null=True, blank=True)
    payout_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the platform marked this payment as paid out to the company.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'quotation_payments'
        ordering = ['-transaction_date', '-created_at']

    def __str__(self):
        return f'Payment {self.pk} quotation={self.quotation_id}'


class QuotationPaymentReceipt(models.Model):
    quotation_payment = models.OneToOneField(
        QuotationPayment,
        on_delete=models.CASCADE,
        related_name='receipt',
        db_column='quotation_payment_id',
    )
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name='payment_receipts',
        db_column='quotation_id',
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
        related_name='quotation_payment_receipts',
    )
    receipt_url = models.TextField(blank=True, default='')
    storage_key = models.TextField(blank=True, default='')
    emailed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quotation_payment_receipts'
        ordering = ['-created_at']

    def __str__(self):
        return f'Receipt payment={self.quotation_payment_id}'


class QuotationPaymentLink(models.Model):
    """Public checkout link for a quotation (PayMongo or Xendit)."""

    class PaymentProvider(models.TextChoices):
        PAYMONGO = 'paymongo', 'PayMongo'
        XENDIT = 'xendit', 'Xendit'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        EXPIRED = 'expired', 'Expired'
        CANCELLED = 'cancelled', 'Cancelled'

    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name='payment_links',
        db_column='quotation_id',
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
        related_name='quotation_payment_links',
    )
    public_token = models.UUIDField(unique=True, db_index=True)
    payment_provider = models.CharField(
        max_length=20,
        choices=PaymentProvider.choices,
        default=PaymentProvider.PAYMONGO,
        db_index=True,
    )
    paymongo_checkout_session_id = models.CharField(max_length=255, blank=True, default='')
    paymongo_checkout_url = models.URLField(max_length=2048, blank=True, default='')
    xendit_payment_session_id = models.CharField(max_length=255, blank=True, default='')
    xendit_checkout_url = models.URLField(max_length=2048, blank=True, default='')
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
    success_return_confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the customer success return URL was first consumed.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotation_payment_links_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quotation_payment_links'
        ordering = ['-created_at']

    def __str__(self):
        return f'Payment link {self.public_token} quotation={self.quotation_id}'


class QuotationUniqueIdSequence(models.Model):
    """Per-company, per-year counter for ``Quotation.unique_id`` (YY-####)."""

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
        db_table = 'quotation_unique_id_sequences'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'year'],
                name='quotation_unique_id_seq_company_year_uniq',
            ),
        ]

    def __str__(self):
        return f'account={self.account_id} year={self.year} seq={self.last_sequence}'


class QuotationGroup(models.Model):
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name='groups',
        db_column='quotation_id',
    )
    name = models.TextField()

    class Meta:
        db_table = 'quotation_groups'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['quotation', 'name'],
                name='quotation_groups_quotation_name_uniq',
            ),
        ]

    def __str__(self):
        return self.name


class QuotationLine(models.Model):
    """Per-quotation custom field row; stored in the ``quotation_lines`` table."""

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

    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='company_id',
        related_name='quotation_lines',
    )
    tier = models.ForeignKey(
        'suppliers.Tier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tier_id',
        related_name='quotation_lines',
    )
    package_version = models.ForeignKey(
        'packages.PackageVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='package_version_id',
        related_name='quotation_lines',
    )
    label = models.CharField(max_length=255)
    quotation_group = models.ForeignKey(
        QuotationGroup,
        on_delete=models.CASCADE,
        related_name='lines',
        db_column='quotation_group_id',
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
    supplier_type = models.ForeignKey(
        'suppliers.SupplierType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='supplier_type_id',
        related_name='+',
    )
    value = models.TextField(blank=True, default='')
    options = models.JSONField(default=list, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'quotation_lines'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.label}: {self.value}'


class History(models.Model):
    """Append-only change log for quotations and other tenant resources."""

    class ResourceType(models.TextChoices):
        QUOTATION = 'quotation', 'Quotation'
        ACCOUNT = 'account', 'Account'
        COMPANY = 'company', 'Company'
        USER = 'user', 'User'
        CONTACT = 'contact', 'Contact'
        SUPPLIER_SETTING = 'supplier_setting', 'Supplier setting'
        QUOTATION_STATUS = 'quotation_status', 'Quotation status'
        EMAIL_TEMPLATE = 'email_template', 'Email template'
        FORM_TEMPLATE = 'form_template', 'Form template'

    class EntityType(models.TextChoices):
        QUOTATION = 'quotation', 'Quotation'
        QUOTATION_LINE = 'quotation_line', 'Quotation line'
        QUOTATION_GROUP = 'quotation_group', 'Quotation group'
        ACCOUNT = 'account', 'Account'
        COMPANY = 'company', 'Company'
        USER = 'user', 'User'
        CONTACT = 'contact', 'Contact'
        SUPPLIER_SETTING = 'supplier_setting', 'Supplier setting'
        QUOTATION_STATUS = 'quotation_status', 'Quotation status'
        EMAIL_TEMPLATE = 'email_template', 'Email template'
        FORM_TEMPLATE = 'form_template', 'Form template'

    class Action(models.TextChoices):
        CREATE = 'create', 'Create'
        UPDATE = 'update', 'Update'
        DELETE = 'delete', 'Delete'
        REPLACE = 'replace', 'Replace'

    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    resource_type = models.CharField(
        max_length=32,
        choices=ResourceType.choices,
        default=ResourceType.QUOTATION,
    )
    resource_id = models.PositiveIntegerField(default=0)
    quotation = models.ForeignKey(
        Quotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='history_entries',
        db_column='quotation_id',
    )
    entity_type = models.CharField(max_length=32)
    entity_id = models.PositiveIntegerField(null=True, blank=True)
    action = models.CharField(max_length=20, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quotation_history_entries',
        db_column='actor_id',
    )
    changes = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'history'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['resource_type', 'resource_id', '-created_at']),
            models.Index(fields=['quotation', '-created_at']),
            models.Index(fields=['account', '-created_at']),
        ]

    def __str__(self):
        return (
            f'{self.action} {self.resource_type}:{self.resource_id} '
            f'({self.entity_type})'
        )


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
