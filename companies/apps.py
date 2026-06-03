from django.apps import AppConfig


class CompaniesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'companies'

    def ready(self):
        import companies.signals  # noqa: F401
        from companies.drf import patch_drf_model_serializer_datetime_fields
        from companies.orm import patch_datetime_field_pre_save

        patch_drf_model_serializer_datetime_fields()
        patch_datetime_field_pre_save()
