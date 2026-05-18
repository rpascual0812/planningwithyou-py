from django.db import models


class Contact(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    company = models.CharField(max_length=200, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'contacts'
        ordering = ['first_name', 'last_name']

    def __str__(self):
        full = f'{self.first_name} {self.last_name}'.strip()
        return full or self.email or f'Contact #{self.pk}'


class ContactNumber(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    class Label(models.TextChoices):
        MOBILE = 'mobile', 'Mobile'
        HOME = 'home', 'Home'
        WORK = 'work', 'Work'
        OTHER = 'other', 'Other'

    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='phone_numbers',
    )
    number = models.CharField(max_length=30)
    label = models.CharField(
        max_length=10,
        choices=Label.choices,
        default=Label.MOBILE,
    )
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = 'contact_numbers'

    def __str__(self):
        return f'{self.label}: {self.number}'


class ContactAddress(models.Model):
    account = models.ForeignKey(
        'users.Account',
        on_delete=models.CASCADE,
        db_column='account_id',
        related_name='+',
    )
    class Label(models.TextChoices):
        HOME = 'home', 'Home'
        WORK = 'work', 'Work'
        OTHER = 'other', 'Other'

    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='addresses',
    )
    label = models.CharField(
        max_length=10,
        choices=Label.choices,
        default=Label.HOME,
    )
    street = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    zip_code = models.CharField(max_length=20, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = 'contact_addresses'

    def __str__(self):
        parts = filter(None, [self.street, self.city, self.state, self.country])
        return f'{self.label}: {", ".join(parts)}'
