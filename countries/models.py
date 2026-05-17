from django.db import models


class Country(models.Model):
    name = models.CharField(max_length=128)
    iso_code = models.CharField(max_length=3, unique=True, db_index=True)
    iso2_code = models.CharField(max_length=2, unique=True, db_index=True)
    currency = models.CharField(max_length=128)
    currency_symbol = models.CharField(max_length=16)
    currency_code = models.CharField(max_length=3, db_index=True)

    class Meta:
        db_table = 'countries'
        ordering = ['name']

    def __str__(self):
        return self.name
