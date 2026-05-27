from django.conf import settings
from django.db import models


class CompanyQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class CompanyManager(models.Manager.from_queryset(CompanyQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class CompanyAllManager(models.Manager.from_queryset(CompanyQuerySet)):
    pass


class Company(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='companies',
    )
    name = models.CharField(max_length=255)
    supplier_type = models.ForeignKey(
        'suppliers.SupplierType',
        on_delete=models.PROTECT,
        db_column='supplier_type_id',
        related_name='companies',
    )
    timezone = models.CharField(max_length=63, blank=True, default='')
    contact_person = models.CharField(max_length=255, blank=True, default='')
    phone_number = models.CharField(max_length=63, blank=True, default='')
    mobile_number = models.CharField(max_length=63, blank=True, default='')
    address = models.TextField(blank=True, default='')
    website = models.URLField(max_length=512, blank=True, default='')
    is_active = models.BooleanField(default=True)
    is_main = models.BooleanField(default=False)
    kyb_verified = models.BooleanField(
        default=False,
        help_text='Set when KYB verification is approved; required for live payments.',
    )
    max_bookings_per_day = models.PositiveIntegerField(default=1)
    logo = models.CharField(
        max_length=512,
        blank=True,
        default='',
        help_text='Secured API URL for the company logo download route.',
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='companies_created',
        db_column='created_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = CompanyManager()
    all_objects = CompanyAllManager()

    class Meta:
        db_table = 'companies'
        ordering = ['sort_order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['account'],
                condition=models.Q(is_main=True),
                name='companies_one_main_per_account',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.is_main and self.account_id:
            qs = Company.all_objects.filter(
                account_id=self.account_id,
                is_main=True,
            )
            if self.pk is not None:
                qs = qs.exclude(pk=self.pk)
            qs.update(is_main=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class CompanyKybVerification(models.Model):
    """
    PayMongo merchant onboarding application for a company.

    Business details are collected locally; documents and compliance review
    happen on PayMongo-hosted onboarding pages.
    """

    class BusinessType(models.TextChoices):
        SOLE_PROPRIETOR = 'sole_proprietor', 'Sole proprietorship'
        CORPORATION = 'corporation', 'Corporation'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING_PAYMONGO = 'pending_paymongo', 'Pending PayMongo verification'
        APPROVED = 'approved', 'Verified'
        REJECTED = 'rejected', 'Rejected'

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name='kyb_verification',
        db_column='company_id',
    )
    business_type = models.CharField(
        max_length=32,
        choices=BusinessType.choices,
        blank=True,
        default='',
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    paymongo_merchant_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='PayMongo platform merchant / child account id.',
    )
    onboarding_url = models.URLField(
        max_length=2048,
        blank=True,
        default='',
        help_text='PayMongo-hosted onboarding link for document upload and KYC.',
    )
    merchant_business_name = models.CharField(max_length=255, blank=True, default='')
    merchant_email = models.EmailField(blank=True, default='')
    merchant_mobile_number = models.CharField(max_length=63, blank=True, default='')
    bank_details = models.JSONField(
        default=dict,
        blank=True,
        help_text='Optional payout bank details collected before PayMongo onboarding.',
    )
    business_website = models.URLField(max_length=2048, blank=True, default='')

    # Legacy document fields (no longer collected in-app; kept for existing rows).
    # Sole proprietorship
    government_id_file = models.CharField(
        max_length=512,
        blank=True,
        default='',
        help_text='Stored file reference for valid government ID.',
    )
    dti_registration_file = models.CharField(max_length=512, blank=True, default='')
    sole_prop_business_address = models.TextField(blank=True, default='')
    sole_prop_mobile_number = models.CharField(max_length=63, blank=True, default='')
    bank_account_same_name = models.TextField(
        blank=True,
        default='',
        help_text='Bank account details; account must be under the same legal name.',
    )

    # Corporation
    sec_registration_file = models.CharField(max_length=512, blank=True, default='')
    articles_of_incorporation_file = models.CharField(max_length=512, blank=True, default='')
    bir_registration_file = models.CharField(max_length=512, blank=True, default='')
    owner_director_id_files = models.JSONField(
        default=list,
        blank=True,
        help_text='List of file references for valid IDs of owners/directors.',
    )
    business_website_social = models.TextField(
        blank=True,
        default='',
        help_text='Business website and/or social media pages.',
    )
    company_email_domain = models.CharField(max_length=255, blank=True, default='')

    # Additional checks (all business types)
    proof_of_address_file = models.CharField(max_length=512, blank=True, default='')
    business_description = models.TextField(blank=True, default='')

    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='company_kyb_reviews',
        db_column='reviewed_by',
    )
    rejection_notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'company_kyb_verifications'
        ordering = ['-updated_at']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        verified = self.status == self.Status.APPROVED
        Company.all_objects.filter(pk=self.company_id).update(kyb_verified=verified)

    def __str__(self):
        return f'KYB {self.company_id} ({self.status})'
