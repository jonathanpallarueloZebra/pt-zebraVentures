from django.apps import AppConfig


class DynamicFieldsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dynamic_fields'
    verbose_name = 'Campos dinamicos'
