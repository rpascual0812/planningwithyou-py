"""ORM helpers: stamp ``auto_now`` / ``auto_now_add`` in ``companies.timezone``."""

from __future__ import annotations

from companies.timezone import company_id_for_instance, now_in_company_timezone


def patch_datetime_field_pre_save() -> None:
    from django.db.models.fields import DateTimeField

    original_pre_save = DateTimeField.pre_save

    def company_aware_pre_save(self, model_instance, add):
        if self.auto_now or (self.auto_now_add and add):
            company_id = company_id_for_instance(model_instance)
            return now_in_company_timezone(company_id)
        return original_pre_save(self, model_instance, add)

    DateTimeField.pre_save = company_aware_pre_save
